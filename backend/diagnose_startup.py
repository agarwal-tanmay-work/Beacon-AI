import sys
import traceback

print("Attempting to import app.main...")
try:
    from app.main import app
    print("Import successful!")
except Exception:
    traceback.print_exc()
