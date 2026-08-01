"""
agents/tools/time_utils.py

Time-aware utility for injecting current date/time into agent prompts.
"""
from datetime import datetime
from zoneinfo import ZoneInfo


def get_current_time_str(user_tz: str = None) -> str:
    """Format current date and time localized to user's timezone if provided."""
    if user_tz:
        try:
            tz = ZoneInfo(user_tz)
            now = datetime.now(tz)
            return f"{now.strftime('%A, %B %d, %Y %H:%M:%S')} ({user_tz} Time)"
        except Exception:
            pass

    now = datetime.now()
    return f"{now.strftime('%A, %B %d, %Y %H:%M:%S')}"
