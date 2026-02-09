"""Unit tests for concurrency store implementations.

These tests verify the core correctness of both in-memory and Redis-based
concurrency stores. Redis tests are marked with @pytest.mark.integration.
"""

import asyncio

import pytest
from backend.core.limits.memory import InMemoryConcurrencyStore


class TestInMemoryConcurrencyStore:
    """Unit tests for InMemoryConcurrencyStore."""

    @pytest.fixture
    def store(self):
        """Create a fresh store for each test."""
        return InMemoryConcurrencyStore(default_ttl_seconds=2)

    @pytest.mark.asyncio
    async def test_acquire_single_slot(self, store):
        """Acquiring a slot should succeed when under limit."""
        key = "test:user:1"
        limit = 3

        acquired, token = await store.acquire(key, limit=limit, ttl_s=5)

        assert acquired is True
        assert token is not None
        assert len(token) > 0  # Should be a hex token

    @pytest.mark.asyncio
    async def test_acquire_multiple_slots_up_to_limit(self, store):
        """Acquiring up to limit should all succeed."""
        key = "test:user:2"
        limit = 3

        results = []
        for i in range(limit):
            acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
            results.append((acquired, token))

        assert all(r[0] for r in results)
        assert all(r[1] is not None for r in results)
        # All tokens should be unique
        tokens = [r[1] for r in results]
        assert len(set(tokens)) == limit

    @pytest.mark.asyncio
    async def test_acquire_fails_at_limit(self, store):
        """Acquiring beyond limit should fail."""
        key = "test:user:3"
        limit = 2

        # Fill up the slots
        for _ in range(limit):
            acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
            assert acquired is True

        # This one should fail
        acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is False
        assert token is None

    @pytest.mark.asyncio
    async def test_acquire_limit_plus_one_fails(self, store):
        """Acquiring limit + 1 should fail."""
        key = "test:user:4"
        limit = 3

        for _ in range(limit):
            await store.acquire(key, limit=limit, ttl_s=5)

        acquired, _ = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_release_with_correct_token(self, store):
        """Releasing with correct token should succeed."""
        key = "test:user:5"
        limit = 3

        acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is True

        released = await store.release(key, token)
        assert released is True

    @pytest.mark.asyncio
    async def test_release_with_wrong_token(self, store):
        """Releasing with wrong token should return False and not affect slots."""
        key = "test:user:6"
        limit = 2

        acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is True

        # Acquire second slot
        acquired_second, _ = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired_second is True

        # Now both slots are used (limit=2), trying wrong token release
        released = await store.release(key, "wrong-token")
        assert released is False

        # Both slots should still be occupied (wrong token didn't release anything)
        acquired3, _ = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired3 is False

    @pytest.mark.asyncio
    async def test_release_twice_returns_false(self, store):
        """Releasing the same slot twice should return False on second call."""
        key = "test:user:7"
        limit = 3

        acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired is True

        released1 = await store.release(key, token)
        assert released1 is True

        released2 = await store.release(key, token)
        assert released2 is False

    @pytest.mark.asyncio
    async def test_release_nonexistent_key(self, store):
        """Releasing a non-existent key should return False."""
        released = await store.release("nonexistent:key", "some-token")
        assert released is False

    @pytest.mark.asyncio
    async def test_ttl_expiry_reclaims_slot(self, store):
        """After TTL expiry, slot should be reclaimable."""
        key = "test:user:8"
        limit = 1
        ttl = 0.1  # 100ms TTL

        # Acquire the slot
        acquired, token = await store.acquire(key, limit=limit, ttl_s=ttl)
        assert acquired is True

        # Wait for expiry
        await asyncio.sleep(0.2)

        # Should be able to acquire again
        acquired2, token2 = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired2 is True
        assert token2 != token  # New token

    @pytest.mark.asyncio
    async def test_ttl_expiry_multiple_slots(self, store):
        """Partial TTL expiry should only reclaim expired slots."""
        key = "test:user:9"
        limit = 3
        ttl_short = 0.1
        ttl_long = 10

        # Acquire 2 slots with long TTL
        acquired1, _ = await store.acquire(key, limit=limit, ttl_s=ttl_long)
        acquired2, _ = await store.acquire(key, limit=limit, ttl_s=ttl_long)
        assert acquired1 is True
        assert acquired2 is True

        # Acquire 1 slot with short TTL
        acquired3, token3 = await store.acquire(key, limit=limit, ttl_s=ttl_short)
        assert acquired3 is True

        # Wait for short TTL to expire
        await asyncio.sleep(0.2)

        # Should be able to acquire exactly one more (the expired one)
        acquired4, _ = await store.acquire(key, limit=limit, ttl_s=ttl_long)
        acquired5, _ = await store.acquire(key, limit=limit, ttl_s=ttl_long)
        assert acquired4 is True
        assert acquired5 is False  # Limit reached again

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, store):
        """Different keys should have independent limits."""
        key1 = "test:user:10"
        key2 = "test:user:11"
        limit = 1

        # Fill key1
        acquired1, _ = await store.acquire(key1, limit=limit, ttl_s=5)
        assert acquired1 is True

        # key2 should still be available
        acquired2, _ = await store.acquire(key2, limit=limit, ttl_s=5)
        assert acquired2 is True

        # key1 should still be full
        acquired3, _ = await store.acquire(key1, limit=limit, ttl_s=5)
        assert acquired3 is False

    @pytest.mark.asyncio
    async def test_release_frees_slot_for_same_key(self, store):
        """Releasing should free slot for same key."""
        key = "test:user:12"
        limit = 2

        acquired1, token1 = await store.acquire(key, limit=limit, ttl_s=5)
        acquired2, token2 = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired1 is True
        assert acquired2 is True

        # Release first slot
        released = await store.release(key, token1)
        assert released is True

        # Should be able to acquire again
        acquired3, _ = await store.acquire(key, limit=limit, ttl_s=5)
        assert acquired3 is True

    @pytest.mark.asyncio
    async def test_token_uniqueness(self, store):
        """Tokens should be unique across acquisitions."""
        key = "test:user:13"
        limit = 10
        ttl = 5

        tokens = []
        for _ in range(limit):
            acquired, token = await store.acquire(key, limit=limit, ttl_s=ttl)
            assert acquired is True
            tokens.append(token)

        # All tokens should be unique
        assert len(set(tokens)) == limit

    @pytest.mark.asyncio
    async def test_default_ttl_used(self, store):
        """When no TTL provided, default TTL should be used."""
        key = "test:user:14"

        acquired, token = await store.acquire(key, limit=1)
        assert acquired is True

        # Wait for default TTL to expire
        await asyncio.sleep(store._default_ttl + 0.1)

        # Should be able to acquire again
        acquired2, _ = await store.acquire(key, limit=1)
        assert acquired2 is True

    @pytest.mark.asyncio
    async def test_empty_cleanup_on_acquire(self, store):
        """Acquiring when no slots exist should work."""
        key = "test:user:15"

        acquired, token = await store.acquire(key, limit=1)
        assert acquired is True

        # Release
        await store.release(key, token)

        # Acquire again
        acquired2, token2 = await store.acquire(key, limit=1)
        assert acquired2 is True
        assert token2 != token


class TestInMemoryConcurrencyStoreEdgeCases:
    """Edge case tests for InMemoryConcurrencyStore."""

    @pytest.fixture
    def store(self):
        return InMemoryConcurrencyStore(default_ttl_seconds=1)

    @pytest.mark.asyncio
    async def test_very_short_ttl(self, store):
        """Should handle very short TTLs correctly."""
        key = "test:edge:1"

        acquired, token = await store.acquire(key, limit=1, ttl_s=0.01)
        assert acquired is True

        # Wait a tiny bit
        await asyncio.sleep(0.05)

        acquired2, _ = await store.acquire(key, limit=1, ttl_s=1)
        assert acquired2 is True

    @pytest.mark.asyncio
    async def test_concurrent_acquire_same_key(self, store):
        """Multiple concurrent acquires for same key should respect limit."""
        key = "test:edge:2"
        limit = 2

        async def acquire():
            return await store.acquire(key, limit=limit, ttl_s=10)

        # Launch more tasks than limit
        tasks = [acquire() for _ in range(limit + 1)]
        results = await asyncio.gather(*tasks)

        # Exactly 'limit' should succeed
        successes = [r for r in results if r[0]]
        assert len(successes) == limit

        failures = [r for r in results if not r[0]]
        assert len(failures) == 1

    @pytest.mark.asyncio
    async def test_release_allows_sequential_acquire(self, store):
        """Rapid acquire-release-acquire cycle should work."""
        key = "test:edge:3"
        limit = 1

        for _ in range(5):
            acquired, token = await store.acquire(key, limit=limit, ttl_s=5)
            assert acquired is True

            released = await store.release(key, token)
            assert released is True
