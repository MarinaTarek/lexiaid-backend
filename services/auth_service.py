from db import cursor, conn

def register_user(name, email, password):
    cursor.execute("""
        INSERT INTO users (name, email, password, level)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (name, email, password, "beginner"))

    user_id = cursor.fetchone()[0]
    conn.commit()
    return user_id


def login_user(email, password):
    cursor.execute("""
        SELECT id, name, email, level 
        FROM users 
        WHERE email=%s AND password=%s
    """, (email, password))

    return cursor.fetchone()