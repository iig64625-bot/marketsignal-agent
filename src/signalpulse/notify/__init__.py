"""Notification module: send pipeline results to Feishu / email / webhook."""
from __future__ import annotations

from signalpulse.notify.base import Notification, NotifyMessage
from signalpulse.notify.feishu import FeishuWebhook
from signalpulse.notify.email_sender import EmailSender


__all__ = [
    "Notification",
    "NotifyMessage",
    "FeishuWebhook",
    "EmailSender",
    "build_notifier",
]


def build_notifier():
    """Return the first available notifier based on settings.

    Priority: feishu > email. Returns None if neither is configured.
    """
    from signalpulse.config.settings import get_settings

    s = get_settings()
    if s.feishu_webhook_url:
        return FeishuWebhook(s.feishu_webhook_url, secret=s.feishu_webhook_secret)
    if s.smtp_host and s.notify_to_emails:
        return EmailSender(
            host=s.smtp_host,
            port=s.smtp_port,
            user=s.smtp_user,
            password=s.smtp_password,
            to_emails=[e.strip() for e in s.notify_to_emails.split(",") if e.strip()],
            from_email=s.notify_from_email or s.smtp_user,
        )
    return None
