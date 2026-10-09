import os
import shutil


# ============================================================
# PROJECT PATHS (ANCHORED TO THIS FILE, NOT THE CWD)
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "best.pt"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "output"
)

DATABASE_FILE = os.path.join(
    BASE_DIR,
    "vehicle_database.csv"
)


# ============================================================
# DETECTION SETTINGS
# ============================================================

# Minimum YOLO confidence accepted for a plate detection.
CONFIDENCE_THRESHOLD = 0.30

# YOLO inference size. Larger values find smaller / more
# distant plates but take longer to process.
INFERENCE_IMG_SIZE = 1280

# Detections smaller than this (in pixels, before padding)
# are ignored because OCR cannot read them.
MIN_PLATE_WIDTH = 40
MIN_PLATE_HEIGHT = 10

# Padding added around each detected plate before cropping.
PADDING_X = 50
PADDING_Y = 30


# ============================================================
# VIDEO PROCESSING
# ============================================================

# Frames analyzed per second of video (1-3 is a good range).
VIDEO_SAMPLE_FPS = 2.0

# A plate must be read in at least this many analyzed frames
# to be accepted as a vehicle in the video.
VIDEO_MIN_HITS = 2

# A single-frame read is accepted anyway when its confidence
# is at least this value.
VIDEO_SINGLE_HIT_CONF = 0.70

# File dialog filter for video uploads.
VIDEO_FILE_TYPES = "*.mp4 *.avi *.mkv *.mov *.webm *.ogv"


# ============================================================
# TESSERACT OCR DISCOVERY
# ============================================================

TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs",
        "Tesseract-OCR",
        "tesseract.exe"
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Tesseract-OCR",
        "tesseract.exe"
    )
]


def find_tesseract():
    """Return the first usable Tesseract path, or None."""

    for candidate in TESSERACT_CANDIDATES:

        if candidate and os.path.isfile(candidate):

            return candidate

    return shutil.which("tesseract")


# ============================================================
# CAMERA CONFIGURATION (MULTI-CAMERA SIMULATION)
# ============================================================

CAMERAS = {

    "CAM-01 - Suchitra Junction": {
        "id": "CAM-01",
        "location": "Suchitra Junction"
    },

    "CAM-02 - Kukatpally": {
        "id": "CAM-02",
        "location": "Kukatpally"
    },

    "CAM-03 - JNTU Road": {
        "id": "CAM-03",
        "location": "JNTU Road"
    },

    "CAM-04 - Miyapur": {
        "id": "CAM-04",
        "location": "Miyapur"
    }
}
