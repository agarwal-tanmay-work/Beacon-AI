import sys
import os
import uvicorn

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8000))
        print(f"Starting uvicorn server on port {port}...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
    except Exception as e:
        print(f"Failed to start server: {e}")
