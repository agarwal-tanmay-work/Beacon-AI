
import urllib.request
import urllib.parse
import json
import os
import mimetypes

BASE_URL = "http://localhost:8000/api/v1/public"
IMAGE_PATH = r"C:/Users/priya/.gemini/antigravity/brain/38bf0767-ac56-477f-ba28-b22e254b0acc/uploaded_image_1768419246911.jpg"

def post_json(url, data_dict):
    data_bytes = json.dumps(data_dict).encode('utf-8')
    req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json', 'User-Agent': 'TestScript'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def upload_file(url, file_path, fields):
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    data = []
    
    # Fields
    for k, v in fields.items():
        data.append(f'--{boundary}')
        data.append(f'Content-Disposition: form-data; name="{k}"')
        data.append('')
        data.append(v)
        
    # File
    filename = os.path.basename(file_path)
    mime = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
        
    data.append(f'--{boundary}')
    data.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
    data.append(f'Content-Type: {mime}')
    data.append('')
    # We need to append bytes, so we can't just join strings easily here without care
    # Simplified approach: build bytearray
    
    body = bytearray()
    for item in data:
        body.extend(str(item).encode('utf-8'))
        body.extend(b'\r\n')
    
    body.extend(file_bytes)
    body.extend(b'\r\n')
    body.extend(f'--{boundary}--'.encode('utf-8'))
    body.extend(b'\r\n')
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    req.add_header('User-Agent', 'TestScript')
    
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode()
    except urllib.error.HTTPError as e:
        print(f"Upload HTTP Error {e.code}: {e.read().decode()}")
        return e.code
    except Exception as e:
        print(f"Upload Error: {e}")
        return 500

def run_chat():
    print("\n[1] Creating Session...")
    res = post_json(f"{BASE_URL}/reports/create", {"client_seed": "test-123"})
    if not res: return
    
    report_id = res["report_id"]
    token = res["access_token"]
    print(f"Session Created: {report_id}")
    
    def send_msg(content):
        print(f"\n[USER]: {content}")
        resp = post_json(f"{BASE_URL}/reports/message", {
            "report_id": report_id,
            "access_token": token,
            "content": content
        })
        if not resp: return ""
        sys_msg = resp["content"]
        # Clean formatting
        sys_formatted = sys_msg.replace("\n\n", "\n").strip()
        print(f"[AI]: {sys_formatted}")
        return sys_formatted

    # 2. Chat Flow
    send_msg("hi")
    
    send_msg("hi, I for police officer came to my house about a verification and they demanded 5000 rupees to fix the fee.")
    
    send_msg("master's union said 25 Gurugram")
    
    print("\n--- TEST: Sending Date Only ---")
    reply = send_msg("12th January 2026")
    
    lower_rep = reply.lower()
    if "time" in lower_rep and "date" not in lower_rep:
            print(">>> PASS: System specifically asked for TIME.")
    elif "time" in lower_rep and "date" in lower_rep:
            # Check if it emphasizes "Time" or asks for "Date AND Time"
            if "provide the **Time**" in reply:
                 print(">>> PASS: System specifically asked for TIME (despite mentioning Date elsewhere).")
            else:
                 print(">>> WARNING: System asked for Date AND Time (Validation might be loose).")
    else:
            print(">>> FAIL: System did not ask for Time.")

    send_msg("2:00 PM")
    
    # 3. Upload
    print("\n--- TEST: Evidence Upload ---")
    if os.path.exists(IMAGE_PATH):
        print(f"Uploading file: {IMAGE_PATH}")
        code = upload_file(f"{BASE_URL}/evidence/upload", IMAGE_PATH, {'report_id': report_id, 'access_token': token})
        print(f"Upload Status: {code}")
        
        reply = send_msg("I have uploaded the photo.")
        
        lower_rep = reply.lower()
        if "location" in lower_rep or "city" in lower_rep:
            print(">>> FAIL: System Regressed to asking Location/City.")
        else:
            print(">>> PASS: System acknowledged Evidence without regression.")
            # Check if it's asking for finalization or anything else
            print(f">>> Current AI State seems valid: '{reply[:50]}...'")
    else:
        print("Image not found.")

if __name__ == "__main__":
    run_chat()
