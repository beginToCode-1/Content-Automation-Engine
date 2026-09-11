import logging

logger = logging.getLogger("content_engine.notifications.desktop")


def send_desktop_notification(title: str, message: str) -> bool:
    """Fires a native Windows toast. Never raises - any failure (missing library,
    no WinRT runtime, etc.) is caught and logged, returning False."""
    try:
        from win11toast import toast

        toast(title, message)
        return True
    except Exception:
        logger.exception("Failed to send desktop notification")
        return False
