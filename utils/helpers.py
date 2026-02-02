# Helper utilities
from datetime import datetime
from typing import Any


def format_datetime(dt_string: str) -> str:
    """Format datetime string"""
    if not dt_string:
        return "N/A"

    try:
        if 'T' in dt_string:
            dt = datetime.fromisoformat(dt_string.replace('Z', ''))
            return dt.strftime('%Y-%m-%d %H:%M')
        return dt_string[:19]
    except:
        return dt_string


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default