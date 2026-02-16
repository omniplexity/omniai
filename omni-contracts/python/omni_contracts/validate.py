from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(schema_name: str, data: dict[str, Any]) -> None:
    schema = _load_schema(SCHEMAS_DIR / schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = [f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in errors]
        raise ValueError("; ".join(msgs))


def validate_event(event: dict[str, Any]) -> None:
    validate_schema("run_event_envelope.schema.json", event)
    kind = event.get("kind")
    if not kind:
        raise ValueError("kind is required")
    validate_schema(f"run_event_kinds/{kind}.schema.json", event.get("payload", {}))