"""Tests for signalpulse.notify (Feishu + Email + factory)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock

import pytest

from signalpulse.notify.base import Notification, NotifyMessage
from signalpulse.notify.email_sender import EmailSender
from signalpulse.notify.feishu import FeishuWebhook


# ---- FeishuWebhook: signature ----

def test_feishu_sign_uses_base64():
    """Feishu signature must be base64-encoded HMAC-SHA256, NOT hex."""
    secret = "test-secret"
    ts = "1700000000"
    sig = FeishuWebhook._sign(secret, ts)
    decoded = base64.b64decode(sig)
    assert len(decoded) == 32
    expected = hmac.new(f"{ts}\n{secret}".encode("utf-8"), digestmod=hashlib.sha256).digest()
    assert decoded == expected
    assert len(sig) != 64 or not all(c in "0123456789abcdef" for c in sig)


def test_feishu_name():
    """FeishuWebhook.name() == 'feishu'."""
    f = FeishuWebhook(webhook_url="https://x", secret="s")
    assert f.name() == "feishu"


# ---- FeishuWebhook: send (mock HTTP at feishu module level) ----

def _make_urlopen_mock(captured: dict, body: bytes = b'{"code":0,"msg":"ok"}',
                       http_status: int = 200):
    """Build a fake urlopen compatible with ``with urlopen(...) as resp:``.

    The feishu send() reads ``resp.status`` and ``resp.read()`` after the
    ``with`` block, so we have to set ``status`` on the returned mock.
    """
    def fake(req, **kw):
        captured["url"] = req.full_url
        captured["data"] = json.loads(req.data.decode("utf-8"))
        resp = MagicMock()
        resp.status = http_status
        resp.read.return_value = body
        # Make the mock work as a context manager
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        return resp
    return fake


def test_feishu_send_success_no_secret(monkeypatch):
    """Successful send without secret (no signature header)."""
    captured = {}
    monkeypatch.setattr(
        "signalpulse.notify.feishu.urllib.request.urlopen",
        _make_urlopen_mock(captured, http_status=200,
                           body=b'{"code":0,"msg":"ok"}'),
    )
    f = FeishuWebhook(webhook_url="https://example.com/hook", secret="")
    msg = NotifyMessage(subject="S", body="B", status="completed", target="T", run_id="r1")
    assert f.send(msg) is True
    assert captured["url"] == "https://example.com/hook"
    assert captured["data"]["msg_type"] == "interactive"


def test_feishu_send_with_signature(monkeypatch):
    """When secret is set, payload contains timestamp + sign."""
    captured = {}
    monkeypatch.setattr(
        "signalpulse.notify.feishu.urllib.request.urlopen",
        _make_urlopen_mock(captured, http_status=200,
                           body=b'{"code":0,"msg":"ok"}'),
    )
    f = FeishuWebhook(webhook_url="https://x", secret="mysecret")
    f.send(NotifyMessage(subject="S", body="B", status="completed", target="T", run_id="r1"))
    assert "timestamp" in captured["data"]
    assert "sign" in captured["data"]
    assert len(captured["data"]["sign"]) > 0


def test_feishu_send_rejected_code(monkeypatch):
    """Server returning non-zero code -> send returns False."""
    captured = {}
    monkeypatch.setattr(
        "signalpulse.notify.feishu.urllib.request.urlopen",
        _make_urlopen_mock(captured, http_status=200,
                           body=b'{"code":19021,"msg":"sign fail"}'),
    )
    f = FeishuWebhook(webhook_url="https://x", secret="s")
    assert f.send(NotifyMessage(subject="S", body="B", status="completed", target="T")) is False


def test_feishu_send_http_error(monkeypatch):
    """HTTP 500 -> send returns False."""
    captured = {}
    monkeypatch.setattr(
        "signalpulse.notify.feishu.urllib.request.urlopen",
        _make_urlopen_mock(captured, http_status=500, body=b"server error"),
    )
    f = FeishuWebhook(webhook_url="https://x", secret="s")
    assert f.send(NotifyMessage(subject="S", body="B", status="completed", target="T")) is False


# ---- EmailSender ----

def test_email_sender_name():
    e = EmailSender(host="smtp.example.com", port=587, user="u", password="p",
                    to_emails=["a@b.com"], from_email="from@b.com")
    assert e.name() == "email"


def test_email_sender_send_calls_smtp(monkeypatch):
    """EmailSender.send opens SMTP, calls starttls/login/sendmail, returns True."""
    sent = {}
    class FakeSMTP:
        def __init__(self, host, port, **kw):
            sent["host"] = host; sent["port"] = port
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, **kw): sent["starttls"] = True
        def login(self, user, pw): sent["login"] = (user, pw)
        def sendmail(self, from_addr, to_addrs, msg_str):
            sent["sendmail"] = (from_addr, tuple(to_addrs), msg_str[:60])
    # email_sender.py does ``import smtplib`` at module level, so the
    # attribute lives on the email_sender module.
    monkeypatch.setattr("signalpulse.notify.email_sender.smtplib.SMTP", FakeSMTP)
    e = EmailSender(host="smtp.x", port=587, user="u", password="p",
                    to_emails=["a@b.com"], from_email="from@b.com")
    msg = NotifyMessage(subject="S", body="B", status="completed", target="T", run_id="r1")
    assert e.send(msg) is True
    assert sent["host"] == "smtp.x"
    assert sent["starttls"] is True
    assert sent["login"] == ("u", "p")
    assert sent["sendmail"][0] == "from@b.com"
    assert sent["sendmail"][1] == ("a@b.com",)


# ---- build_notifier factory ----

def test_build_notifier_returns_none_when_unconfigured(monkeypatch):
    """No webhook, no SMTP -> None.

    pydantic-settings reads from .env file by default, so deleting the
    process env is not enough. We patch ``get_settings`` directly with a
    simple namespace that has empty notify fields.
    """
    from signalpulse.notify import build_notifier
    from types import SimpleNamespace
    fake_settings = SimpleNamespace(
        feishu_webhook_url="",
        feishu_webhook_secret="",
        smtp_host="",
        smtp_user="",
        smtp_password="",
        smtp_port=587,
        notify_to_emails="",
        notify_from_email="",
    )
    monkeypatch.setattr("signalpulse.config.settings.get_settings", lambda: fake_settings)
    result = build_notifier()
    assert result is None


def test_build_notifier_returns_feishu_when_configured(monkeypatch):
    """If FEISHU_WEBHOOK_URL is set, returns a FeishuWebhook.

    Mock ``get_settings`` to avoid pydantic-settings auto-loading the .env.
    """
    from signalpulse.notify import build_notifier
    from types import SimpleNamespace
    fake_settings = SimpleNamespace(
        feishu_webhook_url="https://x",
        feishu_webhook_secret="s",
        smtp_host="",
        smtp_user="",
        smtp_password="",
        smtp_port=587,
        notify_to_emails="",
        notify_from_email="",
    )
    monkeypatch.setattr("signalpulse.config.settings.get_settings", lambda: fake_settings)
    result = build_notifier()
    assert isinstance(result, FeishuWebhook)
    assert result.webhook_url == "https://x"


def test_build_notifier_returns_feishu_when_configured(monkeypatch):
    """If FEISHU_WEBHOOK_URL is set, returns a FeishuWebhook."""
    from signalpulse.notify import build_notifier
    from signalpulse.config.settings import get_settings
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://x")
    monkeypatch.setenv("FEISHU_WEBHOOK_SECRET", "s")
    get_settings.cache_clear()
    try:
        result = build_notifier()
        assert isinstance(result, FeishuWebhook)
        assert result.webhook_url == "https://x"
    finally:
        get_settings.cache_clear()