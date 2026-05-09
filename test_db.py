import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database="lexiaid_db",
        user="postgres",
        password="13102005"
    )
    cursor = conn.cursor()
    print("Connection successful")
    
    cursor.execute("SELECT * FROM users LIMIT 1")
    colnames = [desc[0] for desc in cursor.description]
    print(f"Columns: {colnames}")
    users = cursor.fetchall()
    for u in users:
        print(u)
        
    cursor.execute("SELECT * FROM progress")
    prog = cursor.fetchall()
    print(f"Progress entries: {len(prog)}")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
