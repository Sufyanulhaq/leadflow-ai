import httpx
from sqlalchemy.orm import Session

from app.models import Delivery, Lead, utcnow
from app.notify import build_payload, deliver_lead, webhook_url_allowed
from app.security import RateLimiter, password_matches, sign_token, verify_token

from .conftest import FakeWebhook

URL = "https://hooks.example.com/secret-token"


def test_token_roundtrip_expiry_and_tamper():
    token = sign_token("s", ttl=60, now=1000)
    assert verify_token("s", token, now=1010)
    assert not verify_token("s", token, now=1100)  # expired
    assert not verify_token("other", token, now=1010)  # wrong secret
    payload, signature = token.split(".")
    assert not verify_token("s", payload + "." + signature[:-2] + "aa", now=1010)
    assert not verify_token("s", "garbage", now=1010)


def test_password_matches_is_exact_and_off_when_unset():
    assert password_matches("pw", "pw")
    assert not password_matches("pw ", "pw")
    assert not password_matches("", "")


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert all(limiter.allow("k", 3, 60) for _ in range(3))
    assert not limiter.allow("k", 3, 60)
    assert limiter.allow("other", 3, 60)
    now[0] = 61
    assert limiter.allow("k", 3, 60)


def test_webhook_url_rules():
    assert webhook_url_allowed("https://hooks.slack.com/services/x")
    assert webhook_url_allowed("http://localhost:9000/hook")
    assert not webhook_url_allowed("http://example.com/hook")
    assert not webhook_url_allowed("file:///etc/passwd")
    assert not webhook_url_allowed("")


def make_lead(engine_session: Session) -> int:
    lead = Lead(
        name="Sam <Patel>",
        contact="sam@example.com",
        reason="Book a check-up",
        consent_at=utcnow(),
        category="Dental",
        priority="medium",
        score=60,
        summary="Book a check-up & clean",
        preferred_time="Tue <am>",
    )
    lead.delivery = Delivery()
    engine_session.add(lead)
    engine_session.commit()
    return lead.id


def run(client, script, attempts=3, url=URL):
    webhook = FakeWebhook(script)
    with Session(client.app.state.engine) as session:
        lead_id = make_lead(session)
        delivery = deliver_lead(
            session, lead_id, webhook_url=url, attempts=attempts, backoff=1.0, transport=webhook, sleep=webhook.sleep
        )
        return delivery.status, delivery.attempts, delivery.last_error, webhook


def test_payload_escapes_slack_markup(client):
    with Session(client.app.state.engine) as session:
        lead = session.get(Lead, make_lead(session))
        text = build_payload(lead)["text"]
    assert "&lt;Patel&gt;" in text and "&amp;" in text and "<" not in text.replace("&lt;", "")


def test_success_first_time(client):
    status, attempts, error, webhook = run(client, [200])
    assert (status, attempts, error) == ("sent", 1, None)
    assert webhook.sleeps == []


def test_retries_5xx_and_network_errors_with_doubling_delay(client):
    status, attempts, _, webhook = run(
        client, [503, httpx.ConnectError("no route to https://hooks.example.com/secret-token"), 200]
    )
    assert (status, attempts) == ("sent", 3)
    assert webhook.sleeps == [1.0, 2.0]


def test_honours_retry_after_but_caps_it(client):
    _, _, _, webhook = run(client, [(429, "7"), (429, "9999"), 200])
    assert webhook.sleeps == [7.0, 30.0]


def test_gives_up_after_the_last_attempt_and_never_logs_the_url(client):
    status, attempts, error, webhook = run(client, [httpx.ConnectError("secret-token leaked here")])
    assert (status, attempts) == ("failed", 3)
    assert error == "Network error (ConnectError)" and "secret" not in error


def test_other_4xx_stops_immediately(client):
    status, attempts, error, webhook = run(client, [404, 200])
    assert (status, attempts) == ("failed", 1)
    assert "404" in error and webhook.sleeps == []


def test_redirect_is_a_failure_not_followed(client):
    status, attempts, _, _ = run(client, [302, 200])
    assert (status, attempts) == ("failed", 1)


def test_skipped_without_a_valid_webhook(client):
    assert run(client, [200], url="")[0] == "skipped"
    status, _, error, webhook = run(client, [200], url="http://example.com/hook")
    assert status == "skipped" and "https" in error and webhook.posts == []
