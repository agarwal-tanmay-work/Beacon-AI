from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp; naive values are taken to be UTC."""
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
