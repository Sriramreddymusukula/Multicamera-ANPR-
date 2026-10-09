"""
Smoke tests for the OCR plate-cleaning logic.

Run from the project folder:

    .\\venv\\Scripts\\python.exe tests\\test_plate_cleaning.py
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from plate_cleaning import clean_plate_text


def test_clean_plate_text():

    cases = {
        # Normalization only
        "ts 08 eu 0079": "TS08EU0079",
        "TS-08-EU-0079": "TS08EU0079",
        "TG257602": "TG257602",
        "MH12AB1234": "MH12AB1234",

        # Position-aware corrections
        "T508EU0079": "TS08EU0079",
        "0D02XY1234": "OD02XY1234",
        "KA O1 AB 1234": "KA01AB1234",

        # IND hologram strip
        "IND TG 25 7602": "TG257602",
        "1NDTG257602": "TG257602",
    }

    for raw, expected in cases.items():

        got = clean_plate_text(raw)

        assert got == expected, (
            f"{raw!r}: expected {expected!r}, got {got!r}"
        )


def test_short_texts_are_not_mangled():

    assert clean_plate_text("abc") == "ABC"

    assert clean_plate_text("") == ""

    assert clean_plate_text("n/a") == "NA"


def test_config_paths_are_absolute():

    from config import (
        BASE_DIR,
        MODEL_PATH,
        OUTPUT_DIR,
        DATABASE_FILE
    )

    for path in (
        BASE_DIR,
        MODEL_PATH,
        OUTPUT_DIR,
        DATABASE_FILE
    ):

        assert os.path.isabs(path), path


def test_candidate_extraction():

    from plate_cleaning import find_plate_candidates

    def best(text):

        candidates = {}

        for plate, score in find_plate_candidates(text):

            candidates[plate] = max(
                candidates.get(plate, -100),
                score
            )

        if not candidates:

            return None

        return max(candidates, key=candidates.get)

    assert best("SOL4CBD06307") == "DL4CBD0630"

    assert best("INDTG257602") == "TG257602"

    assert best("MH12AB1234") == "MH12AB1234"

    assert best("T508EU0079") == "TS08EU0079"

    assert best("0D02XY1234") == "OD02XY1234"

    # verbatim read ending with a letter series (trailing A)
    assert best("MH02TCC43A") == "MH02TCC43A"

    assert best("1MH02TCC43A") == "MH02TCC43A"

    # Bharat (BH) series
    assert best("22BH1234AA") == "22BH1234AA"

    # garbage must be rejected (no valid candidate)
    assert best("ONCATSIN") is None

    assert best("") is None


if __name__ == "__main__":

    test_clean_plate_text()

    test_short_texts_are_not_mangled()

    test_config_paths_are_absolute()

    test_candidate_extraction()

    print("All tests passed.")
