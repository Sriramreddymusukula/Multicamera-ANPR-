"""
Pure plate-text utilities: normalization and Indian plate candidate
scoring.

This module intentionally has no OpenCV / OCR / ML dependencies so
the plate-correction logic can be unit-tested and reused without the
heavy detection stack.
"""

import re


# ============================================================
# CHARACTER CONFUSION TABLES
# ============================================================

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


def normalize_text(text):
    """Uppercase, keep alphanumerics, strip noise and IND strip."""

    plate_text = text.upper()

    plate_text = re.sub(
        r"[^A-Z0-9]",
        "",
        plate_text
    )

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
        normalize_text(text)
    )


# ============================================================
# INDIAN PLATE CANDIDATE SCORING
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

    cleaned_text = normalize_text(cleaned_text)

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

            # The district starts immediately after the state code.
            # Requiring its first digit prevents plausible-looking OCR
            # fragments such as UKU7BS1542 from being accepted as plates.
            if not plate[2].isdigit():
                continue

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
