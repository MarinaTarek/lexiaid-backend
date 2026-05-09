from flask import Blueprint, request, jsonify
from db import get_db_connection
from datetime import date, timedelta, datetime
from psycopg2.extras import RealDictCursor

progress_bp = Blueprint("progress", __name__)


# =========================
# helpers
# =========================

def safe_float(value):
    return float(value or 0)


def level_one_display_score(value):
    score = max(0, min(safe_float(value), 100))
    return round((score ** 1.2) * 0.1, 2)


def level_one_points(value):
    score = max(0, min(safe_float(value), 100))
    return max(1, min(5, int(score // 25) + 1))


def weighted_average_score(items):
    total_sessions = sum(sessions for _, sessions in items)

    if total_sessions == 0:
        return 0

    total_score = sum(safe_float(score) * sessions for score, sessions in items)
    return round(total_score / total_sessions, 2)


def _normalize_to_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date()

    raise ValueError(f"Unsupported last_active value: {value!r}")


def _calc_streak_and_days(user, today):
    streak = user.get("streak") or 0
    active_days = user.get("active_days") or 0
    last_date = _normalize_to_date(user.get("last_active"))

    if last_date == today:
        return streak, active_days

    active_days += 1

    if last_date == today - timedelta(days=1):
        streak += 1
    else:
        streak = 1

    return streak, active_days


def _today_and_now():
    now = datetime.now()
    return now.date(), now


# =========================
# GET PROGRESS (ALL)
# =========================
@progress_bp.route("/progress/<int:user_id>", methods=["GET"])
def get_progress(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT 
            points,
            streak,
            active_days,
            tasks_done,
            last_active,

            reading_sessions,
            writing_sessions,
            speaking_sessions,
            quiz_sessions,

            reading_accuracy,
            writing_accuracy,
            pronunciation_score,
            quiz_accuracy

        FROM progress
        WHERE user_id = %s
    """, (user_id,))

    data = cursor.fetchone()

    if not data:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "No data"}), 404

    today, now = _today_and_now()
    streak, active_days = _calc_streak_and_days(data, today)

    cursor.execute("""
        UPDATE progress SET
            streak = %s,
            active_days = %s,
            last_active = %s
        WHERE user_id = %s
    """, (streak, active_days, now, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    data["streak"] = streak
    data["active_days"] = active_days
    data["last_active"] = now
    data["overall_progress"] = weighted_average_score([
        (data.get("reading_accuracy"), data.get("reading_sessions") or 0),
        (data.get("writing_accuracy"), data.get("writing_sessions") or 0),
        (data.get("pronunciation_score"), data.get("speaking_sessions") or 0),
        (data.get("quiz_accuracy"), data.get("quiz_sessions") or 0),
    ])

    return jsonify({
    "status": "success",

    "points": data.get("points", 0),
    "streak": data.get("streak", 0),
    "active_days": data.get("active_days", 0),
    "tasks_done": data.get("tasks_done", 0),
    "last_active": (
        data.get("last_active").isoformat()
        if data.get("last_active") else None
    ),

    "reading_sessions": data.get("reading_sessions", 0),
    "writing_sessions": data.get("writing_sessions", 0),
    "speaking_sessions": data.get("speaking_sessions", 0),
    "quiz_sessions": data.get("quiz_sessions", 0),

    "reading_accuracy": level_one_display_score(data.get("reading_accuracy")),
    "writing_accuracy": level_one_display_score(data.get("writing_accuracy")),
    "pronunciation_score": level_one_display_score(data.get("pronunciation_score")),
    "quiz_accuracy": level_one_display_score(data.get("quiz_accuracy")),
    "overall_progress": level_one_display_score(data.get("overall_progress")),
})

# =========================
# SAVE READING PROGRESS
# =========================
@progress_bp.route("/progress/reading/save", methods=["POST"])
def save_reading_progress():

    data = request.json
    if not data or "user_id" not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    user_id       = data["user_id"]
    words_read    = data.get("words_read", 0)
    correct_count = data.get("correct_count", 0)
    error_count   = data.get("error_count", 0)
    new_accuracy  = safe_float(data.get("accuracy"))
    points_earned = level_one_points(new_accuracy)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today, now = _today_and_now()

    cursor.execute("SELECT * FROM progress WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        old_sessions = user["reading_sessions"] or 0
        old_accuracy = safe_float(user["reading_accuracy"])

        total_sessions = old_sessions + 1
        avg_accuracy = (old_accuracy * old_sessions + new_accuracy) / total_sessions

        streak, active_days = _calc_streak_and_days(user, today)

        cursor.execute("""
            UPDATE progress SET
                words_read = COALESCE(words_read, 0) + %s,
                correct_count = COALESCE(correct_count, 0) + %s,
                error_count = COALESCE(error_count, 0) + %s,
                reading_accuracy = %s,
                reading_sessions = COALESCE(reading_sessions, 0) + 1,
                points = COALESCE(points, 0) + %s,
                tasks_done = COALESCE(tasks_done, 0) + 1,
                streak = %s,
                active_days = %s,
                last_active = %s
            WHERE user_id = %s
        """, (words_read, correct_count, error_count,
              avg_accuracy, points_earned,
              streak, active_days, now, user_id))

    else:
        cursor.execute("""
            INSERT INTO progress
                (user_id, words_read, correct_count, error_count,
                 reading_accuracy, reading_sessions, points,
                 tasks_done, streak, active_days, last_active,
                 writing_accuracy, pronunciation_score,
                 writing_sessions, speaking_sessions)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, words_read, correct_count, error_count,
              new_accuracy, 1, points_earned,
              1, 1, 1, now,
              0, 0, 0, 0))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success"})


# =========================
# GET READING PROGRESS
# =========================
@progress_bp.route("/progress/reading/<int:user_id>", methods=["GET"])
def get_reading_progress(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT reading_sessions, words_read,
               correct_count, error_count, reading_accuracy
        FROM progress WHERE user_id=%s
    """, (user_id,))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return jsonify({
            "status": "success",
            "reading_sessions": 0,
            "words_read": 0,
            "correct_count": 0,
            "error_count": 0,
            "accuracy": 0,
        })

    return jsonify({
        "status": "success",
        "reading_sessions": data["reading_sessions"] or 0,
        "words_read": data["words_read"] or 0,
        "correct_count": data["correct_count"] or 0,
        "error_count": data["error_count"] or 0,
        "accuracy": level_one_display_score(data["reading_accuracy"]),
    })


# =========================
# SAVE WRITING PROGRESS
# =========================
@progress_bp.route("/progress/writing/save", methods=["POST"])
def save_writing_progress():

    data = request.json
    if not data or "user_id" not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    user_id = data["user_id"]
    word_count = data.get("word_count", 0)
    corrected_words = data.get("corrected_words", 0)
    to_fix = data.get("to_fix", 0)
    new_accuracy = safe_float(data.get("accuracy"))
    points_earned = level_one_points(new_accuracy)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today, now = _today_and_now()

    cursor.execute("SELECT * FROM progress WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        old_sessions = user["writing_sessions"] or 0
        old_accuracy = safe_float(user["writing_accuracy"])

        total_sessions = old_sessions + 1
        avg_accuracy = (old_accuracy * old_sessions + new_accuracy) / total_sessions

        streak, active_days = _calc_streak_and_days(user, today)

        cursor.execute("""
            UPDATE progress SET
                word_count = COALESCE(word_count, 0) + %s,
                corrected_words = COALESCE(corrected_words, 0) + %s,
                to_fix = COALESCE(to_fix, 0) + %s,
                writing_accuracy = %s,
                writing_sessions = COALESCE(writing_sessions, 0) + 1,
                points = COALESCE(points, 0) + %s,
                tasks_done = COALESCE(tasks_done, 0) + 1,
                streak = %s,
                active_days = %s,
                last_active = %s
            WHERE user_id = %s
        """, (word_count, corrected_words, to_fix,
              avg_accuracy, points_earned,
              streak, active_days, now, user_id))

    else:
        cursor.execute("""
            INSERT INTO progress
                (user_id, word_count, corrected_words, to_fix,
                 writing_accuracy, writing_sessions, points,
                 tasks_done, streak, active_days, last_active,
                 reading_accuracy, pronunciation_score,
                 reading_sessions, speaking_sessions)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, word_count, corrected_words, to_fix,
              new_accuracy, 1, points_earned,
              1, 1, 1, now,
              0, 0, 0, 0))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success"})


# =========================
# GET WRITING PROGRESS
# =========================
@progress_bp.route("/progress/writing/<int:user_id>", methods=["GET"])
def get_writing_progress(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT writing_sessions, word_count,
               corrected_words, to_fix, writing_accuracy
        FROM progress WHERE user_id=%s
    """, (user_id,))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return jsonify({
            "status": "success",
            "writing_sessions": 0,
            "word_count": 0,
            "corrected_words": 0,
            "to_fix": 0,
            "accuracy": 0,
        })

    return jsonify({
        "status": "success",
        "writing_sessions": data["writing_sessions"] or 0,
        "word_count": data["word_count"] or 0,
        "corrected_words": data["corrected_words"] or 0,
        "to_fix": data["to_fix"] or 0,
        "accuracy": level_one_display_score(data["writing_accuracy"]),
    })


# =========================
# SAVE SPEAKING PROGRESS
# =========================
@progress_bp.route("/progress/speaking/save", methods=["POST"])
def save_speaking_progress():

    data = request.json
    if not data or "user_id" not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    user_id = data["user_id"]
    words_spoken = data.get("words_spoken", 0)
    new_score = safe_float(data.get("pronunciation_score"))
    points_earned = level_one_points(new_score)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today, now = _today_and_now()

    cursor.execute("SELECT * FROM progress WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        old_sessions = user["speaking_sessions"] or 0
        old_score = safe_float(user["pronunciation_score"])

        total_sessions = old_sessions + 1
        avg_score = (old_score * old_sessions + new_score) / total_sessions

        streak, active_days = _calc_streak_and_days(user, today)

        cursor.execute("""
            UPDATE progress SET
                words_spoken = COALESCE(words_spoken, 0) + %s,
                pronunciation_score = %s,
                speaking_sessions = COALESCE(speaking_sessions, 0) + 1,
                points = COALESCE(points, 0) + %s,
                tasks_done = COALESCE(tasks_done, 0) + 1,
                streak = %s,
                active_days = %s,
                last_active = %s
            WHERE user_id = %s
        """, (words_spoken, avg_score, points_earned,
              streak, active_days, now, user_id))

    else:
        cursor.execute("""
            INSERT INTO progress
                (user_id, words_spoken, pronunciation_score,
                 speaking_sessions, points, tasks_done,
                 streak, active_days, last_active,
                 reading_accuracy, writing_accuracy,
                 reading_sessions, writing_sessions)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, words_spoken, new_score,
              1, points_earned, 1,
              1, 1, now,
              0, 0, 0, 0))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success"})


# =========================
# GET SPEAKING PROGRESS
# =========================
@progress_bp.route("/progress/speaking/<int:user_id>", methods=["GET"])
def get_speaking_progress(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT speaking_sessions, words_spoken, pronunciation_score
        FROM progress WHERE user_id=%s
    """, (user_id,))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return jsonify({
            "status": "success",
            "speaking_sessions": 0,
            "words_spoken": 0,
            "pronunciation_score": 0,
        })

    return jsonify({
        "status": "success",
        "speaking_sessions": data["speaking_sessions"] or 0,
        "words_spoken": data["words_spoken"] or 0,
        "pronunciation_score": level_one_display_score(data["pronunciation_score"]),
    })


# =========================
# SAVE QUIZ PROGRESS
# =========================
@progress_bp.route("/progress/quiz/save", methods=["POST"])
def save_quiz_progress():

    data = request.get_json(silent=True) or {}
    if not data or "user_id" not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    user_id = data["user_id"]
    correct = int(data.get("correct", data.get("correct_answers", data.get("quiz_correct", 0))) or 0)
    wrong = int(data.get("wrong", data.get("wrong_answers", data.get("quiz_wrong", 0))) or 0)
    total = int(data.get("total", data.get("question_count", correct + wrong)) or 0)
    raw_accuracy = data.get("accuracy", data.get("quiz_accuracy"))
    new_accuracy = safe_float(raw_accuracy)

    if raw_accuracy is None and total > 0:
        new_accuracy = (correct / total) * 100

    points_earned = level_one_points(new_accuracy)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today, now = _today_and_now()

    cursor.execute("SELECT * FROM progress WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        old_sessions = user["quiz_sessions"] or 0
        old_accuracy = safe_float(user["quiz_accuracy"])

        total_sessions = old_sessions + 1
        avg_accuracy = (old_accuracy * old_sessions + new_accuracy) / total_sessions
        streak, active_days = _calc_streak_and_days(user, today)

        cursor.execute("""
            UPDATE progress SET
                quiz_correct = COALESCE(quiz_correct, 0) + %s,
                quiz_wrong = COALESCE(quiz_wrong, 0) + %s,
                quiz_accuracy = %s,
                quiz_sessions = COALESCE(quiz_sessions, 0) + 1,
                points = COALESCE(points, 0) + %s,
                tasks_done = COALESCE(tasks_done, 0) + 1,
                streak = %s,
                active_days = %s,
                last_active = %s
            WHERE user_id = %s
        """, (correct, wrong, avg_accuracy, points_earned,
              streak, active_days, now, user_id))

    else:
        cursor.execute("""
            INSERT INTO progress
                (user_id, quiz_correct, quiz_wrong, quiz_accuracy,
                 quiz_sessions, points, tasks_done,
                 streak, active_days, last_active,
                 reading_accuracy, writing_accuracy, pronunciation_score,
                 reading_sessions, writing_sessions, speaking_sessions)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, correct, wrong, new_accuracy,
              1, points_earned, 1,
              1, 1, now,
              0, 0, 0, 0, 0, 0))

    conn.commit()

    cursor.execute("""
        SELECT quiz_sessions, quiz_correct, quiz_wrong, quiz_accuracy,
               points, tasks_done, streak, active_days, last_active
        FROM progress WHERE user_id=%s
    """, (user_id,))
    saved = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        "status": "success",
        "saved": True,
        "quiz_sessions": saved["quiz_sessions"] or 0,
        "quiz_correct": saved["quiz_correct"] or 0,
        "correct_answers": saved["quiz_correct"] or 0,
        "quiz_wrong": saved["quiz_wrong"] or 0,
        "wrong_answers": saved["quiz_wrong"] or 0,
        "accuracy": level_one_display_score(saved["quiz_accuracy"]),
        "quiz_accuracy": level_one_display_score(saved["quiz_accuracy"]),
        "points": saved["points"] or 0,
        "points_earned": points_earned,
        "tasks_done": saved["tasks_done"] or 0,
        "streak": saved["streak"] or 0,
        "active_days": saved["active_days"] or 0,
        "last_active": saved["last_active"].isoformat() if saved["last_active"] else None,
    })


# =========================
# GET QUIZ PROGRESS
# =========================
@progress_bp.route("/progress/quiz/<int:user_id>", methods=["GET"])
def get_quiz_progress(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT quiz_sessions, quiz_correct, quiz_wrong, quiz_accuracy
        FROM progress WHERE user_id=%s
    """, (user_id,))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return jsonify({
            "status": "success",
            "quiz_sessions": 0,
            "quiz_correct": 0,
            "quiz_wrong": 0,
            "accuracy": 0,
        })

    return jsonify({
        "status": "success",
        "quiz_sessions": data["quiz_sessions"] or 0,
        "quiz_correct": data["quiz_correct"] or 0,
        "correct_answers": data["quiz_correct"] or 0,
        "quiz_wrong": data["quiz_wrong"] or 0,
        "wrong_answers": data["quiz_wrong"] or 0,
        "accuracy": level_one_display_score(data["quiz_accuracy"]),
        "quiz_accuracy": level_one_display_score(data["quiz_accuracy"]),
    })


# =========================
# UPDATE PROGRESS (COMPATIBILITY)
# =========================
@progress_bp.route("/progress/update", methods=["POST"])
@progress_bp.route("/update-progress", methods=["POST"])
def update_progress():
    data = request.json or {}
    user_id = data.get("user_id")
    points = data.get("points", 0)
    tasks_done = data.get("tasks_done", 0)

    if not user_id:
        return jsonify({"status": "fail", "message": "user_id required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today, now = _today_and_now()

    cursor.execute("SELECT * FROM progress WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        streak, active_days = _calc_streak_and_days(user, today)

        cursor.execute("""
            UPDATE progress SET
                points = GREATEST(COALESCE(points, 0), %s),
                tasks_done = GREATEST(COALESCE(tasks_done, 0), %s),
                streak = %s,
                active_days = %s,
                last_active = %s
            WHERE user_id = %s
        """, (points, tasks_done, streak, active_days, now, user_id))

    else:
        cursor.execute("""
            INSERT INTO progress
                (user_id, points, streak, tasks_done, active_days, last_active)
            VALUES (%s, %s, 1, %s, 1, %s)
        """, (user_id, points, tasks_done, now))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success"})
