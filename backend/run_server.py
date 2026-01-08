import sys
import os
import uvicorn

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        print("Starting uvicorn server...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
    except Exception as e:
        print(f"Failed to start server: {e}")
