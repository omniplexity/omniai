"""Integration tests for Redis concurrency store.

These tests verify the distributed correctness of the Redis-based concurrency store.
Run with: pytest -m integration

Requires a running Redis instance (see CI workflow for setup).
"""

import asyncio

import pytest
from backend.core.limits.factory import _redis_available, _RedisConcurrencyStore

pytestmark = pytest.mark.integration


# Skip all tests in this module if redis is not available
pytestmark = pytest.mark.skipif(
    not _redis_available,
    reason="redis package not installed"
)


@pytest.fixture
async def redis_store():
    """Create a Redis concurrency store connected to localhost:6379."""
    store = _RedisConcurrencyStore(
        redis_url="redis://localhost:6379/0",
        default_ttl_seconds=2
    )
    # Clean up any existing test keys before tests
    client = await store._get_client()
    # Delete any keys matching our test pattern
    async for key in client.scan_iter(match="omni:conc:test:*"):
        await client.delete(key)
    yield store
    # Cleanup after tests
    async for key in client.scan_iter(match="omni:conc:test:*"):
        await client.delete(key)
    await client.aclose()


class TestRedisConcurrencyStore:
    """Integration tests for _RedisConcurrencyStore."""

    @pytest.mark.asyncio
    async def test_acquire_single_slot(self, redis_store):
        """Acquiring a slot should succeed when under limit."""
        key = "test:user:1"
        limit = 3

        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)

        assert acquired is True
        assert token is not None
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_acquire_multiple_slots_up_to_limit(self, redis_store):
        """Acquiring up to limit should all succeed."""
        key = "test:user:2"
        limit = 3

        results = []
        for i in range(limit):
            acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
            results.append((acquired, token))

        assert all(r[0] for r in results)
        assert all(r[1] is not None for r in results)
        tokens = [r[1] for r in results]
        assert len(set(tokens)) == limit

    @pytest.mark.asyncio
    async def test_acquire_fails_at_limit(self, redis_store):
        """Acquiring beyond limit should fail."""
        key = "test:user:3"
        limit = 2

        for _ in range(limit):
            acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
            assert acquired is True

        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is False
        assert token is None

    @pytest.mark.asyncio
    async def test_acquire_limit_plus_one_fails(self, redis_store):
        """Acquiring limit + 1 should fail."""
        key = "test:user:4"
        limit = 3

        for _ in range(limit):
            await redis_store.acquire(key, limit=limit, ttl_s=5)

        acquired, _ = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_release_with_correct_token(self, redis_store):
        """Releasing with correct token should succeed."""
        key = "test:user:5"
        limit = 3

        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is True

        released = await redis_store.release(key, token)
        assert released is True

    @pytest.mark.asyncio
    async def test_release_with_wrong_token(self, redis_store):
        """Releasing with wrong token should return False."""
        key = "test:user:6"
        limit = 3

        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is True

        released = await redis_store.release(key, "wrong-token")
        assert released is False

        # Slot should still be occupied
        acquired2, _ = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired2 is False

    @pytest.mark.asyncio
    async def test_release_twice_returns_false(self, redis_store):
        """Releasing the same slot twice should return False on second call."""
        key = "test:user:7"
        limit = 3

        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is True

        released1 = await redis_store.release(key, token)
        assert released1 is True

        released2 = await redis_store.release(key, token)
        assert released2 is False

    @pytest.mark.asyncio
    async def test_release_nonexistent_key(self, redis_store):
        """Releasing a non-existent key should return False."""
        released = await redis_store.release("nonexistent:key", "some-token")
        assert released is False

    @pytest.mark.asyncio
    async def test_ttl_expiry_reclaims_slot(self, redis_store):
        """After TTL expiry, slot should be reclaimable."""
        key = "test:user:8"
        limit = 1
        ttl = 0.2  # 200ms TTL

        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=ttl)
        assert acquired is True

        # Wait for expiry
        await asyncio.sleep(0.5)

        # Should be able to acquire again
        acquired2, token2 = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired2 is True
        assert token2 != token

    @pytest.mark.asyncio
    async def test_ttl_expiry_simulates_crash(self, redis_store):
        """Simulate crash (no release) - TTL should reclaim slot."""
        key = "test:user:9"
        limit = 1
        ttl = 0.2

        # Acquire like normal
        acquired1, token1 = await redis_store.acquire(key, limit=limit, ttl_s=ttl)
        assert acquired1 is True

        # Simulate crash: don't release, just wait
        await asyncio.sleep(0.5)

        # Should be able to acquire (simulating new worker after crash)
        acquired2, token2 = await redis_store.acquire(key, limit=limit, ttl_s=ttl)
        assert acquired2 is True
        assert token2 != token1

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, redis_store):
        """Different keys should have independent limits."""
        key1 = "test:user:10"
        key2 = "test:user:11"
        limit = 1

        acquired1, _ = await redis_store.acquire(key1, limit=limit, ttl_s=5)
        assert acquired1 is True

        acquired2, _ = await redis_store.acquire(key2, limit=limit, ttl_s=5)
        assert acquired2 is True

        acquired3, _ = await redis_store.acquire(key1, limit=limit, ttl_s=5)
        assert acquired3 is False

    @pytest.mark.asyncio
    async def test_release_frees_slot_for_same_key(self, redis_store):
        """Releasing should free slot for same key."""
        key = "test:user:12"
        limit = 2

        acquired1, token1 = await redis_store.acquire(key, limit=limit, ttl_s=5)
        acquired2, token2 = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired1 is True
        assert acquired2 is True

        released = await redis_store.release(key, token1)
        assert released is True

        acquired3, _ = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired3 is True

    @pytest.mark.asyncio
    async def test_token_uniqueness(self, redis_store):
        """Tokens should be unique across acquisitions."""
        key = "test:user:13"
        limit = 10
        ttl = 5

        tokens = []
        for _ in range(limit):
            acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=ttl)
            assert acquired is True
            tokens.append(token)

        assert len(set(tokens)) == limit


class TestRedisConcurrencyStoreDistributed:
    """Tests for distributed/concurrent behavior across multiple workers."""

    @pytest.mark.asyncio
    async def test_concurrent_acquires_enforce_global_limit(self, redis_store):
        """Multiple concurrent acquires should respect the global limit."""
        key = "test:dist:1"
        limit = 5
        num_tasks = 20  # More than limit

        async def do_acquire():
            return await redis_store.acquire(key, limit=limit, ttl_s=10)

        # Launch many concurrent tasks
        tasks = [do_acquire() for _ in range(num_tasks)]
        results = await asyncio.gather(*tasks)

        # Exactly 'limit' should succeed
        successes = [r for r in results if r[0]]
        assert len(successes) == limit

        failures = [r for r in results if not r[0]]
        assert len(failures) == num_tasks - limit

    @pytest.mark.asyncio
    async def test_concurrent_acquires_and_releases(self, redis_store):
        """Mixed concurrent acquires and releases should maintain consistency."""
        key = "test:dist:2"
        limit = 3

        async def do_work(idx):
            """Simulate work with acquire and release."""
            acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=5)
            if acquired:
                await asyncio.sleep(0.05)  # Simulate work
                released = await redis_store.release(key, token)
                return acquired, released
            return acquired, None

        # Launch more tasks than limit
        num_tasks = 10
        tasks = [do_work(i) for i in range(num_tasks)]
        results = await asyncio.gather(*tasks)

        # All should have acquired
        for acquired, _ in results:
            assert acquired is True


class TestRedisConcurrencyStoreKeyBoundedness:
    """Tests to verify keys don't grow unbounded."""

    @pytest.mark.asyncio
    async def test_expired_slots_cleaned_on_acquire(self, redis_store):
        """Expired slots should be cleaned on each acquire."""
        key = "test:bound:1"
        limit = 3

        # Acquire with short TTL
        acquired, token = await redis_store.acquire(key, limit=limit, ttl_s=0.1)
        assert acquired is True

        # Wait for expiry
        await asyncio.sleep(0.2)

        # Get active count (should be 0 after cleanup)
        count = await redis_store.get_active_count(key)
        # The acquire should have cleaned expired entries
        # So when we acquire again, we should succeed immediately
        acquired2, _ = await redis_store.acquire(key, limit=limit, ttl_s=5)
        assert acquired2 is True

    @pytest.mark.asyncio
    async def test_zset_key_cleanup_on_all_releases(self, redis_store):
        """ZSET members should be removed on release."""
        key = "test:bound:2"

        acquired, token = await redis_store.acquire(key, limit=3, ttl_s=10)
        assert acquired is True

        # Check active count
        count1 = await redis_store.get_active_count(key)
        assert count1 == 1

        # Release
        released = await redis_store.release(key, token)
        assert released is True

        # Check active count
        count2 = await redis_store.get_active_count(key)
        assert count2 == 0


class TestRedisConcurrencyStoreLuaScript:
    """Tests for Lua script correctness."""

    @pytest.mark.asyncio
    async def test_script_reload_on_noscript_error(self, redis_store):
        """Should handle NOSCRIPT error gracefully."""
        key = "test:script:1"

        # Force a NOSCRIPT error by clearing scripts
        client = await redis_store._get_client()
        await client.script_flush()

        # Clear cached shas
        redis_store._acquire_sha = None
        redis_store._release_sha = None

        # Should still work after reload
        acquired, token = await redis_store.acquire(key, limit=3, ttl_s=5)
        assert acquired is True

        released = await redis_store.release(key, token)
        assert released is True
