from db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash


def register_user(name, email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)

    cursor.execute("""
        INSERT INTO users (name, email, password, level, is_verified)
        VALUES (%s, %s, %s, %s, FALSE)
        RETURNING id
    """, (name, email, password_hash, "beginner"))

    user_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return user_id


def login_user(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, level, password, COALESCE(is_verified, FALSE)
        FROM users 
        WHERE LOWER(email)=LOWER(%s)
    """, (email,))

    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return None, "invalid_credentials"

    user_id, name, user_email, level, stored_password, is_verified = user

    if not is_verified:
        cursor.close()
        conn.close()
        return None, "email_not_verified"

    password_ok = check_password_hash(stored_password, password)
    needs_hash_migration = False

    if not password_ok and stored_password == password:
        password_ok = True
        needs_hash_migration = True

    if not password_ok:
        cursor.close()
        conn.close()
        return None, "invalid_credentials"

    if needs_hash_migration:
        cursor.execute(
            "UPDATE users SET password=%s WHERE id=%s",
            (generate_password_hash(password), user_id)
        )
        conn.commit()

    cursor.close()
    conn.close()
    return (user_id, name, user_email, level), None
