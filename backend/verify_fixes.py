
import sys
import os
from datetime import datetime
import pytz

# Add current dir to path to find app module
sys.path.append(os.getcwd())

try:
    from passlib.context import CryptContext
    print("Imported CryptContext")
    
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    print("Initialized CryptContext")
    
    hashed = pwd_context.hash("test-secret-key")
    print(f"Hashed: {hashed[:10]}...")
except Exception as e:
    print(f"❌ BCRYPT ERROR: {e}")
    sys.exit(1)

try:
    from app.models.beacon import Beacon
    from app.core.time_utils import get_ist_now
    
    ist_now = get_ist_now()
    print(f"IST Now (naive): {ist_now}")
    
    beacon = Beacon(
        reported_at=ist_now,
        case_id="BCN123456789012",
        evidence_files=[],
        created_at=ist_now,
        updated_at=ist_now,
        secret_key_hash=hashed,
        status="Received"
    )
    print("Beacon model instantiated successfully.")
except Exception as e:
    print(f"❌ MODEL ERROR: {e}")
    sys.exit(1)

print("✅ ALL CHECKS PASSED")
