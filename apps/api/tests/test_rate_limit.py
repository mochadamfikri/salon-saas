"""Redis rate limiting tests (fakeredis; no live Redis required).

The general suite disables rate limiting via an autouse fixture in conftest
(the shared TestClient IP would otherwise exhaust per-minute buckets). This
module re-enables it with a fakeredis client and covers the limiter unit
behavior plus one end-to-end 429 through the real app stack.
"""

from types import SimpleNamespace

import fakeredis
import pytest
import redis
from app.core.rate_limit import check_rate_limit, rate_limit, set_redis_client
from app.main import app
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _enable_rate_limiting(monkeypatch):
    """Re-enable rate limiting for this module with an isolated fakeredis."""
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=True, trusted_proxies=[]),
    )
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    set_redis_client(fake)
    yield
    set_redis_client(None)


def _request(ip: str = "127.0.0.1") -> Request:
    return Request({"type": "http", "client": (ip, 5000), "headers": []})


def test_check_rate_limit_allows_within_limit():
    result = check_rate_limit("rl:test:basic", limit=3, window_seconds=60)
    assert result.allowed and result.remaining == 2
    result = check_rate_limit("rl:test:basic", limit=3, window_seconds=60)
    assert result.allowed and result.remaining == 1
    result = check_rate_limit("rl:test:basic", limit=3, window_seconds=60)
    assert result.allowed and result.remaining == 0


def test_check_rate_limit_blocks_over_limit():
    for _ in range(2):
        assert check_rate_limit("rl:test:block", limit=2, window_seconds=60).allowed
    blocked = check_rate_limit("rl:test:block", limit=2, window_seconds=60)
    assert not blocked.allowed
    assert blocked.remaining == 0
    assert blocked.retry_after_seconds == 60


def test_check_rate_limit_window_resets():
    assert check_rate_limit("rl:test:window", limit=1, window_seconds=1).allowed
    assert not check_rate_limit("rl:test:window", limit=1, window_seconds=1).allowed
    import time

    time.sleep(1.1)
    assert check_rate_limit("rl:test:window", limit=1, window_seconds=1).allowed


def test_check_rate_limit_fail_open_on_redis_error():
    class BrokenRedis:
        def pipeline(self, *args, **kwargs):
            raise redis.RedisError("boom")

    set_redis_client(BrokenRedis())  # type: ignore[arg-type]
    try:
        result = check_rate_limit("rl:test:broken", limit=1, window_seconds=60)
        assert result.allowed
    finally:
        set_redis_client(fakeredis.FakeStrictRedis(decode_responses=True))


def test_rate_limit_dependency_blocks_with_429_and_headers():
    dependency = rate_limit(limit=2, window_seconds=60, prefix="dep-test")

    dependency(_request())
    dependency(_request())
    with pytest.raises(HTTPException) as exc_info:
        dependency(_request())

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert exc_info.value.headers["X-RateLimit-Limit"] == "2"
    assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_dependency_keys_by_client_ip():
    dependency = rate_limit(limit=1, window_seconds=60, prefix="dep-ip")

    dependency(_request(ip="10.0.0.1"))
    # A different IP gets its own bucket.
    dependency(_request(ip="10.0.0.2"))
    with pytest.raises(HTTPException) as exc_info:
        dependency(_request(ip="10.0.0.1"))
    assert exc_info.value.status_code == 429


def test_rate_limit_disabled_setting_bypasses(monkeypatch):
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=False, trusted_proxies=[]),
    )
    dependency = rate_limit(limit=1, window_seconds=60, prefix="dep-disabled")
    for _ in range(5):
        dependency(_request())  # no 429 despite limit=1


def test_client_ip_defaults_to_peer_when_no_trusted_proxies(monkeypatch):
    """Without trusted proxies, direct peer is used and headers are ignored."""
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=True, trusted_proxies=[]),
    )
    req = Request(
        {
            "type": "http",
            "client": ("198.51.100.1", 5000),
            "headers": [(b"x-forwarded-for", b"203.0.113.195")],
        }
    )
    from app.core.rate_limit import _client_ip

    assert _client_ip(req) == "198.51.100.1"


def test_client_ip_untrusted_peer_ignores_x_forwarded_for(monkeypatch):
    """If peer is not in trusted_proxies, X-Forwarded-For is ignored."""
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=True, trusted_proxies=["127.0.0.1"]),
    )
    req = Request(
        {
            "type": "http",
            "client": ("198.51.100.5", 5000),
            "headers": [(b"x-forwarded-for", b"203.0.113.195")],
        }
    )
    from app.core.rate_limit import _client_ip

    assert _client_ip(req) == "198.51.100.5"


def test_client_ip_trusted_peer_extracts_rightmost_forwarded_for(monkeypatch):
    """When peer is trusted, rightmost IP in X-Forwarded-For is extracted."""
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=True, trusted_proxies=["127.0.0.1"]),
    )
    req = Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 5000),
            "headers": [(b"x-forwarded-for", b"10.0.0.1, 203.0.113.50")],
        }
    )
    from app.core.rate_limit import _client_ip

    assert _client_ip(req) == "203.0.113.50"


def test_client_ip_trusted_peer_empty_header_falls_back_to_peer(monkeypatch):
    """When peer is trusted but header is missing/empty, peer IP is used."""
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=True, trusted_proxies=["127.0.0.1"]),
    )
    req = Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 5000),
            "headers": [],
        }
    )
    from app.core.rate_limit import _client_ip

    assert _client_ip(req) == "127.0.0.1"


def test_password_reset_request_rate_limited_end_to_end(db_session):
    """Hammering /auth/password-reset/request trips the 429 (limit is 5/min)."""
    for _ in range(5):
        response = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
        assert response.status_code == 200

    limited = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert limited.status_code == 429
    assert "retry-after" in {k.lower() for k in limited.headers}
