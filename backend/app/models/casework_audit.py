"""Append-only attributed casework actions; no reconstructed historical events."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CaseworkActionAudit(Base):
    __tablename__ = "casework_action_audit"
    __table_args__ = (
        CheckConstraint(
            "action IN ('ASSIGN', 'REVIEW', 'RECONSIDER', 'CREATE_INTERVENTION', 'UPDATE_INTERVENTION', 'ADD_NOTE', 'COMPLETE_INTERVENTION', 'CANCEL_INTERVENTION', 'CREATE_FOLLOW_UP', 'UPDATE_FOLLOW_UP', 'COMPLETE_FOLLOW_UP', 'CANCEL_FOLLOW_UP', 'TRANSFER_INTERVENTION', 'RECOVER_FOLLOW_UP')",
            name="valid_action",
        ),
        Index("ix_casework_audit_actor_time", "actor_id", "created_at"),
        Index("ix_casework_audit_warning_time", "warning_id", "created_at"),
        Index("ix_casework_audit_intervention_time", "intervention_id", "created_at"),
        Index("ix_casework_audit_follow_up_time", "follow_up_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(80))
    warning_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("warnings.id", ondelete="RESTRICT")
    )
    intervention_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interventions.id", ondelete="RESTRICT")
    )
    follow_up_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("follow_ups.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(String(4000))
    before_values: Mapped[dict] = mapped_column(JSON)
    after_values: Mapped[dict] = mapped_column(JSON)
    correlation_id: Mapped[uuid.UUID] = mapped_column(index=True)
