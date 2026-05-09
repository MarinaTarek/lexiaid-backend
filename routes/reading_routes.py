import random
import re
from flask import Blueprint, request, jsonify

reading_bp = Blueprint("reading", __name__)

# ── Random sentences pool ────────────────────────────────────────────────────

SENTENCES = [
    "The sun rises in the east and sets in the west every day.",
    "She reads a new book every week to improve her vocabulary.",
    "Children learn languages faster than adults in most cases.",
    "The library is a quiet place where people go to study.",
    "He forgot his umbrella and got wet in the rain.",
    "Practice speaking English every day to build your confidence.",
    "The cat sat on the mat and looked out the window.",
    "Good habits take time to build but are worth the effort.",
    "She wrote a letter to her friend who lives far away.",
    "The train arrives at the station every hour on time.",
    "Learning new words helps you express yourself more clearly.",
    "He cooked a delicious meal for his family last night.",
    "The students listened carefully to the teacher's instructions.",
    "Reading every day improves your brain and concentration skills.",
    "Practice makes perfect and helps you become a better reader.",
    "The dog ran across the park and jumped into the lake.",
    "She smiled when she heard the good news from her sister.",
    "The weather was cold so they stayed inside and drank tea.",
    "He finished his homework before dinner and then watched a movie.",
    "The flowers in the garden bloom every spring without fail.",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for comparison."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _compare_words(original: str, spoken: str):
    """
    Word-by-word comparison between the original sentence and what the user said.
    Returns a list of dicts with per-word results.
    """
    orig_words   = original.split()
    spoken_words = spoken.split()
    results = []

    for i, orig_word in enumerate(orig_words):
        spoken_word = spoken_words[i] if i < len(spoken_words) else ""
        correct = _normalize(orig_word) == _normalize(spoken_word)
        results.append({
            "word":    orig_word,
            "spoken":  spoken_word,
            "correct": correct,
        })

    return results


# ── Routes ───────────────────────────────────────────────────────────────────

@reading_bp.route("/reading/sentence", methods=["GET"])
def get_sentence():
    """Return a random sentence for the user to read."""
    sentence = random.choice(SENTENCES)
    return jsonify({"sentence": sentence})


@reading_bp.route("/reading/check", methods=["POST"])
def check_reading():
    """
    Receive the original sentence + what the user spoke, then return:
      - word_results  : per-word correct/wrong
      - score         : percentage of correct words
      - explanation   : short human-readable feedback

    NOTE: T5 grammar correction is removed from this endpoint to avoid
    blocking the response. Word comparison is instant.
    """
    data = request.get_json()

    original = data.get("original", "").strip()
    spoken   = data.get("spoken",   "").strip()

    if not original or not spoken:
        return jsonify({"error": "Both 'original' and 'spoken' are required"}), 400

    # ✅ Per-word comparison - fast, no ML model needed
    word_results  = _compare_words(original, spoken)
    total         = len(word_results)
    correct_count = sum(1 for w in word_results if w["correct"])
    wrong_count   = total - correct_count
    score         = round((correct_count / total) * 100) if total > 0 else 0

    # Build explanation
    wrong_words = [w["word"] for w in word_results if not w["correct"]]
    if score == 100:
        explanation = "Perfect! You read the sentence correctly."
    elif score >= 70:
        explanation = (
            f"Good job! You got {correct_count} out of {total} words right. "
            f"Try to work on: {', '.join(wrong_words)}."
        )
    else:
        explanation = (
            f"Keep practicing! You got {correct_count} out of {total} words right. "
            f"The words that need work are: {', '.join(wrong_words)}."
        )

    return jsonify({
        "original":      original,
        "spoken":        spoken,
        "word_results":  word_results,
        "score":         score,
        "correct_words": correct_count,
        "wrong_words":   wrong_count,
        "explanation":   explanation,
    })