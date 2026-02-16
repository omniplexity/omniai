from __future__ import annotations

import json
import time
import urllib.request
from typing import Any


class McpHttpClient:
    def __init__(self, endpoint_url: str, session_id: str | None = None):
        self.endpoint_url = endpoint_url
        self.session_id = session_id
        self.protocol_version: str | None = None
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _rpc(self, method: str, params: dict[str, Any] | None = None, *, notify: bool = False) -> dict[str, Any] | None:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self._next_id()
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.endpoint_url, method="POST", data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            raw = resp.read().decode("utf-8")
        if notify:
            return None
        if "text/event-stream" in content_type:
            for block in raw.split("\n\n"):
                lines = [line for line in block.splitlines() if line.startswith("data: ")]
                if not lines:
                    continue
                payload = json.loads("\n".join(line[6:] for line in lines))
                if payload.get("id") == body["id"]:
                    return payload
            raise RuntimeError("missing RPC response in SSE stream")
        return json.loads(raw)

    def initialize(self) -> dict[str, Any]:
        start = time.perf_counter()
        rsp = self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "omni-backend", "version": "0.1"}})
        self.protocol_version = rsp.get("result", {}).get("protocolVersion")
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {"response": rsp, "latency_ms": latency_ms, "protocol_version": self.protocol_version, "session_id": self.session_id}

    def notify_initialized(self) -> None:
        self._rpc("notifications/initialized", {}, notify=True)

    def tools_list(self, cursor: str | None = None) -> dict[str, Any]:
        params = {} if cursor is None else {"cursor": cursor}
        rsp = self._rpc("tools/list", params)
        return rsp.get("result", {})

    def tools_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        rsp = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if "error" in rsp:
            raise RuntimeError(rsp["error"].get("message", "MCP error"))
        return rsp.get("result", {})
