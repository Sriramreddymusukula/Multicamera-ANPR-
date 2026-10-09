"""
License plate detection pipeline.

YOLOv8 locates plates in an image or video frame, each crop is
refined and binarized into several OCR variants, and Tesseract
results are mined for structurally valid Indian plate candidates
that are scored and deduplicated.

Heavy dependencies (ultralytics/torch) are imported lazily so
importing this module and unit-testing the text logic stays cheap.
"""

import importlib.util
import logging
import os
import threading
import uuid

import cv2
import pytesseract

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
from plate_cleaning import (
    clean_plate_text,
    find_plate_candidates,
    fix_plate_characters,
    normalize_text as _normalize_text,
    snap_state_code
)

logger = logging.getLogger(__name__)


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

_tesseract_cmd = find_tesseract()

if _tesseract_cmd:

    pytesseract.pytesseract.tesseract_cmd = (
        _tesseract_cmd
    )


# ============================================================
# LAZY YOLO MODEL LOADING (THREAD-SAFE)
# ============================================================

_model = None

_model_lock = threading.Lock()


def get_model():
    """Load the YOLO model on first use and cache it."""

    global _model

    if _model is None:

        if not os.path.isfile(MODEL_PATH):

            raise FileNotFoundError(
                f"YOLO model not found: {MODEL_PATH}"
            )

        with _model_lock:

            if _model is None:

                from ultralytics import YOLO

                logger.info("Loading YOLO model: %s", MODEL_PATH)

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

    try:

        if importlib.util.find_spec("ultralytics") is None:

            problems.append(
                "Ultralytics package not installed. Run: "
                "pip install -r requirements.txt"
            )

    except (ImportError, ValueError):

        problems.append(
            "Ultralytics package not importable. Run: "
            "pip install -r requirements.txt"
        )

    return problems


def _ensure_output_dir():

    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _remove_artifact(path):
    """Delete a generated image without raising."""

    try:

        if path and os.path.exists(path):

            os.remove(path)

    except OSError as error:

        logger.warning("Could not remove artifact %s: %s", path, error)


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


def _prepare_grays(plate):
    """
    Compute the shared preprocessing once per plate crop.

    Returns (gray, gray_soft) where gray is the default enlarged
    denoised image and gray_soft uses a gentler rescale. Both are
    reused by preprocess_plate() and all OCR variants so each
    crop is refined and filtered exactly once.
    """

    refined = _refine_plate_crop(plate)

    return (
        _enhanced_gray(refined),
        _enhanced_gray(refined, scale=6)
    )


def preprocess_plate(plate, prepared=None):
    """Convert a plate crop into a clean binary image for OCR."""

    if prepared is None:

        prepared = _prepare_grays(plate)

    gray = prepared[0]

    _, thresh = cv2.threshold(
        gray,
        150,
        255,
        cv2.THRESH_BINARY
    )

    return thresh


# ============================================================
# MULTI-VARIANT OCR
# ============================================================

def _build_ocr_variants(plate, prepared=None):
    """Build binarization variants used for multi-pass OCR."""

    if prepared is None:

        prepared = _prepare_grays(plate)

    gray, gray_soft = prepared

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

        logger.debug("OCR error: %s", error)

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


def ocr_plate_text(plate, prepared=None):
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

    for name, image, config in _build_ocr_variants(plate, prepared):

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

def detect_number_plates(image, save_artifacts=True, verbose=True):
    """
    Detect all readable number plates in an image or video frame.

    Parameters:
        image          : file path (str) or OpenCV BGR frame
        save_artifacts : write crop/preprocessed images into output/
        verbose        : log per-detection progress at INFO level;
                         when False, details drop to DEBUG level

    Returns a list of dictionaries, each containing:

        plate_number
        confidence
        bbox
        cropped_plate
        preprocessed_plate
        plate_image
    """

    log = logger.info if verbose else logger.debug

    if isinstance(image, str):

        img = cv2.imread(image)

        source = image

    else:

        img = image

        source = "<video frame>"

    if img is None:

        logger.error("Could not read image: %s", source)

        return []

    log("ANPR image processing: %s", source)

    try:

        model = get_model()

    except Exception as error:

        logger.error("Could not load YOLO model: %s", error)

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

    if save_artifacts:

        _ensure_output_dir()

    # --------------------------------------------------------
    # PROCESS YOLO RESULTS
    # --------------------------------------------------------

    for result in results:

        boxes = result.boxes

        log("Boxes found: %d", len(boxes))

        for index, box in enumerate(boxes):

            confidence = float(
                box.conf[0]
            )

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )

            log(
                "Plate %d confidence: %.3f",
                index + 1,
                confidence
            )

            # ------------------------------------------------
            # SKIP DETECTIONS TOO SMALL TO OCR
            # ------------------------------------------------

            if (
                x2 - x1 < MIN_PLATE_WIDTH
                or y2 - y1 < MIN_PLATE_HEIGHT
            ):

                log(
                    "Skipped small detection: %dx%d",
                    x2 - x1,
                    y2 - y1
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

                log("Invalid plate crop.")

                continue

            # ------------------------------------------------
            # SHARED PREPROCESSING (COMPUTED ONCE)
            # ------------------------------------------------

            prepared = _prepare_grays(plate)

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

            thresh = preprocess_plate(plate, prepared)

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

            plate_text, raw_texts = ocr_plate_text(plate, prepared)

            for raw_text in raw_texts:

                logger.debug("OCR pass: %s", raw_text)

            log("Final plate: %r", plate_text)

            if len(plate_text) < 4:

                log(
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

        log("No readable number plate detected.")

    else:

        log(
            "Total detections: %d",
            len(detections)
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
