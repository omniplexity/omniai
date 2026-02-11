"""DuckDNS ops service (admin-only API backing)."""

from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session as DBSession

from backend.config import Settings, get_settings
from backend.core.logging import get_logger
from backend.db.database import get_session_local
from backend.db.models import DuckDnsUpdateEvent

logger = get_logger(__name__)


DUCKDNS_OK = "OK"
DUCKDNS_KO = "KO"
DUCKDNS_TOKEN_MISSING = "DUCKDNS_TOKEN_MISSING"
DUCKDNS_NETWORK = "DUCKDNS_NETWORK"
DUCKDNS_PARSE = "DUCKDNS_PARSE"
DUCKDNS_INTERNAL = "DUCKDNS_INTERNAL"
DUCKDNS_KO_CODE = "DUCKDNS_KO"


@dataclass
class DuckDnsError(Exception):
    code: str
    message: str
    status_code: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class DuckDnsOpsService:
    """DuckDNS updater + event recorder."""

    def __init__(self, db: DBSession, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    def _get_token(self) -> str:
        # Environment takes precedence; never returned to clients.
        token = (os.getenv("DUCKDNS_TOKEN") or self.settings.duckdns_token or "").strip()
        return token

    def token_present(self) -> bool:
        return not (self._get_token() == "")

    @staticmethod
    def _normalize_response_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore").strip()
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            return "".join(str(v) for v in value).strip()
        return str(value).strip()

    @staticmethod
    def _sanitize_error_message(message: str, token: str) -> str:
        out = message or ""
        if token:
            out = out.replace(token, "***redacted***")
        out = re.sub(r"(token=)[^&\s]+", r"\1***redacted***", out, flags=re.IGNORECASE)
        return out

    async def _discover_public_ip(self, timeout_seconds: int) -> str:
        sources = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://checkip.amazonaws.com",
        ]
        timeout = httpx.Timeout(timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for source in sources:
                try:
                    res = await client.get(source, headers={"Accept": "text/plain"})
                    res.raise_for_status()
                    candidate = self._normalize_response_text(res.text)
                    if candidate:
                        return candidate
                except Exception:
                    continue
        raise DuckDnsError(
            code=DUCKDNS_NETWORK,
            message="Unable to discover public IP address",
            status_code=504,
        )

    def _record_event(
        self,
        *,
        subdomain: str,
        ip: Optional[str],
        response: Optional[str],
        success: bool,
        error_code: Optional[str],
        error_message: Optional[str],
        latency_ms: Optional[int],
        actor_user_id: Optional[str],
        source: str,
    ) -> DuckDnsUpdateEvent:
        event = DuckDnsUpdateEvent(
            subdomain=subdomain,
            ip=ip,
            response=response,
            success=bool(success),
            error_code=error_code,
            error_message=error_message,
            latency_ms=latency_ms,
            actor_user_id=actor_user_id,
            source=source,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    async def update(
        self,
        *,
        force: bool = False,
        test: bool = False,
        ip: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        source: str = "manual",
    ) -> Dict[str, Any]:
        subdomain = (self.settings.duckdns_subdomain or "").strip().lower()
        if not subdomain:
            raise DuckDnsError(
                code=DUCKDNS_PARSE,
                message="DUCKDNS_SUBDOMAIN is not configured",
                status_code=500,
            )

        token = self._get_token()
        if not token:
            self._record_event(
                subdomain=subdomain,
                ip=ip,
                response="ERROR",
                success=False,
                error_code=DUCKDNS_TOKEN_MISSING,
                error_message="DuckDNS token is missing",
                latency_ms=0,
                actor_user_id=actor_user_id,
                source=source,
            )
            raise DuckDnsError(
                code=DUCKDNS_TOKEN_MISSING,
                message="DuckDNS token is missing on server",
                status_code=503,
            )

        resolved_ip = ip.strip() if ip else await self._discover_public_ip(self.settings.duckdns_timeout_seconds)
        start = time.perf_counter()
        url = "https://www.duckdns.org/update"
        params = {
            "domains": subdomain,
            "token": token,
            "ip": resolved_ip,
        }
        if force:
            params["verbose"] = "true"

        try:
            timeout = httpx.Timeout(self.settings.duckdns_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(url, params=params, headers={"Accept": "text/plain"})
                res.raise_for_status()
                normalized = self._normalize_response_text(res.text).upper()
        except httpx.HTTPError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            safe_error = self._sanitize_error_message(str(exc), token)
            self._record_event(
                subdomain=subdomain,
                ip=resolved_ip,
                response="ERROR",
                success=False,
                error_code=DUCKDNS_NETWORK,
                error_message=safe_error,
                latency_ms=latency_ms,
                actor_user_id=actor_user_id,
                source=source,
            )
            raise DuckDnsError(
                code=DUCKDNS_NETWORK,
                message="DuckDNS request failed due to network error",
                status_code=504,
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        if normalized == DUCKDNS_OK:
            event = self._record_event(
                subdomain=subdomain,
                ip=resolved_ip,
                response=DUCKDNS_OK,
                success=True,
                error_code=None,
                error_message=None,
                latency_ms=latency_ms,
                actor_user_id=actor_user_id,
                source=source,
            )
            return {
                "success": True,
                "subdomain": subdomain,
                "ip": resolved_ip,
                "response": DUCKDNS_OK,
                "latency_ms": latency_ms,
                "event_id": event.id,
                "mode": "test" if test else "update",
                "source": source,
            }

        if normalized == DUCKDNS_KO:
            event = self._record_event(
                subdomain=subdomain,
                ip=resolved_ip,
                response=DUCKDNS_KO,
                success=False,
                error_code=DUCKDNS_KO_CODE,
                error_message="DuckDNS returned KO",
                latency_ms=latency_ms,
                actor_user_id=actor_user_id,
                source=source,
            )
            raise DuckDnsError(
                code=DUCKDNS_KO_CODE,
                message="DuckDNS rejected token or subdomain",
                status_code=502,
            )

        self._record_event(
            subdomain=subdomain,
            ip=resolved_ip,
            response=normalized[:32] if normalized else "ERROR",
            success=False,
            error_code=DUCKDNS_PARSE,
            error_message=f"Unexpected DuckDNS response: {normalized}",
            latency_ms=latency_ms,
            actor_user_id=actor_user_id,
            source=source,
        )
        raise DuckDnsError(
            code=DUCKDNS_PARSE,
            message="Unexpected response received from DuckDNS",
            status_code=502,
        )

    def get_logs(self, limit: int = 200) -> Dict[str, Any]:
        max_limit = max(1, min(limit, self.settings.duckdns_events_limit))
        rows = (
            self.db.query(DuckDnsUpdateEvent)
            .order_by(DuckDnsUpdateEvent.created_at.desc())
            .limit(max_limit)
            .all()
        )
        return {
            "logs": [
                {
                    "id": row.id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "subdomain": row.subdomain,
                    "ip": row.ip,
                    "response": row.response,
                    "success": bool(row.success),
                    "error_code": row.error_code,
                    "error_message": row.error_message,
                    "latency_ms": row.latency_ms,
                    "actor_user_id": row.actor_user_id,
                    "source": row.source,
                }
                for row in rows
            ]
        }

    def get_status(self, *, scheduler_interval_minutes: int) -> Dict[str, Any]:
        last = (
            self.db.query(DuckDnsUpdateEvent)
            .order_by(DuckDnsUpdateEvent.created_at.desc())
            .first()
        )
        now_unix = int(datetime.now(UTC).timestamp())
        scheduler_last_run_unix = int(last.created_at.timestamp()) if (last and last.created_at) else None
        scheduler_stale_threshold_minutes = 10
        scheduler_stale_threshold_seconds = scheduler_stale_threshold_minutes * 60

        next_scheduled_run = None
        if self.settings.ops_scheduler_enabled and last and last.created_at:
            next_scheduled_run = (
                last.created_at.timestamp() + (scheduler_interval_minutes * 60)
            )
        scheduler_stale = False
        if self.settings.ops_scheduler_enabled:
            if scheduler_last_run_unix is None:
                scheduler_stale = True
            else:
                scheduler_stale = (now_unix - scheduler_last_run_unix) > scheduler_stale_threshold_seconds

        status = {
            "token_present": self.token_present(),
            "subdomain": self.settings.duckdns_subdomain,
            "scheduler_enabled": bool(self.settings.ops_scheduler_enabled),
            "scheduler_interval_minutes": scheduler_interval_minutes,
            "scheduler_last_run_unix": scheduler_last_run_unix,
            "scheduler_stale": scheduler_stale,
            "scheduler_stale_threshold_minutes": scheduler_stale_threshold_minutes,
            "next_scheduled_run_unix": int(next_scheduled_run) if next_scheduled_run else None,
            "last_update": None,
        }
        if last:
            status["last_update"] = {
                "id": last.id,
                "created_at": last.created_at.isoformat() if last.created_at else None,
                "ip": last.ip,
                "response": last.response,
                "success": bool(last.success),
                "error_code": last.error_code,
                "error_message": last.error_message,
                "latency_ms": last.latency_ms,
                "source": last.source,
            }
        return status


class DuckDnsOpsScheduler:
    """Optional internal scheduler for periodic DuckDNS refresh."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not self.settings.ops_scheduler_enabled:
            return
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="duckdns-ops-scheduler")
        logger.info("DuckDNS ops scheduler started")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.info("DuckDNS ops scheduler stopped")

    async def _run_loop(self) -> None:
        interval_seconds = max(60, int(self.settings.ops_scheduler_interval_minutes * 60))
        while not self._stop_event.is_set():
            sleep_seconds = interval_seconds
            db = None
            try:
                session_local = get_session_local()
                db = session_local()
                service = DuckDnsOpsService(db, self.settings)
                try:
                    await service.update(force=False, source="scheduler")
                except DuckDnsError as err:
                    if err.code == DUCKDNS_TOKEN_MISSING:
                        # Back off to reduce noise when token is absent.
                        sleep_seconds = max(interval_seconds, 900)
            except Exception as exc:
                logger.error("DuckDNS scheduler iteration failed", data={"error": str(exc)})
            finally:
                if db is not None:
                    db.close()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_seconds)
            except asyncio.TimeoutError:
                continue
