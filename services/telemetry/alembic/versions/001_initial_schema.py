"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_logs_service", "logs", ["service"])
    op.create_index("ix_logs_timestamp", "logs", ["timestamp"])
    op.create_index("ix_logs_trace_id", "logs", ["trace_id"])

    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_service", "metrics", ["service"])
    op.create_index("ix_metrics_timestamp", "metrics", ["timestamp"])
    op.create_index("ix_metrics_metric_name", "metrics", ["metric_name"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rca_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("postmortem", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("incidents")
    op.drop_index("ix_metrics_metric_name", table_name="metrics")
    op.drop_index("ix_metrics_timestamp", table_name="metrics")
    op.drop_index("ix_metrics_service", table_name="metrics")
    op.drop_table("metrics")
    op.drop_index("ix_logs_trace_id", table_name="logs")
    op.drop_index("ix_logs_timestamp", table_name="logs")
    op.drop_index("ix_logs_service", table_name="logs")
    op.drop_table("logs")
