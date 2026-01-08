from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.utc

def get_ist_now() -> datetime:
    """
    Get current time in IST as a naive datetime (for user-friendly DB storage).
    Effectively: 23:30 IST -> 23:30 (No TZ).
    """
    return datetime.now(UTC).astimezone(IST).replace(tzinfo=None)

def get_utc_now() -> datetime:
    """Get current time in UTC."""
    return datetime.now(UTC)

def to_ist(dt: datetime) -> datetime:
    """Convert a datetime object to IST."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)

def format_ist(dt: datetime) -> str:
    """Format datetime as ISO string in IST."""
    if dt is None:
        return None
    return to_ist(dt).isoformat()
