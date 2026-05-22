import re


def normalize_phone(phone: str) -> str:
    normalized = re.sub(r"[^\d+]", "", (phone or "").strip())
    if not normalized:
        raise ValueError("Mobile number is required.")
    return normalized
