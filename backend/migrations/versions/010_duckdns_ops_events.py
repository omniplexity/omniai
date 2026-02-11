"""add duckdns ops events table

Revision ID: 010_duckdns_ops_events
Revises: 009_workflows
Create Date: 2026-02-11
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "010_duckdns_ops_events"
down_revision = "009_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "duckdns_update_events" in tables:
        return

    op.create_table(
        "duckdns_update_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("subdomain", sa.String(length=128), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("response", sa.String(length=32), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="scheduler"),
    )
    op.create_index("ix_duckdns_events_created_at", "duckdns_update_events", ["created_at"])
    op.create_index("ix_duckdns_events_success", "duckdns_update_events", ["success"])
    op.create_index("ix_duckdns_events_source", "duckdns_update_events", ["source"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "duckdns_update_events" in tables:
        op.drop_table("duckdns_update_events")
