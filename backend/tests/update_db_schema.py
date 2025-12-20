import sqlite3
import os

db_path = "backend/beacon.db"

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if case_id column exists
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "case_id" not in columns:
            print("Adding case_id column to reports table...")
            cursor.execute("ALTER TABLE reports ADD COLUMN case_id VARCHAR(15)")
            # Add index
            cursor.execute("CREATE INDEX ix_reports_case_id ON reports (case_id)")
            conn.commit()
            print("Successfully added case_id column and index.")
        else:
            print("case_id column already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Error updating database: {e}")
else:
    print(f"Database file not found at {db_path}")
