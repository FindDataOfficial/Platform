"""ORM entities — all entities from data-model.md (T016, foundational)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.models.db import Base


def _guid() -> uuid.UUID:
    return uuid.uuid4()


# SQLite-safe JSON type: JSONB on postgres, JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class ProviderType(str, enum.Enum):
    openai_compatible = "openai_compatible"
    anthropic = "anthropic"


class ToolSourceType(str, enum.Enum):
    mcp = "mcp"
    skill = "skill"
    builtin = "builtin"
    browser = "browser"
    computer = "computer"


class RiskLevel(str, enum.Enum):
    none = "none"
    sensitive = "sensitive"
    destructive = "destructive"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ActivityType(str, enum.Enum):
    reasoning = "reasoning"
    tool_call = "tool_call"
    tool_result = "tool_result"
    llm_call = "llm_call"
    error = "error"
    confirmation_request = "confirmation_request"
    confirmation_result = "confirmation_result"
    progress = "progress"


class ConfirmationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    declined = "declined"
    superseded = "superseded"


class SessionKind(str, enum.Enum):
    browser = "browser"
    computer = "computer"


class SessionStatus(str, enum.Enum):
    idle = "idle"
    busy = "busy"
    closed = "closed"


class JobStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    failed = "failed"


class JobTargetType(str, enum.Enum):
    tool = "tool"
    chat = "chat"


class RunStatus(str, enum.Enum):
    success = "success"
    failed = "failed"
    running = "running"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class LlmProvider(Base):
    __tablename__ = "llm_providers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ProviderType] = mapped_column(Enum(ProviderType), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Fernet ciphertext of the API key (research R4). Never sent to frontend.
    api_key_ciphertext: Mapped[bytes] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    models: Mapped[list[LlmModel]] = relationship(back_populates="provider", cascade="all, delete-orphan")


class LlmModel(Base):
    __tablename__ = "llm_models"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_providers.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_price_per_1m: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    output_price_per_1m: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    provider: Mapped[LlmProvider] = relationship(back_populates="models")


class Tool(Base):
    __tablename__ = "tools"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[ToolSourceType] = mapped_column(Enum(ToolSourceType), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(512), nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSONType, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.none, nullable=False)
    auto_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_models.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_jobs.id"), nullable=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), nullable=False)
    tool_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tools.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ConfirmationRequest(Base):
    __tablename__ = "confirmation_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    activity_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("activity_events.id"), nullable=False)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tools.id"), nullable=False)
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False)
    status: Mapped[ConfirmationStatus] = mapped_column(Enum(ConfirmationStatus), default=ConfirmationStatus.pending, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class BrowserComputerSession(Base):
    __tablename__ = "browser_computer_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    kind: Mapped[SessionKind] = mapped_column(Enum(SessionKind), nullable=False)
    profile_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.idle, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_guid)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[JobTargetType] = mapped_column(Enum(JobTargetType), nullable=False)
    target_ref: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.active, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[RunStatus | None] = mapped_column(Enum(RunStatus), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
