"""Phone number normalization and WhatsApp helpers."""

from __future__ import annotations

import re


def sanitize_phone_number(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def validate_phone_number(phone: str | None, *, required: bool = False) -> str:
    sanitized = sanitize_phone_number(phone)
    if not sanitized:
        if required:
            raise ValueError("Phone number is required.")
        return ""
    if len(sanitized) < 7 or len(sanitized) > 15:
        raise ValueError("Phone number must be between 7 and 15 digits.")
    return sanitized


def get_whatsapp_link(phone: str | None) -> str:
    return f"https://wa.me/{sanitize_phone_number(phone)}"
