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
    if request.client is not None:
        return request.client.host
    return "unknown"


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
