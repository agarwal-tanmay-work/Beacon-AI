import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.main import app

print("Inspecting Routes:")
for route in app.routes:
    if hasattr(route, "path"):
        print(f"{route.methods} {route.path}")
