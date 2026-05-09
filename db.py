import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "database": "lexiaid_db",
    "user": "postgres",
    "password": "13102005"
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_cursor():
    conn = get_db_connection()
    return conn.cursor(), conn