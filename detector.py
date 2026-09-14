from ultralytics import YOLO
import cv2
import pytesseract
import re
import os
import uuid


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ============================================================
# LOAD YOLO MODEL
# ============================================================

model = YOLO("models/best.pt")


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

os.makedirs("output", exist_ok=True)


# ============================================================
# CLEAN OCR TEXT
# ============================================================

def clean_plate_text(text):
    """
    Clean and normalize OCR output.
    """

    # Convert to uppercase
    text = text.upper()

    # Remove spaces, symbols and special characters
    plate_text = re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )

    # Common OCR corrections
    plate_text = (
        plate_text
        .replace("O", "0")
        .replace("I", "1")
        .replace("S", "5")
    )

    return plate_text


# ============================================================
# DETECT ALL NUMBER PLATES
# ============================================================

def detect_number_plates(image_path):
    """
    Detect all number plates in an image.

    Returns a list containing:

        plate_number
        confidence
        bbox
        cropped_plate
        preprocessed_plate
    """

    # --------------------------------------------------------
    # READ IMAGE
    # --------------------------------------------------------

    img = cv2.imread(image_path)

    if img is None:

        print(
            "ERROR: Could not read image:",
            image_path
        )

        return []

    print("\n========================================")
    print("CITY ANPR - IMAGE PROCESSING")
    print("========================================")

    print(
        "Image:",
        image_path
    )

    # --------------------------------------------------------
    # YOLO DETECTION
    # --------------------------------------------------------
    # Lower confidence allows our trained model to detect
    # plates that may have weaker confidence scores.

    results = model(
        img,
        conf=0.10
    )

    detections = []

    # Unique ID for output files
    image_id = uuid.uuid4().hex[:8]

    # --------------------------------------------------------
    # PROCESS YOLO RESULTS
    # --------------------------------------------------------

    for result in results:

        boxes = result.boxes

        print(
            "Boxes found:",
            len(boxes)
        )

        # ----------------------------------------------------
        # PROCESS EVERY DETECTED PLATE
        # ----------------------------------------------------

        for index, box in enumerate(boxes):

            # ------------------------------------------------
            # CONFIDENCE
            # ------------------------------------------------

            confidence = float(
                box.conf[0]
            )

            print(
                f"Plate {index + 1} "
                f"confidence: {confidence:.3f}"
            )

            # ------------------------------------------------
            # BOUNDING BOX
            # ------------------------------------------------

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )

            print(
                "Original coordinates:",
                x1,
                y1,
                x2,
                y2
            )

            # ------------------------------------------------
            # ADD PADDING
            # ------------------------------------------------

            x1 = max(
                0,
                x1 - 50
            )

            y1 = max(
                0,
                y1 - 30
            )

            x2 = min(
                img.shape[1],
                x2 + 50
            )

            y2 = min(
                img.shape[0],
                y2 + 30
            )

            print(
                "Padded coordinates:",
                x1,
                y1,
                x2,
                y2
            )

            # ------------------------------------------------
            # CROP NUMBER PLATE
            # ------------------------------------------------

            plate = img[
                y1:y2,
                x1:x2
            ]

            if plate.size == 0:

                print(
                    "Invalid plate crop."
                )

                continue

            # ------------------------------------------------
            # SAVE CROPPED PLATE
            # ------------------------------------------------

            crop_filename = (
                f"cropped_plate_"
                f"{image_id}_"
                f"{index}.jpg"
            )

            crop_path = os.path.join(
                "output",
                crop_filename
            )

            cv2.imwrite(
                crop_path,
                plate
            )

            # ------------------------------------------------
            # GRAYSCALE
            # ------------------------------------------------

            gray = cv2.cvtColor(
                plate,
                cv2.COLOR_BGR2GRAY
            )

            # ------------------------------------------------
            # ENLARGE
            # ------------------------------------------------

            gray = cv2.resize(
                gray,
                None,
                fx=10,
                fy=10,
                interpolation=cv2.INTER_CUBIC
            )

            # ------------------------------------------------
            # NOISE REDUCTION
            # ------------------------------------------------

            gray = cv2.bilateralFilter(
                gray,
                11,
                17,
                17
            )

            # ------------------------------------------------
            # THRESHOLD
            # ------------------------------------------------

            _, thresh = cv2.threshold(
                gray,
                150,
                255,
                cv2.THRESH_BINARY
            )

            # ------------------------------------------------
            # SAVE PREPROCESSED PLATE
            # ------------------------------------------------

            preprocess_filename = (
                f"preprocessed_plate_"
                f"{image_id}_"
                f"{index}.jpg"
            )

            preprocess_path = os.path.join(
                "output",
                preprocess_filename
            )

            cv2.imwrite(
                preprocess_path,
                thresh
            )

            # ------------------------------------------------
            # TESSERACT OCR
            # ------------------------------------------------

            custom_config = (
                r"--oem 3 --psm 7"
            )

            text = pytesseract.image_to_string(
                thresh,
                config=custom_config
            )

            print(
                "OCR Raw Text:",
                repr(text)
            )

            # ------------------------------------------------
            # CLEAN OCR
            # ------------------------------------------------

            plate_text = clean_plate_text(
                text
            )

            # ------------------------------------------------
            # VALIDATE
            # ------------------------------------------------

            if len(plate_text) < 4:

                plate_text = "OCR Failed"

            print(
                "Final Plate:",
                plate_text
            )

            # ------------------------------------------------
            # STORE DETECTION
            # ------------------------------------------------

            detection = {

                "plate_number":
                    plate_text,

                "confidence":
                    round(
                        confidence,
                        4
                    ),

                "bbox": (
                    x1,
                    y1,
                    x2,
                    y2
                ),

                "cropped_plate":
                    crop_path,

                "preprocessed_plate":
                    preprocess_path
            }

            detections.append(
                detection
            )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    if not detections:

        print(
            "NO NUMBER PLATE DETECTED BY YOLO."
        )

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

    Returns the first successfully recognized
    plate number as a string.
    """

    detections = detect_number_plates(
        image_path
    )

    if not detections:

        return "No Plate Detected"

    # --------------------------------------------------------
    # Find valid OCR result
    # --------------------------------------------------------

    for detection in detections:

        plate = detection[
            "plate_number"
        ]

        if plate not in (
            "OCR Failed",
            "No Plate Detected"
        ):

            return plate

    return "OCR Failed"