"""Redact recognizable credential shapes before storing conversational content."""
import re
PATTERNS = [r"https://auth\.openai\.com/[^\s]+", r"\bBearer\s+[^\s]+", r"\bsk-[A-Za-z0-9_-]{12,}",
            r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"]


def redact(text):
    for pattern in PATTERNS:
        text = re.sub(pattern, "[credential redacted]", text, flags=re.IGNORECASE)
    return text
