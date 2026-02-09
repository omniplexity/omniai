"""Custom middleware for OmniAI backend."""

import ipaddress
import re
import secrets
import time
from collections import deque
from typing import Callable, List, Optional, Set, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging import get_logger, request_context

logger = get_logger(__name__)

# Compiled regex patterns for CORS origin validation
_ORIGIN_PATTERN_CACHE: dict[str, re.Pattern] = {}

# Default allowed hosts for tunnel deployments
DEFAULT_ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    # Add your tunnel domains here, e.g.:
    # "your-app.ngrok-free.dev",
    # "your-custom-domain.com",
]

# Trusted proxy IP ranges for X-Forwarded-* header validation
# Only trust forwarded headers from these sources
TRUSTED_PROXY_NETS: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    # Docker bridge (common internal networking)
    ipaddress.ip_network("172.17.0.0/16"),
    # Kubernetes pod network (if running in k8s)
    ipaddress.ip_network("10.244.0.0/16"),
    # Additional ranges can be configured via settings
]


def _is_trusted_proxy(client_ip: str) -> bool:
    """Check if the client IP is from a trusted proxy.
    
    Only IPs from trusted proxy ranges can provide X-Forwarded-* headers
    that we'll trust for determining the real client address.
    """
    try:
        ip = ipaddress.ip_address(client_ip)
        for net in TRUSTED_PROXY_NETS:
            if ip in net:
                return True
    except ValueError:
        # Invalid IP format
        pass
    return False


def get_client_ip(request: Request) -> Tuple[str, bool]:
    """Get the real client IP, respecting X-Forwarded-* headers from trusted proxies.
    
    Returns:
        Tuple of (client_ip, is_trusted) where is_trusted indicates whether
        the IP was validated from a trusted proxy.
    """
    direct_ip = request.client.host if request.client else None
    
    # Check X-Forwarded-For header
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # Get the first IP in the chain (original client)
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            # Only trust X-Forwarded-For if it comes from a trusted proxy
            if direct_ip and _is_trusted_proxy(direct_ip):
                return (first_ip, True)
            # If not from trusted proxy, log warning and use direct IP
            logger.warning(
                "Untrusted X-Forwarded-For header ignored",
                data={"forwarded_for": forwarded_for, "direct_ip": direct_ip},
            )
            return (direct_ip or first_ip, False)
    
    # No forwarded header, use direct connection IP
    return (direct_ip or "unknown", False)


class ForwardedHeadersMiddleware(BaseHTTPMiddleware):
    """Validate and normalize X-Forwarded-* headers from trusted proxies.
    
    This middleware ensures that forwarded headers are only trusted when
    the request comes from a known proxy IP address.
    
    Security: Prevents IP spoofing attacks where attackers send fake
    X-Forwarded-For headers to bypass rate limits or appear as other users.
    """

    def __init__(
        self,
        app,
        trusted_proxies: Optional[List[str]] = None,
    ):
        """Initialize forwarded headers middleware.
        
        Args:
            app: The ASGI application
            trusted_proxies: Optional list of trusted proxy IP ranges (CIDR notation)
        """
        super().__init__(app)
        self._trusted_nets: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if trusted_proxies:
            for proxy in trusted_proxies:
                try:
                    self._trusted_nets.append(ipaddress.ip_network(proxy, strict=False))
                except ValueError:
                    logger.warning(f"Invalid trusted proxy network: {proxy}")
        # Fall back to defaults if none configured
        if not self._trusted_nets:
            self._trusted_nets = TRUSTED_PROXY_NETS

    def _is_trusted(self, client_ip: str) -> bool:
        """Check if client IP is from a trusted proxy."""
        try:
            ip = ipaddress.ip_address(client_ip)
            for net in self._trusted_nets:
                if ip in net:
                    return True
        except ValueError:
            pass
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate forwarded headers before processing request."""
        direct_ip = request.client.host if request.client else None
        
        # Check if request comes from trusted proxy
        is_from_trusted_proxy = direct_ip and self._is_trusted(direct_ip)
        
        # Log untrusted forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for and not is_from_trusted_proxy:
            logger.warning(
                "X-Forwarded-For header from untrusted source, ignoring",
                data={
                    "x-forwarded-for": forwarded_for,
                    "client_ip": direct_ip,
                },
            )
            # Strip the untrusted header to prevent confusion
            request.headers.__dict__.pop("x-forwarded-for", None)
        
        # Also validate X-Forwarded-Proto and X-Forwarded-Host
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto and not is_from_trusted_proxy:
            logger.warning(
                "X-Forwarded-Proto header from untrusted source, ignoring",
                data={"x-forwarded-proto": forwarded_proto, "client_ip": direct_ip},
            )
            request.headers.__dict__.pop("x-forwarded-proto", None)
        
        forwarded_host = request.headers.get("x-forwarded-host", "")
        if forwarded_host and not is_from_trusted_proxy:
            logger.warning(
                "X-Forwarded-Host header from untrusted source, ignoring",
                data={"x-forwarded-host": forwarded_host, "client_ip": direct_ip},
            )
            request.headers.__dict__.pop("x-forwarded-host", None)

        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to inject request context for logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with context."""
        request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
        start_time = time.perf_counter()

        # Set context for logging
        ctx = {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        }
        token = request_context.set(ctx)

        try:
            response = await call_next(request)

            # Log request completion
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code}",
                data={"duration_ms": round(duration_ms, 2)},
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response

        finally:
            request_context.reset(token)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    def __init__(self, app, max_bytes: int = 1048576, voice_max_bytes: int | None = None):
        """Initialize with max size in bytes."""
        super().__init__(app)
        self.max_bytes = max_bytes
        self.voice_max_bytes = voice_max_bytes or max_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size before processing."""
        content_length = request.headers.get("content-length")
        limit = self.max_bytes
        if request.url.path.startswith("/v1/voice") or request.url.path.startswith("/api/voice"):
            limit = self.voice_max_bytes

        if content_length and int(content_length) > limit:
            logger.warning(
                f"Request too large: {content_length} bytes",
                data={"max_bytes": limit},
            )
            return Response(
                content='{"detail": "Request body too large", "error": {"code": "E4130", "message": "Request body too large"}}',
                status_code=413,
                media_type="application/json",
            )

        return await call_next(request)


class RequestSizeLimitExceeded(Exception):
    """Raised when request body exceeds configured size limit."""

    def __init__(self, max_bytes: int, received_bytes: int):
        self.max_bytes = max_bytes
        self.received_bytes = received_bytes
        super().__init__(f"Request body exceeds {max_bytes} bytes (received {received_bytes})")


class MaxRequestSizeMiddleware(BaseHTTPMiddleware):
    """Enforces a maximum request body size for all requests.
    
    - If Content-Length is present and exceeds max_bytes → 413.
    - If chunked/unknown length → wraps receive() and enforces a byte counter.
    - Returns clean 413 JSON instead of generic disconnect.
    """

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = int(max_bytes)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size before processing."""
        # Fast path: check Content-Length header first
        cl = request.headers.get("content-length")
        if cl:
            try:
                content_length = int(cl)
                if content_length > self.max_bytes:
                    return Response(
                        content='{"error": {"code": "E1413", "message": "Request body too large"}}',
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                # Non-integer Content-Length: treat as suspicious
                return Response(
                    content='{"error": {"code": "E1400", "message": "Invalid Content-Length"}}',
                    status_code=400,
                    media_type="application/json",
                )

        # For chunked or unknown-length requests, enforce streaming limit
        received = 0
        original_receive = request._receive  # type: ignore[attr-defined]

        async def limited_receive():
            nonlocal received
            message = await original_receive()
            if message["type"] == "http.request":
                body = message.get("body", b"") or b""
                received += len(body)
                if received > self.max_bytes:
                    # Raise custom exception for clean error handling
                    raise RequestSizeLimitExceeded(self.max_bytes, received)
            return message

        request._receive = limited_receive  # type: ignore[attr-defined]
        
        try:
            response = await call_next(request)
            return response
        except RequestSizeLimitExceeded:
            # Return clean 413 instead of generic disconnect
            return Response(
                content='{"error": {"code": "E1413", "message": "Request body too large"}}',
                status_code=413,
                media_type="application/json",
            )


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """Validate Host header to prevent host header injection attacks.
    
    This middleware rejects requests with Host headers that don't match
    expected allowed hosts (localhost, tunnel domains, etc.).
    """

    def __init__(
        self,
        app,
        allowed_hosts: Optional[List[str]] = None,
        allow_any_host: bool = False,
    ):
        """Initialize trusted host middleware.
        
        Args:
            app: The ASGI application
            allowed_hosts: List of allowed hostnames. If None, uses DEFAULT_ALLOWED_HOSTS
            allow_any_host: If True, skip validation (useful for dev/testing)
        """
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or list(DEFAULT_ALLOWED_HOSTS)
        self.allow_any_host = allow_any_host

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate Host header before processing request."""
        if self.allow_any_host:
            return await call_next(request)

        host_header = request.headers.get("host", "")

        # Allow empty host header for internal requests
        if not host_header:
            return await call_next(request)

        # Check if host matches allowed patterns
        is_allowed = False
        for allowed in self.allowed_hosts:
            # Support wildcard subdomains for tunnel domains
            if allowed.startswith("*."):
                domain = allowed[2:]
                if host_header.endswith(domain) or host_header.endswith("." + domain):
                    is_allowed = True
                    break
            elif host_header == allowed or host_header.startswith(allowed + ":"):
                is_allowed = True
                break

        if not is_allowed:
            logger.warning(
                "Rejected request with unauthorized Host header",
                data={"host": host_header, "allowed_hosts": self.allowed_hosts},
            )
            return Response(
                content='{"detail": "Host not allowed", "error": {"code": "E1001", "message": "Host header not authorized"}}',
                status_code=400,
                media_type="application/json",
            )

        return await call_next(request)


# Hot-path rate limiting: stricter limits for sensitive endpoints
_AUTH_RATE_LIMIT = 10  # 10 requests per minute for auth endpoints
_INVITE_RATE_LIMIT = 5  # 5 invites per hour per user
_STREAM_RATE_LIMIT = 20  # 20 concurrent streams per user


def _normalize_path(path: str) -> str:
    """Normalize request path for consistent matching.
    
    - Strips trailing slashes for consistency
    - Returns "/" for empty or root paths
    """
    return path.rstrip("/") or "/"


class HotPathRateLimitMiddleware(BaseHTTPMiddleware):
    """Stricter rate limiting for hot-path endpoints.
    
    Applies additional rate limits to endpoints that are commonly targeted:
    - /api/auth/login - Brute force protection
    - /api/auth/register - Account enumeration protection
    - /api/auth/invite* - Invite spam protection
    - /v1/chat/stream GET - Streaming abuse protection
    
    Security exemptions:
    - OPTIONS method (CORS preflight - browsers need this unblocked)
    - Health/readiness endpoints (prevent self-inflicted outages)
    """

    # Paths that need stricter rate limiting (use normalized paths)
    AUTH_PATHS = frozenset({"/api/auth/login", "/api/auth/register"})
    INVITE_PATHS = frozenset({"/api/auth/invite", "/api/admin/invite"})
    # Only GET /v1/chat/stream needs concurrent stream limiting
    # POST /v1/chat creates runs and should use regular rate limits
    STREAM_PATHS = frozenset({"/v1/chat/stream"})
    
    # Exemptions for security and operational reasons (use normalized paths)
    EXEMPT_METHODS = frozenset({"OPTIONS"})  # CORS preflight must not be rate-limited
    EXEMPT_PATHS = frozenset({
        "/health",
        "/healthz",
        "/readyz",
        "/v1/health",
        "/v1/status",
    })

    def __init__(
        self,
        app,
        auth_rpm: int = _AUTH_RATE_LIMIT,
        invite_rpm: int = 5,
        stream_concurrent: int = _STREAM_RATE_LIMIT,
    ):
        """Initialize hot-path rate limiter.
        
        Args:
            app: The ASGI application
            auth_rpm: Requests per minute for auth endpoints
            invite_rpm: Invites per minute for invite endpoints
            stream_concurrent: Max concurrent streams per user
        """
        super().__init__(app)
        self.auth_rpm = max(0, int(auth_rpm))
        self.invite_rpm = max(0, int(invite_rpm))
        self.stream_concurrent = max(0, int(stream_concurrent))
        self.window_seconds = 60
        self._auth_buckets: dict[str, deque[float]] = {}
        self._invite_buckets: dict[str, deque[float]] = {}
        self._stream_buckets: dict[str, deque[int]] = {}  # Track concurrent connections

    def _allow(self, buckets: dict[str, deque[float]], key: str, limit: int, now: float) -> bool:
        if limit <= 0:
            return True

        bucket = buckets.get(key)
        if bucket is None:
            bucket = deque()
            buckets[key] = bucket

        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply hot-path rate limiting."""
        # Normalize path for consistent matching (strips trailing slashes)
        path = _normalize_path(request.url.path)
        method = request.method

        # Skip exempt methods (CORS preflight)
        if method in self.EXEMPT_METHODS:
            return await call_next(request)

        # Skip exempt paths (health checks, liveness probes)
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get client IP
        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else None
        if not client_ip and request.client:
            client_ip = request.client.host
        client_ip = client_ip or "unknown"

        now = time.monotonic()

        # Check auth path rate limiting (login, register)
        if method == "POST" and path in self.AUTH_PATHS:
            if not self._allow(self._auth_buckets, client_ip, self.auth_rpm, now):
                logger.warning(
                    "Auth rate limit exceeded",
                    data={"path": path, "ip": client_ip, "rpm": self.auth_rpm},
                )
                return Response(
                    content='{"detail": "Rate limit exceeded", "error": {"code": "E1101", "message": "Too many auth requests"}}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": "60"},
                )

        # Check invite path rate limiting
        if method == "POST" and any(path.startswith(p) for p in self.INVITE_PATHS):
            if not self._allow(self._invite_buckets, client_ip, self.invite_rpm, now):
                logger.warning(
                    "Invite rate limit exceeded",
                    data={"path": path, "ip": client_ip, "rpm": self.invite_rpm},
                )
                return Response(
                    content='{"detail": "Rate limit exceeded", "error": {"code": "E1102", "message": "Too many invite requests"}}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": "3600"},
                )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""

    EXEMPT_PATHS = {"/health", "/healthz", "/readyz", "/api/diag/lite"}

    def __init__(
        self,
        app,
        ip_requests_per_minute: int = 60,
        user_requests_per_minute: int = 60,
    ):
        """Initialize rate limiter with per-IP and per-user RPM.

        Per-user limits require a valid session cookie; they are enforced
        in addition to per-IP limits.
        """
        super().__init__(app)
        self.ip_requests_per_minute = max(0, int(ip_requests_per_minute))
        self.user_requests_per_minute = max(0, int(user_requests_per_minute))
        self.window_seconds = 60
        self._ip_buckets: dict[str, deque[float]] = {}
        self._user_buckets: dict[str, deque[float]] = {}

    def _allow(self, buckets: dict[str, deque[float]], key: str, limit: int, now: float) -> bool:
        if limit <= 0:
            return True

        bucket = buckets.get(key)
        if bucket is None:
            bucket = deque()
            buckets[key] = bucket

        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to incoming requests."""
        if self.ip_requests_per_minute <= 0 and self.user_requests_per_minute <= 0:
            return await call_next(request)

        # Normalize path for consistent matching (strips trailing slashes)
        normalized_path = _normalize_path(request.url.path)
        if normalized_path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Determine client IP (respect X-Forwarded-For when present)
        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else None
        if not client_ip and request.client:
            client_ip = request.client.host
        client_ip = client_ip or "unknown"

        now = time.monotonic()

        # Per-IP limit (always enforce if enabled)
        if not self._allow(self._ip_buckets, client_ip, self.ip_requests_per_minute, now):
            logger.warning(
                "Rate limit exceeded",
                data={"scope": "ip", "ip": client_ip, "rpm": self.ip_requests_per_minute},
            )
            return Response(
                content='{"detail": "Rate limit exceeded", "error": {"code": "E1005", "message": "Rate limit exceeded"}}',
                status_code=429,
                media_type="application/json",
            )

        # Per-user limit (only if session is valid)
        if self.user_requests_per_minute > 0:
            try:
                from backend.config import get_settings
                from backend.auth.session import validate_session
                from backend.db.database import get_session_local

                settings = get_settings()
                session_cookie = request.cookies.get(settings.session_cookie_name)
                if session_cookie:
                    SessionLocal = get_session_local()
                    db = SessionLocal()
                    try:
                        session = validate_session(db, session_cookie)
                    finally:
                        db.close()

                    if session:
                        user_key = session.user_id
                        if not self._allow(
                            self._user_buckets,
                            user_key,
                            self.user_requests_per_minute,
                            now,
                        ):
                            logger.warning(
                                "Rate limit exceeded",
                                data={
                                    "scope": "user",
                                    "user_id": user_key,
                                    "rpm": self.user_requests_per_minute,
                                },
                            )
                            return Response(
                                content='{"detail": "Rate limit exceeded", "error": {"code": "E1006", "message": "Rate limit exceeded"}}',
                                status_code=429,
                                media_type="application/json",
                            )
            except Exception:
                # Fail open for user limiting; IP limiting still applies.
                pass

        return await call_next(request)


def _parse_origin(origin: str) -> tuple[str, str, int] | None:
    """Parse origin into (scheme, hostname, port) tuple.
    
    Returns None if the origin is malformed, missing required parts, or explicitly invalid.
    
    Security considerations:
    - Rejects "null" origin (used by browser in opaque requests)
    - Strips userinfo (user:pass@host) - not used in origin matching
    - Normalizes lowercase hostname
    - Defaults ports: 443 for https, 80 for http
    """
    # Reject explicit null origin (browser sends this for opaque requests)
    if origin.lower() == "null":
        return None
    
    try:
        # Handle origins with implicit ports
        if origin.startswith("//"):
            origin = "https:" + origin
        elif not origin.startswith("http"):
            origin = "https://" + origin
        
        # Parse URL
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        
        scheme = parsed.scheme
        # urlparse strips userinfo automatically - user:pass@host → hostname only
        hostname = parsed.hostname or ""
        port = parsed.port if parsed.port else (443 if scheme == "https" else 80)
        
        if not scheme or not hostname:
            return None
        
        return (scheme, hostname.lower(), port)
    except Exception:
        return None


def _is_origin_allowed(origin: str, allowed_origins: Set[str]) -> bool:
    """Check if origin matches allowed origins with exact scheme+hostname+port matching.
    
    Prevents substring bypass attacks like:
    - https://omniplexity.github.io.evil.com (should NOT match omniplexity.github.io)
    - https://evil.com?origin=https://omniplexity.github.io
    
    Supports fnmatch-style wildcards for hostname only (e.g., *.example.com).
    """
    if not origin:
        return False
    
    parsed = _parse_origin(origin)
    if not parsed:
        return False
    
    origin_scheme, origin_hostname, origin_port = parsed
    
    for allowed in allowed_origins:
        allowed_parsed = _parse_origin(allowed)
        if not allowed_parsed:
            continue
        
        allowed_scheme, allowed_hostname, allowed_port = allowed_parsed
        
        # Exact match on scheme, hostname, and port
        if origin_scheme == allowed_scheme and origin_port == allowed_port:
            if origin_hostname == allowed_hostname:
                return True
            
            # Support fnmatch-style wildcards for hostname only
            if "*" in allowed_hostname:
                from fnmatch import fnmatch
                if fnmatch(origin_hostname, allowed_hostname):
                    return True
    
    return False


def _is_same_site_request(request: Request) -> bool:
    """Check if request is same-site based on Origin/Host headers."""
    origin = request.headers.get("origin")
    host = request.headers.get("host", "")
    
    if not origin or not host:
        return True
    
    # Parse origin
    origin_parsed = _parse_origin(origin)
    if not origin_parsed:
        return False
    
    origin_scheme, origin_hostname, origin_port = origin_parsed
    
    # Check if origin matches host
    # Extract host:port from Host header
    host_port = host.split(":")
    host_hostname = host_port[0].lower()
    host_port_num = host_port[1] if len(host_port) > 1 else ("443" if origin_scheme == "https" else "80")
    
    return (
        origin_hostname == host_hostname
        and origin_port == host_port_num
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.
    
    Sets headers to protect against common web vulnerabilities:
    - X-Content-Type-Options: nosniff
    - Referrer-Policy: no-referrer
    - Permissions-Policy: restrictive (camera, mic, etc. disabled)
    - Cross-Origin-Resource-Policy: NOT set by default (can break future embedding)
    
    Note: Cross-Origin-Resource-Policy is intentionally NOT set by default.
    If you need cross-origin embedding later, configure it at the reverse proxy level.
    """

    # Security headers applied to all responses (CORP omitted for flexibility)
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        # Disable potentially sensitive browser features by default
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        # Prevent clickjacking - deny framing of this resource
        "X-Frame-Options": "DENY",
    }

    # Headers that should NOT be exposed to cross-site requests
    SENSITIVE_HEADERS = {
        "Set-Cookie",
        "Authorization",
        "X-CSRF-Token",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Add security headers
        for header, value in self.SECURITY_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value

        # For cross-site requests, strip sensitive headers
        origin = request.headers.get("origin")
        if origin:
            # Check if this is a cross-site request
            is_cross_site = not _is_same_site_request(request)
            
            if is_cross_site:
                # Don't expose sensitive headers to cross-site requests
                for header in self.SENSITIVE_HEADERS:
                    if header in response.headers:
                        del response.headers[header]

        return response


class ChatCSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware for chat endpoints.
    
    Validates CSRF tokens AND origin/referer for cross-site protection.
    
    Security notes:
    - GET requests are generally safe methods, BUT streaming endpoints that
      return user data require origin validation for defense-in-depth
    - SSE polling endpoints can leak sensitive conversation content
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = {"/health", "/readyz", "/docs", "/redoc", "/openapi.json"}
    
    # GET endpoints that return user data and need origin validation
    # These are read-only but still require same-origin enforcement
    GET_DATA_PATHS = {"/v1/chat/stream", "/api/runs/"}

    def __init__(self, app):
        super().__init__(app)
        self._allowed_origins: Set[str] = set()

    def _get_allowed_origins(self) -> Set[str]:
        """Lazy load allowed origins from settings."""
        if not self._allowed_origins:
            from backend.config import get_settings
            settings = get_settings()
            self._allowed_origins = set(settings.cors_origins_list)
        return self._allowed_origins

    def _check_origin_validation(
        self,
        request: Request,
        settings,
        session_cookie: str,
    ) -> Response | None:
        """Check origin validation for authenticated requests.
        
        Returns a Response if validation fails, None if it passes.
        """
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        allowed_origins = self._get_allowed_origins()
        request_origin = origin or referer

        # For authenticated cookie requests, require valid origin/referer
        if not request_origin:
            logger.warning(
                "Missing Origin/Referer for authenticated request",
                data={"path": request.url.path},
            )
            return Response(
                content='{"detail": "Origin validation failed", "error": {"code": "E2004", "message": "Missing Origin/Referer header"}}',
                status_code=403,
                media_type="application/json",
            )

        # Extract origin from referer (remove path)
        check_origin = origin
        if not check_origin and referer:
            referer_parsed = _parse_origin(referer)
            if referer_parsed:
                check_origin = f"{referer_parsed[0]}://{referer_parsed[1]}:{referer_parsed[2]}"

        if check_origin and allowed_origins:
            if not _is_origin_allowed(check_origin, allowed_origins):
                logger.warning(
                    "Origin validation failed",
                    data={"origin": origin, "referer": referer, "path": request.url.path},
                )
                return Response(
                    content='{"detail": "Origin not allowed", "error": {"code": "E2003", "message": "Origin validation failed"}}',
                    status_code=403,
                    media_type="application/json",
                )

        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate CSRF token and origin for state-changing requests."""
        from backend.config import get_settings

        settings = get_settings()

        # Check if this is a GET request to a data endpoint that needs origin validation
        if request.method in self.SAFE_METHODS:
            # Even GET requests to streaming endpoints require origin validation
            # when they carry session cookies (defense-in-depth)
            path = request.url.path
            needs_origin_check = (
                path.startswith("/v1/chat/stream") or 
                path.startswith("/api/runs/")
            )
            if needs_origin_check:
                session_cookie = request.cookies.get(settings.session_cookie_name)
                if session_cookie:
                    # Validate origin for authenticated GET requests
                    origin_response = self._check_origin_validation(request, settings, session_cookie)
                    if origin_response:
                        return origin_response
            return await call_next(request)

        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # For API endpoints, check CSRF header matches cookie when session cookie is present
        if request.url.path.startswith(("/api/", "/v1/")):
            session_cookie = request.cookies.get(settings.session_cookie_name)
            if not session_cookie:
                return await call_next(request)

            # Origin validation for cross-site request forgery protection
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            allowed_origins = self._get_allowed_origins()

            # Determine the request's effective origin
            request_origin = origin or referer

            # For authenticated cookie requests, require valid origin/referer
            # With Referrer-Policy: no-referrer, browsers may drop Referer
            # Fail closed: reject authenticated requests without origin info
            if not request_origin:
                logger.warning(
                    "Missing Origin/Referer for authenticated request",
                    data={"path": request.url.path},
                )
                return Response(
                    content='{"detail": "Origin validation failed", "error": {"code": "E2004", "message": "Missing Origin/Referer header"}}',
                    status_code=403,
                    media_type="application/json",
                )

            # Extract origin from referer (remove path)
            check_origin = origin
            if not check_origin and referer:
                # Remove path from referer to get just origin
                referer_parsed = _parse_origin(referer)
                if referer_parsed:
                    check_origin = f"{referer_parsed[0]}://{referer_parsed[1]}:{referer_parsed[2]}"

            if check_origin and allowed_origins:
                if not _is_origin_allowed(check_origin, allowed_origins):
                    logger.warning(
                        "Origin validation failed",
                        data={"origin": origin, "referer": referer, "path": request.url.path},
                    )
                    return Response(
                        content='{"detail": "Origin not allowed", "error": {"code": "E2003", "message": "Origin validation failed"}}',
                        status_code=403,
                        media_type="application/json",
                    )

            # Validate session before enforcing CSRF
            session = None
            db = None
            try:
                from backend.auth.session import validate_session
                from backend.db.database import get_session_local

                SessionLocal = get_session_local()
                db = SessionLocal()
                session = validate_session(db, session_cookie)
            finally:
                if db is not None:
                    db.close()

            if not session:
                return await call_next(request)

            csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
            csrf_header = request.headers.get(settings.csrf_header_name)

            # If session cookie exists, CSRF cookie and header must exist and match
            if (
                not csrf_cookie
                or not csrf_header
                or csrf_cookie != csrf_header
                or csrf_cookie != session.csrf_token
            ):
                logger.warning(
                    "CSRF validation failed",
                    data={"path": request.url.path},
                )
                return Response(
                    content='{"detail": "CSRF validation failed", "error": {"code": "E2002", "message": "CSRF validation failed"}}',
                    status_code=403,
                    media_type="application/json",
                )

        return await call_next(request)
