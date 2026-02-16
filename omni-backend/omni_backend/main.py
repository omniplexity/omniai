from __future__ import annotations

import uvicorn

from .app import create_app
from .config import Settings
from .db import Database
from argon2 import PasswordHasher

app = create_app()

PWD = PasswordHasher()


def ensure_admin_user(db: Database) -> None:
    """Create admin user 'Omni' if not exists."""
    ADMIN_USERNAME = "Omni"
    ADMIN_PASSWORD = "OmniAI2026!"  # Change this in production!
    ADMIN_DISPLAY = "Omni AI Admin"
    
    # Check if identity already exists
    existing = db.get_identity_by_username(ADMIN_USERNAME)
    if existing:
        print(f"Admin user '{ADMIN_USERNAME}' already exists")
        return
    
    # Create identity and user
    password_hash = PWD.hash(ADMIN_PASSWORD)
    ident = db.create_identity(ADMIN_USERNAME, password_hash)
    user = db.ensure_user(ident["user_id"], ADMIN_DISPLAY)
    
    print(f"Created admin user '{ADMIN_USERNAME}' with ID: {user['user_id']}")


def main() -> None:
    settings = Settings()
    
    # Create admin user on startup
    db = Database(settings.db_path)
    ensure_admin_user(db)
    
    uvicorn.run("omni_backend.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
