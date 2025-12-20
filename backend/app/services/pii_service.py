import re
from typing import List

class PIIRedactor:
    """
    Deterministic Regex-based PII Scrubber.
    Removes: Emails, Phones, IPs, Credit Cards, SSN-like patterns.
    """
    
    PATTERNS = {
        'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'PHONE': r'\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
        'IP_ADDRESS': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        'CREDIT_CARD': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'SSN_US': r'\b\d{3}-\d{2}-\d{4}\b',
        # Generic ID patterns (e.g. 5+ digits) could be dangerous to scrub globally, 
        # protecting specific structured IDs is safer.
    }

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text:
            return ""
            
        redacted_text = text
        for label, pattern in cls.PATTERNS.items():
            replacement = f"[{label}_REDACTED]"
            redacted_text = re.sub(pattern, replacement, redacted_text)
            
        return redacted_text
