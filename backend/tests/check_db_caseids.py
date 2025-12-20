import sqlite3
import os

db_path = "backend/beacon.db"

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for reports with case_id
        cursor.execute("SELECT id, case_id FROM reports WHERE case_id IS NOT NULL LIMIT 5")
        rows = cursor.fetchall()
        
        if rows:
            print("Successfully found reports with Case IDs in database:")
            for row in rows:
                print(f"ID: {row[0]}, Case ID: {row[1]}")
        else:
            print("No reports with Case IDs found yet (waiting for a report completion).")
            
        conn.close()
    except Exception as e:
        print(f"Error reading database: {e}")
else:
    print(f"Database file not found at {db_path}")
