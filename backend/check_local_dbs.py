
import sqlite3
import os

DB_PATHS = ["backend/local_staging.db", "backend/beacon.db"]

def check_db(path):
    if not os.path.exists(path):
        print(f"DB not found at {path}")
        return

    print(f"Connecting to {path}...")
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT count(*) FROM beacon")
            count = cursor.fetchone()[0]
            print(f"[{path}] Beacon Count: {count}")
        except Exception as e:
            print(f"[{path}] Error checking beacon: {e}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    for p in DB_PATHS:
        check_db(p)
