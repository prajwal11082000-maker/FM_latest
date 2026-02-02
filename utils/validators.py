# Input validators
import re
from typing import Optional


def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_device_id(device_id: str) -> bool:
    """Validate device ID format"""
    if not device_id:
        return False

    # Allow alphanumeric and underscores, 3-20 characters
    pattern = r'^[a-zA-Z0-9_]{3,20}$'
    return re.match(pattern, device_id) is not None


def validate_required_field(value: str) -> bool:
    """Validate required field is not empty"""
    return bool(value and value.strip())