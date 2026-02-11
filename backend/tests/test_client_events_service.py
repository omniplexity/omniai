from backend.services.client_events import (
    resolve_effective_sample_rate,
    sample_events,
)


def test_resolve_effective_sample_rate_caps_client():
    rate = resolve_effective_sample_rate(
        client_reported_rate=1.0,
        max_sample_rate=0.1,
        force_sample_rate=None,
    )
    assert rate == 0.1


def test_resolve_effective_sample_rate_force_wins():
    rate = resolve_effective_sample_rate(
        client_reported_rate=1.0,
        max_sample_rate=0.5,
        force_sample_rate=0.02,
    )
    assert rate == 0.02


def test_hash_sampling_is_deterministic():
    events = [{"type": "run_start", "run_id": f"r{i}", "ts": f"2026-01-01T00:00:{i:02d}Z"} for i in range(100)]
    accepted_a, dropped_a = sample_events(
        user_id="u1",
        events=events,
        effective_sample_rate=0.2,
        sampling_mode="hash",
    )
    accepted_b, dropped_b = sample_events(
        user_id="u1",
        events=events,
        effective_sample_rate=0.2,
        sampling_mode="hash",
    )
    assert dropped_a == dropped_b
    assert accepted_a == accepted_b

