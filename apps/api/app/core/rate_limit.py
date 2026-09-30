"""Redis-backed fixed-window rate limiting for abuse-sensitive endpoints.

Design notes:
- Fixed window keyed ``ratelimit:{prefix}:{client_ip}``. The counter itself
  is incremented with atomic ``INCR`` (inside a MULTI/EXEC pipeline together
  with a PTTL read), so concurrent requests can never slip past the limit.
  The window expiry is (re-)armed whenever the key is observed without a TTL,
  which is idempotent under concurrency and self-heals keys left without a
  TTL by a crashed request.
- Client identity is the direct TCP peer (``request.client.host``). Deploy
  behind a trusted proxy accordingly; blindly trusting X-Forwarded-For
  would let callers spoof their bucket.
- Fail-open: if Redis is unreachable the request is allowed and a warning is
  logged. A rate limiter must not turn a Redis blip into a full outage of
  authentication endpoints. Redis health should be monitored separately.
- The limiter reads settings on every request (no import-time snapshot) so
  tests can toggle ``rate_limit_enabled`` without process restarts.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return the process Redis client, creating it from settings on first use."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def set_redis_client(client: redis.Redis | None) -> None:
    """Override the Redis client (tests use fakeredis here)."""
    global _redis_client
    _redis_client = client


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a single rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


def check_rate_limit(key: str, limit: int, window_seconds: int) -> RateLimitResult:
    """Atomically check-and-increment the fixed-window counter for ``key``.

    The INCR is atomic, so the limit cannot be slipped by concurrent requests.
    The window TTL is (re-)armed whenever the key has none, which keeps the
    implementation correct on both real Redis and fakeredis (no Lua needed).

    Returns an allowed result when Redis is unreachable (fail-open, logged).
    """
    window_ms = int(window_seconds * 1000)
    try:
        client = get_redis_client()
        pipeline = client.pipeline(transaction=True)
        pipeline.incr(key)
        pipeline.pttl(key)
        count_raw, ttl_ms_raw = pipeline.execute()
        count = int(count_raw)
        ttl_ms = int(ttl_ms_raw)
        if ttl_ms == -1:
            # No window armed (first hit, or a key leaked without TTL by a
            # crashed request): arm it now. Idempotent under concurrency.
            client.pexpire(key, window_ms)
    except redis.RedisError:
        logger.warning("Rate limiter Redis unavailable; allowing request (fail-open)")
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, retry_after_seconds=0)

    allowed = count <= limit
    remaining = max(0, limit - count)
    # Approximate: worst case the caller waits out the full window.
    retry_after = 0 if allowed else window_seconds
    return RateLimitResult(
        allowed=allowed,
        limit=limit,
        remaining=remaining,
        retry_after_seconds=retry_after,
    )


def _client_ip(request: Request) -> str:
    """Extract client IP from request, respecting trusted proxy configuration.

    **Single-proxy topology only**: This implementation is designed for a single
    trusted reverse proxy (Nginx or HAProxy) directly in front of the API. It
    extracts the rightmost IP from X-Forwarded-For, which is correct when:
    - Nginx strips any client-provided X-Forwarded-For
    - Nginx sets X-Forwarded-For to the real client IP ($remote_addr)
    - The API trusts only Nginx's internal IP

    **Not supported**: Multi-proxy chains (e.g., CDN → WAF → Nginx → API) where
    you need to traverse a known chain of proxies. For that topology, you would
    need to walk backwards from the rightmost IP, skipping known proxy IPs until
    reaching the first untrusted IP (the real client).

    SECURITY: An empty trusted_proxies list (the default) means we NEVER trust
    X-Forwarded-For, which is correct for direct-to-internet deployments and
    prevents IP spoofing. Only set trusted_proxies in production when the app
    is behind a reverse proxy that strips + rewrites X-Forwarded-For.
    """
    settings = get_settings()

    # Default: use direct TCP peer (no proxy trust).
    if request.client is None:
        return "unknown"

    peer_ip = request.client.host

    # If no trusted proxies configured, use peer IP directly (safe default).
    if not settings.trusted_proxies:
        return peer_ip

    # If peer is NOT a trusted proxy, use peer IP (don't trust its headers).
    if peer_ip not in settings.trusted_proxies:
        return peer_ip

    # Peer is trusted: parse X-Forwarded-For. Format: "client, proxy1, proxy2"
    # For single-proxy topology, rightmost IP is the real client IP.
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if not forwarded_for:
        return peer_ip  # No header set, fall back to peer

    # Take the rightmost IP (strip whitespace). This is the client IP as seen
    # by our trusted proxy (single-proxy topology only).
    ips = [ip.strip() for ip in forwarded_for.split(",")]
    return ips[-1] if ips else peer_ip


def rate_limit(
    limit: int,
    window_seconds: int = 60,
    prefix: str = "default",
    key_fn: Callable[[Request], str] = _client_ip,
):
    """FastAPI dependency factory enforcing ``limit`` requests per window.

    Raises:
        HTTPException: 429 with a Retry-After header when the limit is exceeded.
    """

    def _dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        bucket = f"ratelimit:{prefix}:{key_fn(request)}"
        result = check_rate_limit(bucket, limit, window_seconds)
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
                headers={
                    "Retry-After": str(result.retry_after_seconds),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                },
            )

    return _dependency
