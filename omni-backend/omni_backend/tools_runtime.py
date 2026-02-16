from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

EXECUTOR_VERSION = "omni-exec/0.1"


def builtin_tool_manifests() -> list[dict[str, Any]]:
    return [
        {
            "tool_id": "web.search",
            "version": "1.0.0",
            "title": "Web Search",
            "description": "Deterministic stub search",
            "inputs_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query"],
                "properties": {"query": {"type": "string", "minLength": 1}, "top_k": {"type": "integer", "minimum": 1, "maximum": 10}},
            },
            "outputs_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["results"],
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["title", "snippet", "url"],
                            "properties": {"title": {"type": "string"}, "snippet": {"type": "string"}, "url": {"type": "string"}},
                        },
                    }
                },
            },
            "binding": {"type": "inproc_safe", "entrypoint": "omni_backend.tools_runtime:web_search"},
            "risk": {"scopes_required": [], "external_write": False, "network_egress": False, "secrets_required": []},
            "compat": {"contract_version": "v1", "min_runtime_version": "0.1"},
        },
        {
            "tool_id": "files.write_patch",
            "version": "1.0.0",
            "title": "Write Patch",
            "description": "Write content under workspace",
            "inputs_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "unified_diff"],
                "properties": {"path": {"type": "string", "minLength": 1}, "unified_diff": {"type": "string"}},
            },
            "outputs_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["applied", "files_touched"],
                "properties": {"applied": {"type": "boolean"}, "files_touched": {"type": "array", "items": {"type": "string"}}},
            },
            "binding": {"type": "inproc_safe", "entrypoint": "omni_backend.tools_runtime:files_write_patch"},
            "risk": {"scopes_required": ["write_files"], "external_write": True, "network_egress": False, "secrets_required": []},
            "compat": {"contract_version": "v1", "min_runtime_version": "0.1"},
        },
        {
            "tool_id": "python.compute",
            "version": "1.0.0",
            "title": "Python Compute",
            "description": "Sandbox compute stub",
            "inputs_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code"],
                "properties": {"code": {"type": "string"}},
            },
            "outputs_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["stdout", "stderr", "exit_code"],
                "properties": {"stdout": {"type": "string"}, "stderr": {"type": "string"}, "exit_code": {"type": "integer"}},
            },
            "binding": {"type": "sandbox_job", "entrypoint": "omni_backend.tools_runtime:python_compute"},
            "risk": {"scopes_required": ["sandbox_exec"], "external_write": False, "network_egress": False, "secrets_required": []},
            "compat": {"contract_version": "v1", "min_runtime_version": "0.1"},
        },
    ]


def web_search(inputs: dict[str, Any]) -> dict[str, Any]:
    query = inputs["query"]
    top_k = int(inputs.get("top_k", 3))
    seed = int(hashlib.sha256(query.encode("utf-8")).hexdigest()[:8], 16)
    results = []
    for i in range(top_k):
        n = (seed + i) % 10000
        results.append({"title": f"Result {i+1} for {query}", "snippet": f"Deterministic snippet #{n}", "url": f"https://stub.local/{query.replace(' ', '-')}/{n}"})
    return {"results": results}


def _safe_workspace_path(workspace_root: Path, rel_path: str) -> Path:
    if Path(rel_path).is_absolute() or ".." in Path(rel_path).parts:
        raise ValueError("unsafe path")
    if any(token in rel_path.lower() for token in [".env", "secret", "token"]):
        raise ValueError("restricted path")
    out = workspace_root / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def files_write_patch(inputs: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    # Minimal v1 behavior: write provided patch text as file content.
    target = _safe_workspace_path(workspace_root, inputs["path"])
    target.write_text(inputs["unified_diff"], encoding="utf-8")
    return {"applied": True, "files_touched": [str(target)]}


def python_compute(inputs: dict[str, Any], timeout_s: float = 2.0, max_output: int = 4000) -> dict[str, Any]:
    code = inputs["code"]
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script = f.name
    try:
        proc = subprocess.run(["python", script], capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("execution timed out") from exc
    stdout = (proc.stdout or "")[:max_output]
    stderr = (proc.stderr or "")[:max_output]
    return {"stdout": stdout, "stderr": stderr, "exit_code": int(proc.returncode)}


def execute_tool(
    manifest: dict[str, Any],
    inputs: dict[str, Any],
    workspace_root: Path,
    mcp_remote_caller: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    binding = manifest["binding"]["type"]
    tool_id = manifest["tool_id"]
    if binding == "inproc_safe":
        if tool_id == "web.search":
            return web_search(inputs)
        if tool_id == "files.write_patch":
            return files_write_patch(inputs, workspace_root)
    if binding == "sandbox_job":
        if tool_id == "python.compute":
            return python_compute(inputs)
    if binding == "mcp_remote":
        if mcp_remote_caller is None:
            raise NotImplementedError("UNSUPPORTED_BINDING")
        return mcp_remote_caller(manifest, inputs)
    if binding in {"mcp_remote", "openapi_proxy"}:
        raise NotImplementedError("UNSUPPORTED_BINDING")
    raise NotImplementedError("UNSUPPORTED_BINDING")


def validate_json_schema(schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    from jsonschema import Draft202012Validator

    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: e.path)
    return [f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in errors]
