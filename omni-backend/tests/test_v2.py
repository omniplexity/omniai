"""V2 SSE + EventBus + RunService tests."""
import asyncio
import json
import os
os.environ["OMNI_V2_DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["OMNI_ENV"] = "dev"
os.environ["OMNI_SSE_HEARTBEAT_SECONDS"] = "0.3"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from omni_backend.app import create_app
from omni_backend.v2.services.run_service import RunService, parse_cursor
from omni_backend.v2.core.eventbus import MemoryEventBus, BusEvent
from omni_backend.v2.db.session import make_engine, make_session_factory
from omni_backend.v2.db.models import Base


# ── fixtures ──

@pytest_asyncio.fixture
async def app_and_client():
    app = create_app()
    await app.router.startup()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c
    await app.router.shutdown()


@pytest_asyncio.fixture
async def run_svc():
    engine = make_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = make_session_factory(engine)
    svc = RunService(sf)
    yield svc
    await engine.dispose()


# ── RunService tests ──

@pytest.mark.asyncio
async def test_run_service_seq_monotonicity(run_svc):
    """seq must be strictly monotonic 1..N."""
    run = await run_svc.create_run()
    seqs = []
    for i in range(10):
        ev = await run_svc.append_event(run["id"], type="test", data={"i": i})
        seqs.append(ev["seq"])
    assert seqs == list(range(1, 11))


@pytest.mark.asyncio
async def test_run_service_get_events_after(run_svc):
    """get_events with after_seq filters correctly."""
    run = await run_svc.create_run()
    for i in range(5):
        await run_svc.append_event(run["id"], type="t", data={"i": i})
    events = await run_svc.get_events(run["id"], after_seq=3)
    assert [e["seq"] for e in events] == [4, 5]


@pytest.mark.asyncio
async def test_run_service_cursor_format(run_svc):
    run = await run_svc.create_run()
    ev = await run_svc.append_event(run["id"], type="t", data={})
    assert ev["cursor"] == f"{run['id']}:1"
    rid, seq = parse_cursor(ev["cursor"])
    assert rid == run["id"]
    assert seq == 1


# ── EventBus tests ──

@pytest.mark.asyncio
async def test_eventbus_subscribe_and_publish():
    bus = MemoryEventBus(backlog_size=100)
    received = []

    async def consumer():
        async for ev in bus.subscribe("ch1"):
            received.append(ev)
            if len(received) >= 3:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    for i in range(3):
        await bus.publish("ch1", BusEvent(channel="ch1", event_id=f"id:{i}", data={"i": i}))

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received) == 3
    assert [e.event_id for e in received] == ["id:0", "id:1", "id:2"]


@pytest.mark.asyncio
async def test_eventbus_backlog_replay():
    bus = MemoryEventBus(backlog_size=100)

    # Publish 3 events before subscribing
    for i in range(3):
        await bus.publish("ch", BusEvent(channel="ch", event_id=f"ev:{i}", data={"i": i}))

    # Subscribe with after_id of first event — should replay events after it
    received = []
    async for ev in bus.subscribe("ch", after_id="ev:0"):
        received.append(ev)
        if len(received) >= 2:
            break

    assert [e.event_id for e in received] == ["ev:1", "ev:2"]


@pytest.mark.asyncio
async def test_eventbus_bounded_backlog():
    bus = MemoryEventBus(backlog_size=5)
    for i in range(10):
        await bus.publish("ch", BusEvent(channel="ch", event_id=f"ev:{i}", data={}))

    # Backlog should only have last 5
    assert len(bus._backlogs["ch"]) == 5


# ── API endpoint tests (non-streaming) ──

@pytest.mark.asyncio
async def test_v2_health(app_and_client):
    _, client = app_and_client
    r = await client.get("/v2/health")
    assert r.status_code == 200
    assert r.json()["db_ok"] is True


@pytest.mark.asyncio
async def test_v2_run_crud(app_and_client):
    _, client = app_and_client
    r = await client.post("/v2/runs", json={"status": "active"})
    assert r.status_code == 200
    run_id = r.json()["id"]

    r = await client.get(f"/v2/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["id"] == run_id

    r = await client.get("/v2/runs/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_v2_events_api(app_and_client):
    _, client = app_and_client
    r = await client.post("/v2/runs", json={"status": "active"})
    run_id = r.json()["id"]

    for i in range(5):
        r = await client.post(f"/v2/runs/{run_id}/events", json={"type": "msg", "data": {"i": i}})
        assert r.json()["seq"] == i + 1

    r = await client.get(f"/v2/runs/{run_id}/events")
    assert len(r.json()["events"]) == 5

    r = await client.get(f"/v2/runs/{run_id}/events", params={"after": f"{run_id}:3"})
    assert [e["seq"] for e in r.json()["events"]] == [4, 5]


@pytest.mark.asyncio
async def test_sse_404_missing_run(app_and_client):
    _, client = app_and_client
    r = await client.get("/v2/runs/nonexistent/events/stream")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_v1_still_works(app_and_client):
    """V1 must remain unchanged."""
    _, client = app_and_client
    r = await client.get("/v1/system/health")
    assert r.status_code == 200
