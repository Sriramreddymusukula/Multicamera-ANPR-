from ultralytics import YOLO
import cv2
import pytesseract
import re
import os
import uuid

from config import (
    MODEL_PATH,
    OUTPUT_DIR,
    CONFIDENCE_THRESHOLD,
    INFERENCE_IMG_SIZE,
    MIN_PLATE_WIDTH,
    MIN_PLATE_HEIGHT,
    PADDING_X,
    PADDING_Y,
    find_tesseract
)


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

_tesseract_cmd = find_tesseract()

if _tesseract_cmd:

    pytesseract.pytesseract.tesseract_cmd = (
        _tesseract_cmd
    )


# ============================================================
# LAZY YOLO MODEL LOADING
# ============================================================

_model = None


def get_model():
    """Load the YOLO model on first use and cache it."""

    global _model

    if _model is None:

        if not os.path.isfile(MODEL_PATH):

            raise FileNotFoundError(
                f"YOLO model not found: {MODEL_PATH}"
            )

        print("Loading YOLO model:", MODEL_PATH)

        _model = YOLO(MODEL_PATH)

    return _model


def check_dependencies():
    """Return a list of startup problems (empty when all good)."""

    problems = []

    if not os.path.isfile(MODEL_PATH):

        problems.append(
            f"YOLO model missing: {MODEL_PATH}"
        )

    if find_tesseract() is None:

        problems.append(
            "Tesseract OCR not found. Install it or add "
            "its path to TESSERACT_CANDIDATES in config.py"
        )

    return problems


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# OCR TEXT CLEANING (POSITION-AWARE)
# ============================================================

# Letters and digits that OCR commonly confuses.
DIGIT_TO_LETTER = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "5": "S",
    "6": "G",
    "8": "B"
}

LETTER_TO_DIGIT = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "Z": "2",
    "S": "5",
    "G": "6",
    "B": "8"
}


def fix_plate_characters(plate_text):
    """
    Position-aware corrections for the Indian plate format
    SS-DD-LL(L)-NNNN:

        positions 0-1    : state code  -> letters
        positions 2-3    : district    -> digits
        middle positions : series      -> letters
        last 4 positions : serial      -> digits

    Texts with an unexpected length are returned unchanged.
    """

    if not 8 <= len(plate_text) <= 10:

        return plate_text

    chars = list(plate_text)

    n = len(chars)

    for index in range(0, 2):

        chars[index] = DIGIT_TO_LETTER.get(
            chars[index],
            chars[index]
        )

    for index in range(2, 4):

        chars[index] = LETTER_TO_DIGIT.get(
            chars[index],
            chars[index]
        )

    for index in range(n - 4, n):

        chars[index] = LETTER_TO_DIGIT.get(
            chars[index],
            chars[index]
        )

    for index in range(4, n - 4):

        chars[index] = DIGIT_TO_LETTER.get(
            chars[index],
            chars[index]
        )

    return "".join(chars)


def _normalize_text(text):
    """Uppercase, keep alphanumerics, strip noise and IND strip."""

    plate_text = text.upper()

    plate_text = re.sub(
        r"[^A-Z0-9]",
        "",
        plate_text
    )

    # --------------------------------------------------------
    # Remove the "IND" hologram text printed on Indian plates
    # --------------------------------------------------------

    if len(plate_text) > 10 and plate_text[0] == "1":

        plate_text = "I" + plate_text[1:]

    if (
        plate_text.startswith("IND")
        and len(plate_text) - 3 >= 8
    ):

        plate_text = plate_text[3:]

    return plate_text


def clean_plate_text(text):
    """
    Clean and normalize OCR output into an alphanumeric
    registration identifier, then apply position-aware
    character corrections.
    """

    return fix_plate_characters(
        _normalize_text(text)
    )


def _remove_artifact(path):
    """Delete a generated image without raising."""

    try:

        if path and os.path.exists(path):

            os.remove(path)

    except OSError as error:

        print("Could not remove artifact:", path, error)


def _remove_artifacts(detection):
    """Delete both generated images of a detection."""

    _remove_artifact(
        detection.get("cropped_plate")
    )

    _remove_artifact(
        detection.get("preprocessed_plate")
    )


def _dedupe_detections(detections):
    """
    Keep only the highest-confidence detection per plate
    text and remove the artifacts of dropped duplicates.
    """

    best_by_plate = {}

    for detection in detections:

        plate = detection["plate_number"]

        current = best_by_plate.get(plate)

        if current is None:

            best_by_plate[plate] = detection

        elif detection["confidence"] > current["confidence"]:

            _remove_artifacts(current)

            best_by_plate[plate] = detection

        else:

            _remove_artifacts(detection)

    return list(best_by_plate.values())


# ============================================================
# PLATE PREPROCESSING FOR OCR
# ============================================================

def _refine_plate_crop(plate):
    """
    Shrink a padded plate crop to the bright plate region.

    Detection crops include surrounding vehicle body; cropping
    to the plate itself makes contrast normalization much more
    effective. Returns the original crop when no clear bright
    plate-like region is found.
    """

    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, mask = cv2.threshold(
        blur,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (15, 5)
        )
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:

        return plate

    largest = max(contours, key=cv2.contourArea)

    x, y, w, h = cv2.boundingRect(largest)

    area_ratio = (w * h) / (
        plate.shape[0] * plate.shape[1]
    )

    if (
        not 0.25 <= area_ratio <= 0.97
        or w < 60
        or h < 15
    ):

        return plate

    margin_x = max(2, int(w * 0.02))
    margin_y = max(2, int(h * 0.06))

    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)
    x2 = min(plate.shape[1], x + w + margin_x)
    y2 = min(plate.shape[0], y + h + margin_y)

    return plate[y1:y2, x1:x2]


def _enhanced_gray(plate, scale=10):
    """Grayscale + enlarge + denoise a plate crop."""

    gray = cv2.cvtColor(
        plate,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC
    )

    return cv2.bilateralFilter(
        gray,
        11,
        17,
        17
    )


def preprocess_plate(plate):
    """Convert a plate crop into a clean binary image for OCR."""

    gray = _enhanced_gray(
        _refine_plate_crop(plate)
    )

    _, thresh = cv2.threshold(
        gray,
        150,
        255,
        cv2.THRESH_BINARY
    )

    return thresh


# ============================================================
# MULTI-VARIANT OCR + INDIAN PLATE CANDIDATE SCORING
# ============================================================

# Valid state / union territory codes on Indian plates.
STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN",
    "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD",
    "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ",
    "SK", "TG", "TN", "TR", "TS", "UK", "UP", "UT", "WB"
}

# Common OCR confusions, used ONLY to snap a state code to a
# valid one when it is within a single character.
STATE_CODE_CONFUSIONS = {
    "O": "DQ0U", "Q": "O0", "D": "O0", "0": "ODQ",
    "I": "L1T", "L": "I1T", "1": "IL",
    "S": "58", "5": "S",
    "B": "8RP", "8": "B",
    "Z": "2", "2": "Z",
    "G": "6C", "6": "G",
    "T": "7I", "7": "T",
    "C": "G", "U": "O", "V": "U",
    "K": "X", "X": "K",
    "N": "M", "M": "N",
    "R": "B", "P": "B",
    "J": "I", "E": "F", "F": "E", "H": "N",
    "A": "4", "4": "A"
}


def snap_state_code(code):
    """Snap a 2-letter code to a valid state code within one confusion."""

    if code in STATE_CODES:

        return code

    for position in (0, 1):

        for replacement in STATE_CODE_CONFUSIONS.get(code[position], ""):

            candidate = (
                code[:position]
                + replacement
                + code[position + 1:]
            )

            if candidate in STATE_CODES:

                return candidate

    return code


def _count_changes(before, after):
    """Number of differing characters between two strings."""

    return sum(
        1 for first, second in zip(before, after)
        if first != second
    )


def find_plate_candidates(cleaned_text):
    """
    Yield (plate, score) candidates mined from one OCR text.

    Every 8-10 character window is corrected, its state code is
    snapped to a valid one, and it is scored on Indian-plate
    structure. Candidates are penalized for characters that had
    to be corrected and for surrounding text the window does not
    explain, so a clean full match beats a noisy fragment.

    The 4-digit serial ending is required for corrected reads,
    while verbatim reads (no corrections at all) may end with a
    letter series such as  MH02TCC43A. Bharat (BH) series plates
    are recognised directly.
    """

    cleaned_text = _normalize_text(cleaned_text)

    text_length = len(cleaned_text)

    # --------------------------------------------------------
    # Bharat (BH) series:  YY BH NNNN LL
    # --------------------------------------------------------

    for match in re.finditer(
        r"[0-9]{2}BH[0-9]{4}[A-Z]{1,2}",
        cleaned_text
    ):

        yield match.group(0), 10

    # --------------------------------------------------------
    # Classic format windows
    # --------------------------------------------------------

    for length in (10, 9, 8):

        if text_length < length:

            continue

        for start in range(0, text_length - length + 1):

            window = cleaned_text[start:start + length]

            fixed = fix_plate_characters(window)

            state = snap_state_code(fixed[:2])

            if state not in STATE_CODES:

                continue

            plate = state + fixed[2:]

            corrections = _count_changes(window, fixed)

            corrections += _count_changes(fixed[:2], plate[:2])

            unexplained = text_length - length

            digits_in_serial = sum(
                char.isdigit() for char in plate[-4:]
            )

            if digits_in_serial == 4:

                base = 7

            elif digits_in_serial == 3:

                base = 5

            elif (
                digits_in_serial == 2
                and corrections == 0
                and unexplained <= 2
            ):

                # Verbatim read with a trailing letter series
                # (a little OCR noise around it is tolerated).
                base = 4

            else:

                continue

            score = base + 1

            middle = plate[2:-4]

            if any(char.isalpha() for char in middle):

                score += 1

            if any(char.isdigit() for char in middle):

                score += 1

            score -= corrections

            score -= unexplained

            yield plate, score


def _build_ocr_variants(plate):
    """Build binarization variants used for multi-pass OCR."""

    refined = _refine_plate_crop(plate)

    gray = _enhanced_gray(refined)

    gray_soft = _enhanced_gray(refined, scale=6)

    _, fixed_150 = cv2.threshold(
        gray,
        150,
        255,
        cv2.THRESH_BINARY
    )

    _, fixed_120 = cv2.threshold(
        gray,
        120,
        255,
        cv2.THRESH_BINARY
    )

    _, otsu = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # --------------------------------------------------------
    # Contrast-normalized variants: rescue low-contrast /
    # washed-out plates (light gray text on white background).
    # A gentler rescale reads fine strokes better.
    # --------------------------------------------------------

    norm = cv2.normalize(gray_soft, None, 0, 255, cv2.NORM_MINMAX)

    _, norm_otsu = cv2.threshold(
        norm,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    norm_otsu_inverted = 255 - norm_otsu

    return [
        ("fixed150", fixed_150, "--oem 3 --psm 7"),
        ("otsu", otsu, "--oem 3 --psm 7"),
        ("fixed120", fixed_120, "--oem 3 --psm 7"),
        ("otsu-block", otsu, "--oem 3 --psm 6"),
        ("norm-otsu", norm_otsu, "--oem 3 --psm 7"),
        ("norm-otsu-inv", norm_otsu_inverted, "--oem 3 --psm 7")
    ]


def _tesseract_read(image, config):
    """Run one OCR pass. Returns (text, mean confidence)."""

    try:

        data = pytesseract.image_to_data(
            image,
            config=config,
            output_type=pytesseract.Output.DICT
        )

    except Exception as error:

        print("OCR error:", error)

        return "", 0.0

    text = " ".join(
        word
        for word in data.get("text", [])
        if word and word.strip()
    )

    confidences = []

    for value in data.get("conf", []):

        try:

            confidence = float(value)

        except (TypeError, ValueError):

            continue

        if confidence >= 0:

            confidences.append(confidence)

    mean_confidence = (
        sum(confidences) / len(confidences) / 100.0
        if confidences else 0.0
    )

    return text, mean_confidence


def ocr_plate_text(plate):
    """
    Multi-variant OCR + Indian plate candidate scoring.

    Runs Tesseract over several binarization variants, mines
    valid plate candidates from every result, and returns the
    best-scoring candidate. Returns an empty string when no
    structurally valid plate is found (the detection is then
    dropped instead of storing garbage).

    Returns (plate_text, raw_texts) where raw_texts is a list
    of per-pass debug strings.
    """

    candidates = {}

    raw_texts = []

    for name, image, config in _build_ocr_variants(plate):

        text, confidence = _tesseract_read(image, config)

        raw_texts.append(f"{name}: {text!r}")

        cleaned = _normalize_text(text)

        if not cleaned:

            continue

        for candidate, score in find_plate_candidates(cleaned):

            entry = candidates.get(candidate)

            if entry is None:

                candidates[candidate] = {
                    "score": score,
                    "hits": 1,
                    "confidence": confidence
                }

            else:

                entry["score"] = max(entry["score"], score)

                entry["hits"] += 1

                entry["confidence"] = max(
                    entry["confidence"],
                    confidence
                )

    if not candidates:

        return "", raw_texts

    best_plate = max(
        candidates,
        key=lambda candidate: (
            candidates[candidate]["score"]
            + 2 * (candidates[candidate]["hits"] - 1),
            candidates[candidate]["hits"],
            candidates[candidate]["confidence"]
        )
    )

    best_combined = (
        candidates[best_plate]["score"]
        + 2 * (candidates[best_plate]["hits"] - 1)
    )

    if best_combined < 5:

        return "", raw_texts

    return best_plate, raw_texts


# ============================================================
# DETECT ALL NUMBER PLATES
# ============================================================

def detect_number_plates(image, save_artifacts=True):
    """
    Detect all readable number plates in an image or video frame.

    Parameters:
        image          : file path (str) or OpenCV BGR frame
        save_artifacts : write crop/preprocessed images into output/

    Returns a list of dictionaries, each containing:

        plate_number
        confidence
        bbox
        cropped_plate
        preprocessed_plate
        plate_image
    """

    if isinstance(image, str):

        img = cv2.imread(image)

        source = image

    else:

        img = image

        source = "<video frame>"

    if img is None:

        print("ERROR: Could not read image:", source)

        return []

    print("\n========================================")
    print("CITY ANPR - IMAGE PROCESSING")
    print("========================================")

    print("Image:", source)

    try:

        model = get_model()

    except Exception as error:

        print("ERROR: Could not load YOLO model:", error)

        return []

    # --------------------------------------------------------
    # YOLO DETECTION
    # --------------------------------------------------------

    results = model(
        img,
        conf=CONFIDENCE_THRESHOLD,
        imgsz=INFERENCE_IMG_SIZE,
        verbose=False
    )

    detections = []

    # Unique ID for output files
    image_id = uuid.uuid4().hex[:8]

    # --------------------------------------------------------
    # PROCESS YOLO RESULTS
    # --------------------------------------------------------

    for result in results:

        boxes = result.boxes

        print("Boxes found:", len(boxes))

        for index, box in enumerate(boxes):

            confidence = float(
                box.conf[0]
            )

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )

            print(
                f"Plate {index + 1} "
                f"confidence: {confidence:.3f}"
            )

            # ------------------------------------------------
            # SKIP DETECTIONS TOO SMALL TO OCR
            # ------------------------------------------------

            if (
                x2 - x1 < MIN_PLATE_WIDTH
                or y2 - y1 < MIN_PLATE_HEIGHT
            ):

                print(
                    "Skipped small detection: "
                    f"{x2 - x1}x{y2 - y1}"
                )

                continue

            # ------------------------------------------------
            # ADD PADDING
            # ------------------------------------------------

            x1 = max(0, x1 - PADDING_X)
            y1 = max(0, y1 - PADDING_Y)
            x2 = min(img.shape[1], x2 + PADDING_X)
            y2 = min(img.shape[0], y2 + PADDING_Y)

            # ------------------------------------------------
            # CROP NUMBER PLATE
            # ------------------------------------------------

            plate = img[y1:y2, x1:x2]

            if plate.size == 0:

                print("Invalid plate crop.")

                continue

            # ------------------------------------------------
            # SAVE CROPPED PLATE (OPTIONAL)
            # ------------------------------------------------

            crop_path = None

            if save_artifacts:

                crop_path = os.path.join(
                    OUTPUT_DIR,
                    f"cropped_plate_{image_id}_{index}.jpg"
                )

                cv2.imwrite(crop_path, plate)

            # ------------------------------------------------
            # PREPROCESS FOR OCR
            # ------------------------------------------------

            thresh = preprocess_plate(plate)

            preprocess_path = None

            if save_artifacts:

                preprocess_path = os.path.join(
                    OUTPUT_DIR,
                    f"preprocessed_plate_{image_id}_{index}.jpg"
                )

                cv2.imwrite(preprocess_path, thresh)

            # ------------------------------------------------
            # TESSERACT OCR (MULTI-VARIANT + CANDIDATE SCORING)
            # ------------------------------------------------

            plate_text, raw_texts = ocr_plate_text(plate)

            for raw_text in raw_texts:

                print("OCR Pass:", raw_text)

            print("Final Plate:", plate_text)

            if len(plate_text) < 4:

                print(
                    "OCR failed - dropping detection "
                    "and removing artifacts."
                )

                _remove_artifact(crop_path)

                _remove_artifact(preprocess_path)

                continue

            # ------------------------------------------------
            # STORE DETECTION
            # ------------------------------------------------

            detections.append({

                "plate_number":
                    plate_text,

                "confidence":
                    round(confidence, 4),

                "bbox": (
                    x1,
                    y1,
                    x2,
                    y2
                ),

                "cropped_plate":
                    crop_path,

                "preprocessed_plate":
                    preprocess_path,

                "plate_image":
                    plate.copy()
            })

    # ========================================================
    # DEDUPE + FINAL RESULT
    # ========================================================

    detections = _dedupe_detections(detections)

    if not detections:

        print("NO READABLE NUMBER PLATE DETECTED.")

    else:

        print(
            f"Total detections: "
            f"{len(detections)}"
        )

    print(
        "========================================\n"
    )

    return detections


# ============================================================
# SINGLE PLATE COMPATIBILITY FUNCTION
# ============================================================

def detect_number_plate(image_path):
    """
    Compatibility function.

    Returns the most confident plate number in the image,
    or "No Plate Detected".
    """

    detections = detect_number_plates(
        image_path
    )

    if not detections:

        return "No Plate Detected"

    best = max(
        detections,
        key=lambda detection: detection["confidence"]
    )

    return best["plate_number"]
