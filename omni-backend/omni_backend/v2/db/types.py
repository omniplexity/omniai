"""Dialect-aware column types for Postgres/SQLite dual support."""

from __future__ import annotations

import uuid

from sqlalchemy import String, types
from sqlalchemy.dialects import postgresql


class GUID(types.TypeDecorator):
    """UUID type: native UUID on Postgres, CHAR(36) on SQLite."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=False))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value)

    @staticmethod
    def new() -> str:
        return str(uuid.uuid4())


class JSONB(types.TypeDecorator):
    """JSONB on Postgres, JSON on SQLite."""

    impl = types.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB)
        return dialect.type_descriptor(types.JSON)
