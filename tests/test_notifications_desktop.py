from unittest.mock import MagicMock, patch

from content_engine.notifications.desktop import send_desktop_notification


def test_send_desktop_notification_success():
    fake_toast = MagicMock()
    with patch.dict("sys.modules", {"win11toast": MagicMock(toast=fake_toast)}):
        result = send_desktop_notification("Title", "Body")

    assert result is True
    fake_toast.assert_called_once_with("Title", "Body")


def test_send_desktop_notification_never_raises_on_failure():
    broken_module = MagicMock()
    broken_module.toast.side_effect = RuntimeError("no WinRT runtime")
    with patch.dict("sys.modules", {"win11toast": broken_module}):
        result = send_desktop_notification("Title", "Body")

    assert result is False


def test_send_desktop_notification_never_raises_on_missing_library():
    with patch.dict("sys.modules", {"win11toast": None}):
        result = send_desktop_notification("Title", "Body")

    assert result is False
