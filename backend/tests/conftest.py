from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.assistant import Reply
from app.config import Settings
from app.main import create_app

PASSWORD = "correct horse"


class FakeClaude:
    """Stands in for anthropic.Anthropic: records calls and returns a prepared reply or raises."""

    def __init__(self, reply: Reply | None = None, error: Exception | None = None, stop_reason: str = "end_turn"):
        self.reply, self.error, self.stop_reason = reply, error, stop_reason
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=self.reply)


class FakeWebhook:
    """Records webhook posts and answers with a scripted list of results (an int status or an exception)."""

    def __init__(self, script=None):
        self.script = list(script or [200])
        self.posts: list[tuple[str, dict]] = []
        self.sleeps: list[float] = []

    def __call__(self, url, payload):
        self.posts.append((url, payload))
        result = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(result, Exception):
            raise result
        if isinstance(result, tuple):
            return result
        return result, None

    def sleep(self, seconds):
        self.sleeps.append(seconds)


@pytest.fixture
def settings():
    return Settings(
        database_url="sqlite://",
        admin_password=PASSWORD,
        secret="test-secret",
        notify_webhook_url="https://hooks.example.com/secret-token",
        notify_attempts=3,
        notify_backoff_seconds=1.0,
        seed_demo=True,
    )


@pytest.fixture
def webhook():
    return FakeWebhook()


@pytest.fixture
def make_client(settings, webhook):
    def _make(claude=None, **overrides):
        app = create_app(replace(settings, **overrides), anthropic_client=claude, transport=webhook, sleep=webhook.sleep)
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def admin(client):
    token = client.post("/api/admin/login", json={"password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


LEAD = {
    "name": "Sam Patel",
    "contact": "sam@example.com",
    "reason": "I would like to book a check-up, ideally next week.",
    "consent": True,
}
