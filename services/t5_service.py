import os
import re

import language_tool_python


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from happytransformer import HappyTextToText


T5_MODEL = "vennify/t5-base-grammar-correction"


ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"^[A-Za-z']+$")
SPELLING_RULES = {"MORFOLOGIK_RULE_EN_US"}
COMMON_WORD_FIXES = {
    "freind": "friend",
    "frind": "friend",
    "frindt": "friend",
    "helo": "hello",
}

_happy_tt = None
_language_tool = None


def _is_supported_english_text(text):
    return bool(LATIN_RE.search(text)) and not ARABIC_RE.search(text)


def _get_language_tool():
    global _language_tool

    if _language_tool is None:
        _language_tool = language_tool_python.LanguageTool("en-US")

    return _language_tool


def _get_happy_tt():
    global _happy_tt

    if _happy_tt is None:
        _happy_tt = HappyTextToText("T5", T5_MODEL)

    return _happy_tt


def _generate_with_t5(text):
    happy_tt = _get_happy_tt()
    happy_tt._load_pipeline()

    output = happy_tt._pipeline(
        text,
        max_new_tokens=64,
        do_sample=False,
    )
    return output[0]["generated_text"]


def _edit_distance(left, right):
    left = left.lower()
    right = right.lower()

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        previous = current

    return previous[-1]


def _match_case(original, replacement):
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement.capitalize()
    return replacement.lower()


def _choose_spelling_replacement(word, replacements, is_first_word):
    normalized_word = word.lower()

    if normalized_word in COMMON_WORD_FIXES:
        return _match_case(word, COMMON_WORD_FIXES[normalized_word])

    clean_replacements = [
        replacement
        for replacement in replacements
        if WORD_RE.match(replacement)
    ]

    if not clean_replacements:
        return None

    best = min(
        clean_replacements,
        key=lambda replacement: (
            _edit_distance(normalized_word, replacement),
            len(replacement),
            clean_replacements.index(replacement),
        ),
    )

    return _match_case(word, best)


def _apply_spelling_corrections(text):
    matches = [
        match
        for match in _get_language_tool().check(text)
        if match.rule_id in SPELLING_RULES and match.replacements
    ]

    corrected = text
    for match in reversed(matches):
        start = match.offset
        end = start + match.error_length
        wrong_word = corrected[start:end]
        replacement = _choose_spelling_replacement(
            wrong_word,
            match.replacements,
            start == 0,
        )

        if replacement:
            corrected = corrected[:start] + replacement + corrected[end:]

    return corrected


def correct_text_t5(text):
    text = " ".join(text.strip().split())

    if not text:
        return ""

    # This model is trained for English grammar correction. Sending Arabic or
    # mixed Arabic/English text through it produces unreliable rewritten text.
    if not _is_supported_english_text(text):
        return text

    text = _apply_spelling_corrections(text)

    if len(text.split()) <= 2:
        return text

    corrected = _generate_with_t5(f"grammar: {text}").strip()

    return corrected or text
