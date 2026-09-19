import pytest
from fastapi import HTTPException

from app.core.rate_limiter import check_rate_limit


async def test_rate_limit_allows_requests_under_limit(redis):
    for _ in range(3):
        await check_rate_limit(
            key="test:user",
            limit=3,
            window=60,
        )


async def test_rate_limit_blocks_requests_over_limit(redis):
    for _ in range(3):
        await check_rate_limit(
            key="test:user",
            limit=3,
            window=60,
        )

    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit(
            key="test:user",
            limit=3,
            window=60,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Слишком много запросов"


async def test_rate_limit_sets_expiration(redis):
    await check_rate_limit(
        key="test:user",
        limit=5,
        window=60,
    )

    ttl = await redis.ttl("rate_limit:test:user")

    assert 0 < ttl <= 60


async def test_rate_limit_does_not_reset_ttl_on_next_request(redis):
    await check_rate_limit(
        key="test:user",
        limit=5,
        window=60,
    )

    first_ttl = await redis.ttl("rate_limit:test:user")

    await check_rate_limit(
        key="test:user",
        limit=5,
        window=60,
    )

    second_ttl = await redis.ttl("rate_limit:test:user")

    assert second_ttl <= first_ttl


async def test_rate_limit_keys_are_independent(redis):
    await check_rate_limit(
        key="user:1",
        limit=1,
        window=60,
    )

    await check_rate_limit(
        key="user:2",
        limit=2,
        window=60,
    )

    with pytest.raises(HTTPException):
        await check_rate_limit(
            key="user:1",
            limit=1,
            window=60,
        )

    await check_rate_limit(
        key="user:2",
        limit=2,
        window=60,
    )