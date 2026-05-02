from flask import Blueprint, request, jsonify
from services.t5_service import correct_text_t5
from utils.grammar import get_corrections

correction_bp = Blueprint("correction", __name__)

@correction_bp.route("/correct", methods=["POST"])
def correct():
    data = request.get_json()
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    corrected = correct_text_t5(text)
    corrections = get_corrections(text, corrected)

    word_count = len(text.split())
    to_fix = len(corrections)
    correct_words = word_count - to_fix

    similarity = (correct_words / word_count * 100) if word_count > 0 else 0

    return jsonify({
        "input": text,
        "correctedText": corrected,
        "corrections": corrections,
        "word_count": word_count,
        "correct_words": correct_words,
        "to_fix": to_fix,
        "similarity": similarity
    })