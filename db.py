import psycopg2
conn = psycopg2.connect(
    host="localhost",
    database="lexiaid_db",
    user="postgres",
    password="13102005"
)

cursor = conn.cursor()