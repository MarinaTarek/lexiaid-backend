import os
import json
from uuid import uuid4

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from groq import Groq

from utils.grammar import get_corrections


voice = Blueprint("voice", __name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─── helpers ────────────────────────────────────────────────────────────────

def _get_uploaded_audio():
    for field_name in ("audio", "file", "voice", "recording"):
        if field_name in request.files:
            return request.files[field_name], field_name
    return None, None


def _save_audio_file(audio):
    original_filename = secure_filename(audio.filename or "")
    extension = os.path.splitext(original_filename)[1] or ".m4a"
    filename = f"{uuid4().hex}{extension}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    audio.save(path)
    return path, filename


def _transcribe(path: str) -> str:
    with open(path, "rb") as f:
        result = groq_client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f
        )
    return result.text.strip()


def _correct_with_groq(text: str) -> dict:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an English grammar teacher. "
                    "Always respond ONLY with a valid JSON object. "
                    "No markdown, no extra text. "
                    "Keys: correction (corrected sentence), explanation (short friendly explanation)."
                )
            },
            {
                "role": "user",
                "content": f"Correct this sentence: {text}"
            }
        ]
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
        return {
            "correction": data.get("correction", text),
            "explanation": data.get("explanation", ""),
        }
    except json.JSONDecodeError:
        return {
            "correction": text,
            "explanation": raw,
        }


def _build_response(speech: str, audio_filename: str = None) -> dict:
    result = _correct_with_groq(speech)
    correction = result["correction"]
    explanation = result["explanation"]

    return {
        "speech": speech,
        "correction": correction,
        "correctedText": correction,
        "corrections": get_corrections(speech, correction),
        "explanation": explanation,
        "audioFile": audio_filename,
        "message": "Audio transcribed and corrected successfully.",
    }


# ─── route ──────────────────────────────────────────────────────────────────

@voice.route("/chat", methods=["POST"])
@voice.route("/voice/chat", methods=["POST"])
def chat():
    audio, field_name = _get_uploaded_audio()
    speech = ""

    if request.is_json:
        speech = (request.get_json(silent=True) or {}).get("text", "").strip()
    else:
        speech = request.form.get("text", "").strip()

    if audio is None and not speech:
        return jsonify({
            "error": "No audio file or text provided.",
            "expectedFields": ["audio", "file", "voice", "recording"],
        }), 400

    if audio is None:
        return jsonify(_build_response(speech))

    if not audio.filename:
        return jsonify({"error": "Audio file has no filename."}), 400

    path, filename = _save_audio_file(audio)

    if speech:
        response = _build_response(speech, filename)
    else:
        try:
            speech = _transcribe(path)
        except Exception as e:
            return jsonify({"error": f"Transcription failed: {str(e)}"}), 500

        response = _build_response(speech, filename)

    response["savedPath"] = path
    return jsonify(response)