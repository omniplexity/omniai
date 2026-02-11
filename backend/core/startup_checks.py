"""Production startup configuration checks.

This module that production validates deployments meet security requirements.
Run at application startup when ENVIRONMENT=production.
"""

import logging
from urllib.parse import urlparse
from typing import List

from backend.config import Settings

logger = logging.getLogger(__name__)


class ProductionConfigError(Exception):
    """Raised when production configuration fails validation."""
    pass


def _origin_hostname(origin: str) -> str | None:
    """Return hostname from an origin-like URL, or None if invalid."""
    if not origin:
        return None
    value = origin.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    try:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.hostname:
            return None
        return parsed.hostname.lower()
    except Exception:
        return None


def validate_production_settings(settings: Settings) -> List[str]:
    """Validate production configuration requirements.
    
    Returns a list of error messages (empty if valid).
    This allows collecting all violations before failing.
    
    Args:
        settings: The application settings to validate
        
    Returns:
        List of error messages (empty if valid)
    """
    errors: List[str] = []

    # 1. No wildcard ALLOWED_HOSTS
    for host in settings.allowed_hosts_list:
        if host.startswith("*."):
            errors.append(
                f"Wildcard hosts (*.{host[2:]}) are not allowed in production. "
                "Use exact hostnames."
            )

    # 2. COOKIE_SECURE must be true
    if not settings.cookie_secure:
        errors.append("COOKIE_SECURE must be true in production for secure cookies")

    # 3. COOKIE_SAMESITE=None for cross-site cookies (capitalized for header)
    # Production requires cross-site cookies for GitHub Pages -> API communication
    if settings.cookie_samesite != "none":
        errors.append(
            f"COOKIE_SAMESITE must be 'none' in production for cross-site access "
            f"(current: '{settings.cookie_samesite}')"
        )

    # 4. CORS_ORIGINS must contain required frontend origins
    # Allow override via REQUIRED_FRONTEND_ORIGINS env var
    required_origins_env = settings.required_frontend_origins or ""
    if required_origins_env:
        required_origins = [o.strip() for o in required_origins_env.split(",") if o.strip()]
    else:
        # Default: require GH Pages origin
        required_origins = ["https://omniplexity.github.io"]

    for frontend_origin in required_origins:
        if frontend_origin not in settings.cors_origins_list:
            errors.append(
                f"CORS_ORIGINS must contain '{frontend_origin}' for frontend access"
            )

    # 5. CORS_ORIGINS must not contain wildcard
    if "*" in settings.cors_origins:
        errors.append("CORS_ORIGINS must not contain wildcard '*' in production")

    # 6. CORS_ORIGINS should be https-only in production
    for origin in settings.cors_origins_list:
        if origin.startswith("http://"):
            errors.append(
                f"CORS_ORIGINS must be https-only in production; "
                f"found insecure origin: '{origin}'"
            )

    # 7. Cross-site deployments must use Partitioned cookies (CHIPS).
    # Determine whether frontend origins differ from backend host.
    backend_host = _origin_hostname(settings.public_base_url)
    cross_site_required = False
    if not backend_host:
        # Fail closed to the default architecture (Pages -> API cross-site).
        cross_site_required = True
    else:
        for frontend_origin in required_origins:
            frontend_host = _origin_hostname(frontend_origin)
            if not frontend_host or frontend_host != backend_host:
                cross_site_required = True
                break

    if cross_site_required and not settings.cookie_partitioned:
        errors.append(
            "COOKIE_PARTITIONED must be true for cross-site cookie deployments "
            "(CHIPS required for Pages -> API architecture)"
        )

    return errors


def assert_production_settings(settings: Settings) -> None:
    """Assert production configuration requirements.
    
    Raises ProductionConfigError with details if validation fails.
    This is called at startup in production mode.
    
    Args:
        settings: The application settings to validate
        
    Raises:
        ProductionConfigError: If any validation fails
    """
    errors = validate_production_settings(settings)

    if errors:
        error_msg = "\n".join(f"  - {e}" for e in errors)
        logger.error(
            f"Production configuration validation failed:\n{error_msg}"
        )
        raise ProductionConfigError(
            f"Production configuration errors:\n{error_msg}"
        )

    logger.info("Production configuration validation passed")


def validate_test_settings(settings: Settings) -> List[str]:
    """Validate test environment configuration.
    
    Returns a list of warning messages.
    
    Args:
        settings: The application settings to validate
        
    Returns:
        List of warning messages
    """
    warnings: List[str] = []

    # Test environment should have test database or be isolated
    if settings.database_url.startswith("sqlite://"):
        if "test" not in settings.database_url.lower():
            warnings.append(
                "DATABASE_URL appears to be a non-test SQLite database. "
                "Consider using a separate test database to avoid data corruption."
            )

    return warnings


def run_startup_validations(settings: Settings) -> None:
    """Run all startup validations based on environment.
    
    Args:
        settings: The application settings
    """
    if settings.is_production or settings.is_staging:
        # Production and staging use the same strict validation
        assert_production_settings(settings)
    elif settings.is_test:
        warnings = validate_test_settings(settings)
        for warning in warnings:
            logger.warning(f"Test configuration warning: {warning}")
    else:
        # Development - no strict validation
        pass
