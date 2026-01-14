
import urllib.request
import json
import time
import sqlite3
import os
import uuid

BASE_URL = "http://localhost:8000/api/v1/public/reports"
DB_PATH = "local_staging.db"
DUMMY_AUDIO = "test_audio.mp3"

def post_json(url, data):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.getcode(), json.loads(response.read().decode('utf-8'))

def create_dummy_audio():
    with open(DUMMY_AUDIO, "wb") as f:
        f.write(b"\xFF\xFB\x90\x44" * 1000) # Fake MP3 frame headers
    print(f"[SETUP] Created {DUMMY_AUDIO}")
    return os.path.abspath(DUMMY_AUDIO)

def inject_evidence(report_id, file_path):
    print(f"[SETUP] Injecting evidence for {report_id}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    ev_id = str(uuid.uuid4())
    # Schema: id, session_id, file_path, file_name, mime_type, size, uploaded_at
    cursor.execute("""
        INSERT INTO local_evidence (id, session_id, file_path, file_name, mime_type, size_bytes, file_hash, is_pii_cleansed, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
    """, (ev_id, report_id, file_path, "test_audio.mp3", "audio/mpeg", 4000, "dummy_hash"))
    
    conn.commit()
    conn.close()
    print("[SETUP] Evidence injected.")

def test_flow():
    # 1. Create Report
    print("[TEST] Creating Report...")
    code, data = post_json(f"{BASE_URL}/create", {"client_seed": "audio_test"})
    report_id = data["report_id"]
    token = data["access_token"]
    print(f"[TEST] Report ID: {report_id}")
    
    # 2. Setup Evidence
    audio_path = create_dummy_audio()
    inject_evidence(report_id, audio_path)
    
    # 3. Message (Triggers Analysis)
    print("[TEST] Sending Message (Expect Audio Analysis)...")
    start = time.time()
    try:
        code, resp = post_json(f"{BASE_URL}/message", {
            "report_id": report_id,
            "access_token": token,
            "content": "Uploading proof."
        })
        duration = time.time() - start
        print(f"[TEST] Message Result: {code} (Time: {duration:.2f}s)")
        print(f"[TEST] Body: {resp}")
    except Exception as e:
        print(f"[TEST] FAILED: {e}")

if __name__ == "__main__":
    test_flow()
