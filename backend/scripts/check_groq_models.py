
import os
import sys
import requests
from pathlib import Path

# Manually load backend_config.env
env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "backend_config.env"
if env_path.exists():
    print(f"Loading env from {env_path}")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'").strip('"')

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    print("Error: GROQ_API_KEY not found.")
    sys.exit(1)

url = "https://api.groq.com/openai/v1/models"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        models = response.json().get("data", [])
        print(f"Found {len(models)} models:")
        for m in models:
            print(f" - {m['id']}")
    else:
        print(f"Error fetching models: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Exception: {e}")
