from __future__ import annotations

import pytest

from jobify_api.rate_limit import RateLimitExceededError, RedisRateLimiter


class FakeRedis:
    def __init__(self, responses: list[list[int]]) -> None:
        self.responses = responses

    async def eval(self, *_args: object) -> list[int]:
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_rate_limiter_returns_remaining_capacity() -> None:
    limiter = RedisRateLimiter(FakeRedis([[2, 42]]))
    assert await limiter.hit(key="google:ip", limit=10, window_seconds=60) == 8


@pytest.mark.asyncio
async def test_rate_limiter_raises_with_retry_after() -> None:
    limiter = RedisRateLimiter(FakeRedis([[11, 37]]))
    with pytest.raises(RateLimitExceededError) as raised:
        await limiter.hit(key="google:ip", limit=10, window_seconds=60)
    assert raised.value.retry_after == 37
