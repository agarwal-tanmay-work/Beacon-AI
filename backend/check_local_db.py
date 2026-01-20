
import sqlite3
import os

DB_PATH = "backend/local_staging.db"

def check_local_db():
    if not os.path.exists(DB_PATH):
        print(f"Local DB not found at {DB_PATH}")
        return

    print(f"Connecting to {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check Beacon count
        try:
            cursor.execute("SELECT count(*) FROM beacon")
            count = cursor.fetchone()[0]
            print(f"Local Beacon Count: {count}")
        except Exception as e:
            print(f"Error checking beacon: {e}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_local_db()
