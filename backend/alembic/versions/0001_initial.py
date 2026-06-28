"""initial schema — all entities from data-model.md (T008)

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.Enum("openai_compatible", "anthropic", name="providertype"), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("api_key_ciphertext", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "llm_models",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("llm_providers.id"), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("input_price_per_1m", sa.Numeric, nullable=True),
        sa.Column("output_price_per_1m", sa.Numeric, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_id", "model_name"),
    )
    op.create_table(
        "tools",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_type", sa.Enum("mcp", "skill", "builtin", "browser", "computer", name="toolsourcetype"), nullable=False),
        sa.Column("source_ref", sa.String(512), nullable=True),
        sa.Column("input_schema", sa.JSON, nullable=False),
        sa.Column("risk_level", sa.Enum("none", "sensitive", "destructive", name="risklevel"), nullable=False, server_default="none"),
        sa.Column("auto_run", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("llm_models.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", "system", name="messagerole"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "seq"),
    )
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cron_expr", sa.String(128), nullable=False),
        sa.Column("target_type", sa.Enum("tool", "chat", name="jobtargettype"), nullable=False),
        sa.Column("target_ref", sa.JSON, nullable=False),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("status", sa.Enum("active", "paused", "failed", name="jobstatus"), nullable=False, server_default="active"),
        sa.Column("last_run_at", sa.DateTime, nullable=True),
        sa.Column("last_run_status", sa.Enum("success", "failed", "running", name="runstatus"), nullable=True),
        sa.Column("next_run_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "activity_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=True),
        sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("scheduled_jobs.id"), nullable=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("type", sa.Enum("reasoning", "tool_call", "tool_result", "llm_call", "error", "confirmation_request", "confirmation_result", "progress", name="activitytype"), nullable=False),
        sa.Column("tool_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("tools.id"), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "confirmation_requests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("activity_event_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("activity_events.id"), nullable=False),
        sa.Column("tool_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("action_summary", sa.Text, nullable=False),
        sa.Column("risk_level", sa.Enum("none", "sensitive", "destructive", name="risklevel"), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "declined", "superseded", name="confirmationstatus"), nullable=False, server_default="pending"),
        sa.Column("decided_at", sa.DateTime, nullable=True),
        sa.Column("decided_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_table(
        "browser_computer_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("kind", sa.Enum("browser", "computer", name="sessionkind"), nullable=False),
        sa.Column("profile_dir", sa.String(1024), nullable=False),
        sa.Column("status", sa.Enum("idle", "busy", "closed", name="sessionstatus"), nullable=False, server_default="idle"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for t in (
        "browser_computer_sessions",
        "confirmation_requests",
        "activity_events",
        "messages",
        "scheduled_jobs",
        "chat_sessions",
        "tools",
        "llm_models",
        "llm_providers",
        "users",
    ):
        op.drop_table(t)
