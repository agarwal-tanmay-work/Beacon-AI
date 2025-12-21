import urllib.request
import json
import uuid
import mimetypes

API_URL = "http://localhost:8000/api/v1/public"

def create_report():
    url = f"{API_URL}/reports/create"
    data = {
        "client_seed": uuid.uuid4().hex
    }
    jsondata = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=jsondata, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"Create Report Failed: {e.code}")
        print(e.read().decode())
        return None

def upload_evidence(report_id, access_token):
    url = f"{API_URL}/evidence/upload"
    boundary = uuid.uuid4().hex
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    }
    
    file_content = b"Fake content for testing upload."
    filename = "test_evidence.txt"
    
    # Multipart body
    parts = []
    
    # report_id
    parts.append(f'--{boundary}'.encode())
    parts.append(f'Content-Disposition: form-data; name="report_id"'.encode())
    parts.append(b'')
    parts.append(report_id.encode())
    
    # access_token
    parts.append(f'--{boundary}'.encode())
    parts.append(f'Content-Disposition: form-data; name="access_token"'.encode())
    parts.append(b'')
    parts.append(access_token.encode())
    
    # file
    parts.append(f'--{boundary}'.encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    parts.append('Content-Type: text/plain'.encode())
    parts.append(b'')
    parts.append(file_content)
    
    parts.append(f'--{boundary}--'.encode())
    
    body = b'\r\n'.join(parts)
    
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Upload Success: {response.status}")
            print(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Upload Failed: {e.code}")
        print(e.read().decode())

if __name__ == "__main__":
    print("Creating report...")
    report_data = create_report()
    if report_data:
        rid = report_data['report_id']
        token = report_data['access_token']
        print(f"Report Created. ID: {rid}, Token: {token}")
        print("Uploading evidence...")
        upload_evidence(rid, token)
    else:
        print("Could not create report.")
