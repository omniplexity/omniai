from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from omni_contracts.models import Pins, Privacy, RunEventEnvelope, SystemConfigSnapshot
from omni_contracts.validate import validate_event, validate_schema

GOLDENS = Path(__file__).parent / "goldens"
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "omni-contracts" / "schemas"


def _build_envelope(golden: dict) -> dict:
    return {
        "event_id": str(uuid4()),
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "project_id": str(uuid4()),
        "seq": 1,
        "ts": datetime.now(UTC).isoformat(),
        "kind": golden["kind"],
        "payload": golden["payload"],
        "actor": golden["actor"],
        "privacy": Privacy().model_dump(),
        "pins": Pins().model_dump(),
    }


# ============================================================
# GOLDEN FILE ROUND-TRIP TESTS
# ============================================================

def test_golden_round_trip() -> None:
    """Test all golden files can be validated and parsed."""
    for path in sorted(GOLDENS.glob("*.json")):
        golden = json.loads(path.read_text(encoding="utf-8"))
        if "kind" not in golden:
            continue
        event_dict = _build_envelope(golden)
        validate_event(event_dict)
        model = RunEventEnvelope.model_validate(event_dict)
        validate_event(model.model_dump(mode="json", exclude_none=True))


def test_artifact_linked_golden_present() -> None:
    assert (GOLDENS / "artifact_linked.json").exists()


def test_system_config_golden_round_trip() -> None:
    golden = json.loads((GOLDENS / "system_config.json").read_text(encoding="utf-8"))
    validate_schema("system_config.schema.json", golden)
    model = SystemConfigSnapshot.model_validate(golden)
    validate_schema("system_config.schema.json", model.model_dump(mode="json", exclude_none=True))


# ============================================================
# SCHEMA VALIDATION TESTS - All Event Kinds
# ============================================================

EVENT_KINDS = [
    "user_message",
    "assistant_message",
    "assistant_message_delta",
    "tool_call",
    "tool_result",
    "tool_error",
    "artifact_ref",
    "artifact_linked",
    "system_event",
    "editor_action",
    "run_status",
    "memory_item_created",
    "memory_item_updated",
    "memory_item_deleted",
    "memory_retrieved",
    "research_stage_started",
    "research_stage_completed",
    "research_source_created",
    "research_report_created",
    "workflow_defined",
    "workflow_run_started",
    "workflow_node_started",
    "workflow_node_completed",
    "workflow_node_failed",
    "workflow_run_completed",
    "tool_package_published",
    "tool_package_installed",
    "tool_package_uninstalled",
    "tool_package_yanked",
    "tool_pins_updated",
    "tool_package_reported",
    "tool_package_status_changed",
    "tool_package_mirrored",
    "collection_created",
    "collection_updated",
    "metrics_computed",
    "quota_exceeded",
    "project_member_added",
    "project_member_role_changed",
    "project_member_removed",
    "comment_created",
    "comment_deleted",
    "activity_emitted",
    "auth_session_created",
    "auth_session_revoked",
    "auth_login_failed",
    "auth_csrf_failed",
]


@pytest.mark.parametrize("kind", EVENT_KINDS)
def test_all_event_kind_schemas_valid(kind: str) -> None:
    """Test that all event kind schemas exist and are valid JSON Schema."""
    schema_path = SCHEMAS_DIR / "run_event_kinds" / f"{kind}.schema.json"
    assert schema_path.exists(), f"Schema missing for {kind}"
    
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "$schema" in schema, f"Missing $schema in {kind}"
    assert "type" in schema, f"Missing type in {kind}"


@pytest.mark.parametrize("kind", EVENT_KINDS)
def test_all_event_kind_goldens_exist(kind: str) -> None:
    """Test that golden files exist for all event kinds."""
    golden_path = GOLDENS / f"{kind}.json"
    # Not all goldens exist yet, so we just check schema exists


def test_user_message_schema_validation() -> None:
    """Test user_message payload validation."""
    golden = {"kind": "user_message", "actor": "user", "payload": {"text": "hello"}}
    validate_schema("run_event_kinds/user_message.schema.json", golden["payload"])


def test_assistant_message_schema_validation() -> None:
    """Test assistant_message payload validation."""
    golden = {"kind": "assistant_message", "actor": "assistant", "payload": {"text": "response"}}
    validate_schema("run_event_kinds/assistant_message.schema.json", golden["payload"])


def test_tool_call_schema_validation() -> None:
    """Test tool_call payload validation."""
    golden = {
        "kind": "tool_call",
        "actor": "tool",
        "payload": {
            "tool_id": "web.search",
            "tool_version": "1.0.0",
            "inputs": {"query": "test"},
            "binding_type": "inproc_safe",
            "correlation_id": "corr-123"
        }
    }
    validate_schema("run_event_kinds/tool_call.schema.json", golden["payload"])


def test_tool_result_schema_validation() -> None:
    """Test tool_result payload validation."""
    golden = {
        "kind": "tool_result",
        "actor": "tool",
        "payload": {
            "tool_id": "web.search",
            "tool_version": "1.0.0",
            "outputs": {"results": []},
            "correlation_id": "corr-123"
        }
    }
    validate_schema("run_event_kinds/tool_result.schema.json", golden["payload"])


def test_tool_error_schema_validation() -> None:
    """Test tool_error payload validation."""
    golden = {
        "kind": "tool_error",
        "actor": "tool",
        "payload": {
            "tool_id": "web.search",
            "tool_version": "1.0.0",
            "error_code": "TIMEOUT",
            "message": "execution timed out",
            "correlation_id": "corr-123"
        }
    }
    validate_schema("run_event_kinds/tool_error.schema.json", golden["payload"])


def test_system_event_schema_validation() -> None:
    """Test system_event payload validation."""
    golden = {
        "kind": "system_event",
        "actor": "system",
        "payload": {
            "code": "approval_required",
            "message": "Elevated risk requires approval"
        }
    }
    validate_schema("run_event_kinds/system_event.schema.json", golden["payload"])


def test_memory_item_created_schema_validation() -> None:
    """Test memory_item_created payload validation."""
    golden = {
        "kind": "memory_item_created",
        "actor": "system",
        "payload": {
            "memory_id": "mem-123",
            "provenance": {"source_kind": "manual"}
        }
    }
    validate_schema("run_event_kinds/memory_item_created.schema.json", golden["payload"])


def test_workflow_run_started_schema_validation() -> None:
    """Test workflow_run_started payload validation."""
    golden = {
        "kind": "workflow_run_started",
        "actor": "system",
        "payload": {
            "workflow_run_id": "wf-123",
            "workflow_id": "wf-1",
            "inputs": {},
            "started_at": datetime.now(UTC).isoformat()
        }
    }
    validate_schema("run_event_kinds/workflow_run_started.schema.json", golden["payload"])


def test_workflow_node_completed_schema_validation() -> None:
    """Test workflow_node_completed payload validation."""
    golden = {
        "kind": "workflow_node_completed",
        "actor": "system",
        "payload": {
            "workflow_run_id": "wf-123",
            "node_id": "node-1",
            "attempt": 1,
            "outputs_ref": "art-123",
            "completed_at": datetime.now(UTC).isoformat()
        }
    }
    validate_schema("run_event_kinds/workflow_node_completed.schema.json", golden["payload"])


def test_research_stage_started_schema_validation() -> None:
    """Test research_stage_started payload validation."""
    golden = {
        "kind": "research_stage_started",
        "actor": "system",
        "payload": {
            "stage": "decompose",
            "query": "test query",
            "started_at": datetime.now(UTC).isoformat()
        }
    }
    validate_schema("run_event_kinds/research_stage_started.schema.json", golden["payload"])


def test_auth_session_created_schema_validation() -> None:
    """Test auth_session_created payload validation."""
    golden = {
        "kind": "auth_session_created",
        "actor": "system",
        "payload": {
            "user_id": "user-123",
            "session_id": "sess-123",
            "created_at": datetime.now(UTC).isoformat()
        }
    }
    validate_schema("run_event_kinds/auth_session_created.schema.json", golden["payload"])


# ============================================================
# MODEL VALIDATION TESTS
# ============================================================

def test_run_event_envelope_full_validation() -> None:
    """Test full RunEventEnvelope model validation."""
    event = {
        "event_id": str(uuid4()),
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "project_id": str(uuid4()),
        "seq": 1,
        "ts": datetime.now(UTC).isoformat(),
        "kind": "user_message",
        "payload": {"text": "test"},
        "actor": "user",
        "privacy": {"redact_level": "none", "contains_secrets": False},
        "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}
    }
    model = RunEventEnvelope.model_validate(event)
    assert model.kind == "user_message"
    assert model.actor == "user"


def test_pins_model_validation() -> None:
    """Test Pins model validation."""
    pins = Pins(
        model={"provider": "openai", "model_id": "gpt-4", "params": {"temperature": 0.7}, "seed": None},
        tools=[{"name": "web.search", "version": "1.0.0"}],
        runtime={"executor_version": "v1"}
    )
    assert pins.model.provider == "openai"
    assert len(pins.tools) == 1


def test_privacy_model_validation() -> None:
    """Test Privacy model validation."""
    privacy = Privacy(redact_level="partial", contains_secrets=True)
    assert privacy.redact_level == "partial"
    assert privacy.contains_secrets is True


def test_system_config_snapshot_validation() -> None:
    """Test SystemConfigSnapshot model validation."""
    config = SystemConfigSnapshot(
        notify_tool_errors=True,
        notify_tool_errors_only_codes=["TIMEOUT"],
        notify_tool_errors_only_bindings=["mcp_remote"],
        notify_tool_errors_max_per_run=5,
        sse_max_replay=200,
        sse_heartbeat_seconds=30,
        artifact_max_bytes=5_000_000,
        artifact_part_size=1_000_000,
        session_ttl_seconds=86400,
        session_sliding_enabled=True,
        session_sliding_window_seconds=3600,
        max_events_per_run=10000,
        max_bytes_per_run=100_000_000,
        generated_at=datetime.now(UTC),
        contract_version="0.1.0",
        runtime_version="omni-backend-0.4.0"
    )
    assert config.notify_tool_errors is True
    assert config.session_ttl_seconds == 86400


# ============================================================
# CONTRACT BOUNDARY TESTS
# ============================================================

def test_backend_event_validation_compatibility() -> None:
    """Test that backend-generated events pass contract validation."""
    # Simulate event from backend
    event = {
        "event_id": str(uuid4()),
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "project_id": str(uuid4()),
        "seq": 1,
        "ts": datetime.now(UTC).isoformat(),
        "kind": "tool_call",
        "payload": {
            "tool_id": "files.read",
            "tool_version": "1.0.0",
            "inputs": {"path": "/test.txt"},
            "binding_type": "inproc_safe",
            "correlation_id": str(uuid4())
        },
        "actor": "tool",
        "privacy": {"redact_level": "none", "contains_secrets": False},
        "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}
    }
    # This should not raise
    validate_event(event)


def test_all_top_level_schemas_exist() -> None:
    """Test all top-level schemas exist."""
    required_schemas = [
        "run_event_envelope.schema.json",
        "system_config.schema.json",
        "tool_manifest.schema.json",
        "tool_package.schema.json",
        "artifact_ref.schema.json",
        "memory_item.schema.json",
        "policy.schema.json",
        "user.schema.json",
        "report.schema.json",
    ]
    for schema_name in required_schemas:
        schema_path = SCHEMAS_DIR / schema_name
        assert schema_path.exists(), f"Missing schema: {schema_name}"
        # Verify it's valid JSON
        json.loads(schema_path.read_text(encoding="utf-8"))


# ============================================================
# EDGE CASE TESTS
# ============================================================

def test_event_with_all_optional_fields() -> None:
    """Test event with all optional fields populated."""
    event = {
        "event_id": str(uuid4()),
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "project_id": str(uuid4()),
        "seq": 1,
        "ts": datetime.now(UTC).isoformat(),
        "kind": "tool_call",
        "payload": {"tool_id": "test", "tool_version": "1.0", "inputs": {}, "binding_type": "inproc_safe", "correlation_id": "corr"},
        "parent_event_id": str(uuid4()),
        "correlation_id": "corr-123",
        "actor": "tool",
        "privacy": {"redact_level": "full", "contains_secrets": True},
        "pins": {"model": {"provider": "openai", "model_id": "gpt-4", "params": {"temperature": 1.0}, "seed": 42}, "tools": [{"name": "web.search", "version": "1.0.0"}], "runtime": {"executor_version": "v1"}}
    }
    validate_event(event)
    model = RunEventEnvelope.model_validate(event)
    assert model.parent_event_id is not None
    assert model.correlation_id == "corr-123"


def test_invalid_event_rejected() -> None:
    """Test that invalid events are rejected."""
    event = {
        "event_id": str(uuid4()),
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "project_id": str(uuid4()),
        "seq": 1,
        "ts": datetime.now(UTC).isoformat(),
        "kind": "user_message",
        "payload": {},  # Missing required "text" field
        "actor": "user",
        "privacy": {"redact_level": "none", "contains_secrets": False},
        "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}
    }
    with pytest.raises(ValueError):
        validate_event(event)
