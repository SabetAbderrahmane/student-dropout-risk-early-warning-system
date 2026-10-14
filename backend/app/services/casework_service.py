from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.casework import (
    FollowUp,
    FollowUpStatus,
    Intervention,
    InterventionNote,
    InterventionStatus,
)
from app.models.student import Student
from app.models.user import User, UserRole
from app.models.warning import Warning, WarningReviewState
from app.repositories.casework_repository import CaseworkRepository
from app.repositories.user_repository import UserRepository
from app.schemas.casework import (
    AdvisorSummary,
    CancellationRequest,
    EffectiveFollowUpStatus,
    FollowUpComplete,
    FollowUpCreate,
    FollowUpPage,
    FollowUpRecovery,
    FollowUpRow,
    FollowUpUpdate,
    InterventionComplete,
    InterventionCreate,
    InterventionDetail,
    InterventionNoteCreate,
    InterventionNoteResponse,
    InterventionPage,
    InterventionRow,
    InterventionTransfer,
    InterventionUpdate,
    StudentSummary,
    WarningLink,
)
from app.services.casework_mutation import CASEWORK_ROLES, guarded


class CaseworkService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CaseworkRepository(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def effective_status(follow_up: FollowUp, now: datetime) -> EffectiveFollowUpStatus:
        if follow_up.status == FollowUpStatus.COMPLETED:
            return EffectiveFollowUpStatus.COMPLETED
        if follow_up.status == FollowUpStatus.CANCELLED:
            return EffectiveFollowUpStatus.CANCELLED
        scheduled = follow_up.scheduled_for
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=UTC)
        start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        if scheduled < start:
            return EffectiveFollowUpStatus.OVERDUE
        if scheduled < start + timedelta(days=1):
            return EffectiveFollowUpStatus.DUE
        return EffectiveFollowUpStatus.SCHEDULED

    def _advisor(self, user_id: UUID, code: str) -> User:
        user = UserRepository(self.db).lock_by_id(user_id)
        if user is None or not user.is_active or user.role != UserRole.ACADEMIC_ADVISOR:
            raise ApplicationError(
                422, code, "The assignee must be an active Academic Advisor."
            )
        return user

    @staticmethod
    def _intervention_owner(intervention: Intervention, actor: User) -> None:
        if actor.role == UserRole.ACADEMIC_ADMIN:
            return
        if (
            actor.role != UserRole.ACADEMIC_ADVISOR
            or intervention.assigned_to != actor.id
        ):
            raise ApplicationError(
                403,
                "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
                "Only the assigned advisor may change this case.",
            )

    @staticmethod
    def _follow_up_owner(follow_up: FollowUp, actor: User) -> None:
        if actor.role == UserRole.ACADEMIC_ADMIN:
            return
        if (
            actor.role != UserRole.ACADEMIC_ADVISOR
            or follow_up.assigned_to != actor.id
            or follow_up.intervention.assigned_to != actor.id
        ):
            raise ApplicationError(
                403,
                "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR",
                "Only the assigned case and follow-up advisor may change this follow-up.",
            )

    def _intervention(
        self, intervention_id: UUID, *, lock: bool = False
    ) -> Intervention:
        intervention = self.repository.intervention(intervention_id, lock=lock)
        if intervention is None:
            raise ApplicationError(
                404,
                "INTERVENTION_NOT_FOUND",
                "The requested intervention does not exist.",
            )
        return intervention

    def _follow_up(self, follow_up_id: UUID, *, lock: bool = False) -> FollowUp:
        follow_up = self.repository.follow_up(follow_up_id, lock=lock)
        if follow_up is None:
            raise ApplicationError(
                404, "FOLLOW_UP_NOT_FOUND", "The requested follow-up does not exist."
            )
        return follow_up

    @staticmethod
    def _note_row(note: InterventionNote) -> InterventionNoteResponse:
        return InterventionNoteResponse(
            id=note.id,
            intervention_id=note.intervention_id,
            author_id=note.author_id,
            author_name=note.author.full_name,
            note=note.note,
            created_at=note.created_at,
        )

    def _follow_up_row(self, follow_up: FollowUp, now: datetime) -> FollowUpRow:
        student = follow_up.student
        return FollowUpRow(
            id=follow_up.id,
            revision=follow_up.revision,
            parent_status=follow_up.intervention.status,
            parent_assigned_to=follow_up.intervention.assigned_to,
            integrity_issues=self._integrity_issues(follow_up),
            intervention_id=follow_up.intervention_id,
            warning_id=follow_up.intervention.warning_id,
            prediction_id=follow_up.intervention.warning.prediction_id,
            student=StudentSummary(
                id=student.id, student_number=student.student_number, name=student.name
            ),
            assigned_advisor=AdvisorSummary(
                id=follow_up.assignee.id, full_name=follow_up.assignee.full_name
            ),
            scheduled_for=follow_up.scheduled_for,
            method=follow_up.method,
            purpose=follow_up.purpose,
            stored_status=follow_up.status,
            status=self.effective_status(follow_up, now),
            effective_status=self.effective_status(follow_up, now),
            outcome=follow_up.outcome,
            notes=follow_up.notes,
            completed_at=follow_up.completed_at,
            created_by=follow_up.created_by,
            created_at=follow_up.created_at,
            updated_at=follow_up.updated_at,
        )

    @staticmethod
    def _intervention_row(intervention: Intervention) -> InterventionRow:
        student = intervention.student
        warning = intervention.warning
        return InterventionRow(
            id=intervention.id,
            revision=intervention.revision,
            student=StudentSummary(
                id=student.id, student_number=student.student_number, name=student.name
            ),
            warning=WarningLink(
                id=warning.id,
                prediction_id=warning.prediction_id,
                review_state=warning.review_state,
            ),
            type=intervention.type,
            title=intervention.title,
            description=intervention.description,
            priority=intervention.priority,
            status=intervention.status,
            assigned_advisor=AdvisorSummary(
                id=intervention.assignee.id, full_name=intervention.assignee.full_name
            ),
            start_date=intervention.start_date,
            target_date=intervention.target_date,
            completed_at=intervention.completed_at,
            completion_outcome=intervention.completion_outcome,
            completion_notes=intervention.completion_notes,
            created_by=intervention.created_by,
            created_at=intervention.created_at,
            updated_at=intervention.updated_at,
        )

    def intervention_detail(self, intervention_id: UUID) -> InterventionDetail:
        intervention = self._intervention(intervention_id)
        row = self._intervention_row(intervention).model_dump()
        now = self._now()
        # Populate each follow-up's linked intervention/assignee for the detail response.
        follow_ups = [self._follow_up(item.id) for item in intervention.follow_ups]
        return InterventionDetail(
            **row,
            notes=[
                self._note_row(n)
                for n in sorted(
                    intervention.intervention_notes,
                    key=lambda n: (n.created_at, n.id),
                    reverse=True,
                )
            ],
            follow_ups=[self._follow_up_row(item, now) for item in follow_ups],
        )

    def list_interventions(self, **kwargs) -> InterventionPage:
        rows, total = self.repository.list_interventions(**kwargs)
        return InterventionPage.create(
            [self._intervention_row(row) for row in rows],
            kwargs["page"],
            kwargs["page_size"],
            total,
        )

    def student_interventions(
        self, student_id: UUID, *, page: int, page_size: int
    ) -> InterventionPage:
        if self.db.get(Student, student_id) is None:
            raise ApplicationError(
                404, "STUDENT_NOT_FOUND", "The requested student does not exist."
            )
        return self.list_interventions(
            page=page,
            page_size=page_size,
            search=None,
            status=None,
            priority=None,
            type=None,
            assigned_to=None,
            student_id=student_id,
            warning_id=None,
            sort="created_at",
            order="desc",
        )

    @guarded(*CASEWORK_ROLES)
    def create_intervention(
        self, payload: InterventionCreate, actor: User
    ) -> InterventionDetail:
        warning = self.db.scalar(
            select(Warning)
            .where(Warning.id == payload.warning_id)
            .with_for_update(of=Warning)
        )
        if warning is None:
            raise ApplicationError(
                404, "WARNING_NOT_FOUND", "The requested warning does not exist."
            )
        if warning.student_id != payload.student_id:
            raise ApplicationError(
                409,
                "INTERVENTION_WARNING_STUDENT_MISMATCH",
                "Warning and student must match.",
            )
        if warning.review_state != WarningReviewState.CONFIRMED:
            raise ApplicationError(
                409,
                "INTERVENTION_REQUIRES_CONFIRMED_WARNING",
                "A warning must be confirmed before creating an intervention.",
            )
        if actor.role == UserRole.ACADEMIC_ADVISOR and warning.assigned_to != actor.id:
            raise ApplicationError(
                403,
                "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
                "Only the warning's assigned advisor may create this case.",
            )
        self._advisor(payload.assigned_to, "INVALID_INTERVENTION_ASSIGNEE")
        if actor.role == UserRole.ACADEMIC_ADVISOR and payload.assigned_to != actor.id:
            raise ApplicationError(
                403,
                "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
                "An advisor may create only a case assigned to them.",
            )
        intervention = Intervention(
            **payload.model_dump(),
            created_by=actor.id,
            status=InterventionStatus.PLANNED,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.db.add(intervention)
        self._mutation.commit()
        return self.intervention_detail(intervention.id)

    @guarded(*CASEWORK_ROLES)
    def update_intervention(
        self, intervention_id: UUID, payload: InterventionUpdate, actor: User
    ) -> InterventionDetail:
        intervention = self._intervention(intervention_id, lock=True)
        self._intervention_owner(intervention, actor)
        if intervention.status in (
            InterventionStatus.COMPLETED,
            InterventionStatus.CANCELLED,
        ):
            raise ApplicationError(
                409,
                "INVALID_INTERVENTION_TRANSITION",
                "Terminal interventions cannot be changed.",
            )
        fields = payload.model_fields_set
        if "assigned_to" in fields:
            if (
                actor.role != UserRole.ACADEMIC_ADMIN
                and payload.assigned_to != actor.id
            ):
                raise ApplicationError(
                    403,
                    "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
                    "Only Academic Admin may transfer a case.",
                )
            raise ApplicationError(
                409,
                "EXPLICIT_TRANSFER_REQUIRED",
                "Use the reasoned intervention transfer action.",
            )
        if "status" in fields:
            allowed = {
                InterventionStatus.PLANNED: {InterventionStatus.IN_PROGRESS},
                InterventionStatus.IN_PROGRESS: {InterventionStatus.ACTION_REQUIRED},
                InterventionStatus.ACTION_REQUIRED: {InterventionStatus.IN_PROGRESS},
            }
            if payload.status not in allowed[intervention.status]:
                raise ApplicationError(
                    409,
                    "INVALID_INTERVENTION_TRANSITION",
                    "Use an allowed transition or the dedicated completion/cancellation endpoint.",
                )
            intervention.status = payload.status
        for field in ("title", "description", "priority"):
            if field in fields:
                value = getattr(payload, field)
                if value is None:
                    raise ApplicationError(
                        422,
                        "INVALID_INTERVENTION_TRANSITION",
                        f"{field} cannot be null.",
                    )
                setattr(intervention, field, value)
        if "target_date" in fields:
            if (
                payload.target_date is not None
                and payload.target_date < intervention.start_date
            ):
                raise ApplicationError(
                    422,
                    "INVALID_INTERVENTION_TRANSITION",
                    "Target date cannot precede start date.",
                )
            intervention.target_date = payload.target_date
        intervention.updated_at = self._now()
        self._mutation.commit()
        return self.intervention_detail(intervention_id)

    @guarded(*CASEWORK_ROLES)
    def add_note(
        self, intervention_id: UUID, payload: InterventionNoteCreate, actor: User
    ) -> InterventionNoteResponse:
        intervention = self._intervention(intervention_id, lock=True)
        self._intervention_owner(intervention, actor)
        note = InterventionNote(
            intervention_id=intervention_id,
            author_id=actor.id,
            note=payload.note,
            created_at=self._now(),
        )
        self.db.add(note)
        self._mutation.commit()
        return self._note_row(note)

    def list_notes(self, intervention_id: UUID) -> list[InterventionNoteResponse]:
        intervention = self._intervention(intervention_id)
        return [
            self._note_row(note)
            for note in sorted(
                intervention.intervention_notes,
                key=lambda n: (n.created_at, n.id),
                reverse=True,
            )
        ]

    @guarded(*CASEWORK_ROLES)
    def complete_intervention(
        self, intervention_id: UUID, payload: InterventionComplete, actor: User
    ) -> InterventionDetail:
        intervention = self._intervention(intervention_id, lock=True)
        self._intervention_owner(intervention, actor)
        if intervention.status in (
            InterventionStatus.COMPLETED,
            InterventionStatus.CANCELLED,
        ):
            raise ApplicationError(
                409,
                "INVALID_INTERVENTION_TRANSITION",
                "This intervention is already terminal.",
            )
        self._closure_gate(intervention)
        intervention.status = InterventionStatus.COMPLETED
        intervention.completed_at = self._now()
        intervention.completion_outcome = payload.outcome
        intervention.completion_notes = payload.completion_notes
        intervention.updated_at = self._now()
        self._mutation.commit()
        return self.intervention_detail(intervention_id)

    @guarded(*CASEWORK_ROLES)
    def cancel_intervention(
        self, intervention_id: UUID, payload: CancellationRequest, actor: User
    ) -> InterventionDetail:
        intervention = self._intervention(intervention_id, lock=True)
        self._intervention_owner(intervention, actor)
        if intervention.status in (
            InterventionStatus.COMPLETED,
            InterventionStatus.CANCELLED,
        ):
            raise ApplicationError(
                409,
                "INVALID_INTERVENTION_TRANSITION",
                "This intervention is already terminal.",
            )
        self._closure_gate(intervention)
        intervention.status = InterventionStatus.CANCELLED
        intervention.completion_notes = payload.reason
        intervention.updated_at = self._now()
        self._mutation.commit()
        return self.intervention_detail(intervention_id)

    def follow_up_detail(self, follow_up_id: UUID) -> FollowUpRow:
        return self._follow_up_row(self._follow_up(follow_up_id), self._now())

    def list_follow_ups(self, **kwargs) -> FollowUpPage:
        now = self._now()
        rows, total = self.repository.list_follow_ups(**kwargs, now=now)
        return FollowUpPage.create(
            [self._follow_up_row(row, now) for row in rows],
            kwargs["page"],
            kwargs["page_size"],
            total,
        )

    def intervention_follow_ups(
        self, intervention_id: UUID, *, page: int, page_size: int
    ) -> FollowUpPage:
        self._intervention(intervention_id)
        return self.list_follow_ups(
            page=page,
            page_size=page_size,
            status=None,
            assigned_to=None,
            student_id=None,
            intervention_id=intervention_id,
            from_date=None,
            to_date=None,
            search=None,
            sort="scheduled_for",
            order="desc",
        )

    @guarded(*CASEWORK_ROLES)
    def create_follow_up(
        self, intervention_id: UUID, payload: FollowUpCreate, actor: User
    ) -> FollowUpRow:
        intervention = self._intervention(intervention_id, lock=True)
        self._intervention_owner(intervention, actor)
        self._scheduling_gate(intervention)
        self._advisor(payload.assigned_to, "INVALID_FOLLOW_UP_ASSIGNEE")
        if payload.assigned_to != intervention.assigned_to:
            raise ApplicationError(
                409,
                "INDEPENDENT_FOLLOW_UP_DELEGATION",
                "Scheduled follow-ups must use the intervention owner.",
            )
        self._advisor(intervention.assigned_to, "INVALID_FOLLOW_UP_ASSIGNEE")
        follow_up = FollowUp(
            intervention_id=intervention.id,
            student_id=intervention.student_id,
            assigned_to=payload.assigned_to,
            scheduled_for=payload.scheduled_for,
            method=payload.method,
            purpose=payload.purpose,
            status=FollowUpStatus.SCHEDULED,
            created_by=actor.id,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.db.add(follow_up)
        self._mutation.commit()
        return self.follow_up_detail(follow_up.id)

    @guarded(*CASEWORK_ROLES)
    def update_follow_up(
        self, follow_up_id: UUID, payload: FollowUpUpdate, actor: User
    ) -> FollowUpRow:
        follow_up = self._follow_up(follow_up_id, lock=True)
        self._follow_up_owner(follow_up, actor)
        self._regular_child_gate(follow_up)
        if follow_up.status != FollowUpStatus.SCHEDULED:
            raise ApplicationError(
                409,
                "INVALID_FOLLOW_UP_TRANSITION",
                "Only scheduled follow-ups may be changed.",
            )
        fields = payload.model_fields_set
        for field in ("scheduled_for", "method", "purpose"):
            if field in fields:
                value = getattr(payload, field)
                if value is None:
                    raise ApplicationError(
                        422, "INVALID_FOLLOW_UP_TRANSITION", f"{field} cannot be null."
                    )
                setattr(follow_up, field, value)
        if "assigned_to" in fields:
            if (
                actor.role != UserRole.ACADEMIC_ADMIN
                and payload.assigned_to != actor.id
            ):
                raise ApplicationError(
                    403,
                    "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR",
                    "Independent delegation is forbidden.",
                )
            raise ApplicationError(
                409,
                "EXPLICIT_RECOVERY_REQUIRED",
                "Use transfer or the explicit integrity recovery action.",
            )
        follow_up.updated_at = self._now()
        self._mutation.commit()
        return self.follow_up_detail(follow_up_id)

    @guarded(*CASEWORK_ROLES)
    def complete_follow_up(
        self, follow_up_id: UUID, payload: FollowUpComplete, actor: User
    ) -> FollowUpRow:
        follow_up = self._follow_up(follow_up_id, lock=True)
        self._follow_up_owner(follow_up, actor)
        if payload.next_follow_up_at is not None:
            self._scheduling_gate(follow_up.intervention)
        self._regular_child_gate(follow_up)
        if follow_up.status != FollowUpStatus.SCHEDULED:
            raise ApplicationError(
                409,
                "INVALID_FOLLOW_UP_TRANSITION",
                "This follow-up is already terminal.",
            )
        if payload.next_follow_up_at is not None:
            self._scheduling_gate(follow_up.intervention)
            self._advisor(
                follow_up.intervention.assigned_to, "INVALID_FOLLOW_UP_ASSIGNEE"
            )
        follow_up.status = FollowUpStatus.COMPLETED
        follow_up.outcome = payload.outcome
        follow_up.notes = payload.notes
        follow_up.completed_at = self._now()
        follow_up.updated_at = self._now()
        if payload.next_follow_up_at is not None:
            self.db.add(
                FollowUp(
                    intervention_id=follow_up.intervention_id,
                    student_id=follow_up.student_id,
                    assigned_to=follow_up.assigned_to,
                    scheduled_for=payload.next_follow_up_at,
                    method=follow_up.method,
                    purpose=follow_up.purpose,
                    status=FollowUpStatus.SCHEDULED,
                    created_by=actor.id,
                    created_at=self._now(),
                    updated_at=self._now(),
                )
            )
        try:
            self._mutation.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.follow_up_detail(follow_up_id)

    @guarded(*CASEWORK_ROLES)
    def cancel_follow_up(
        self, follow_up_id: UUID, payload: CancellationRequest, actor: User
    ) -> FollowUpRow:
        follow_up = self._follow_up(follow_up_id, lock=True)
        self._follow_up_owner(follow_up, actor)
        self._regular_child_gate(follow_up)
        if follow_up.status != FollowUpStatus.SCHEDULED:
            raise ApplicationError(
                409,
                "INVALID_FOLLOW_UP_TRANSITION",
                "This follow-up is already terminal.",
            )
        follow_up.status = FollowUpStatus.CANCELLED
        follow_up.notes = payload.reason
        follow_up.updated_at = self._now()
        self._mutation.commit()
        return self.follow_up_detail(follow_up_id)

    @staticmethod
    def _integrity_issues(follow_up: FollowUp) -> list[str]:
        if follow_up.status != FollowUpStatus.SCHEDULED:
            return []
        issues = []
        if follow_up.assigned_to != follow_up.intervention.assigned_to:
            issues.append("OWNER_MISMATCH")
        if follow_up.intervention.status in (
            InterventionStatus.COMPLETED,
            InterventionStatus.CANCELLED,
        ):
            issues.append("TERMINAL_PARENT")
        return issues

    @staticmethod
    def _scheduling_gate(intervention: Intervention) -> None:
        if intervention.status in (
            InterventionStatus.COMPLETED,
            InterventionStatus.CANCELLED,
        ):
            raise ApplicationError(
                409,
                "INVALID_FOLLOW_UP_TRANSITION",
                "Terminal interventions cannot receive follow-ups or successors.",
            )

    def _regular_child_gate(self, follow_up: FollowUp) -> None:
        issues = self._integrity_issues(follow_up)
        if issues:
            raise ApplicationError(
                409,
                "CASEWORK_RECOVERY_REQUIRED",
                "Academic Admin must explicitly recover this historical obligation.",
                {"issues": issues, "follow_up_id": str(follow_up.id)},
            )

    def _closure_gate(self, intervention: Intervention) -> None:
        ids = list(
            self.db.scalars(
                select(FollowUp.id)
                .where(
                    FollowUp.intervention_id == intervention.id,
                    FollowUp.status == FollowUpStatus.SCHEDULED,
                )
                .order_by(FollowUp.id)
            )
        )
        if ids:
            raise ApplicationError(
                409,
                "INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS",
                "Complete or cancel scheduled follow-ups before closing the intervention.",
                {"follow_ups": len(ids), "follow_up_ids": [str(item) for item in ids]},
            )

    @guarded(UserRole.ACADEMIC_ADMIN)
    def transfer_intervention(
        self, intervention_id: UUID, payload: InterventionTransfer, actor: User
    ) -> InterventionDetail:
        intervention = self._intervention(intervention_id, lock=True)
        self._scheduling_gate(intervention)
        self._advisor(payload.assigned_to, "INVALID_INTERVENTION_ASSIGNEE")
        if intervention.assigned_to == payload.assigned_to:
            raise ApplicationError(
                409,
                "INTERVENTION_ALREADY_ASSIGNED",
                "The selected advisor already owns this intervention.",
            )
        intervention.assigned_to = payload.assigned_to
        intervention.updated_at = self._now()
        children = list(
            self.db.scalars(
                select(FollowUp)
                .where(
                    FollowUp.intervention_id == intervention.id,
                    FollowUp.status == FollowUpStatus.SCHEDULED,
                )
                .order_by(FollowUp.id)
                .with_for_update()
            )
        )
        for child in children:
            child.assigned_to = payload.assigned_to
            child.updated_at = self._now()
        self._mutation.commit()
        return self.intervention_detail(intervention_id)

    @guarded(UserRole.ACADEMIC_ADMIN)
    def recover_follow_up(
        self, follow_up_id: UUID, payload: FollowUpRecovery, actor: User
    ) -> FollowUpRow:
        follow_up = self._follow_up(follow_up_id, lock=True)
        issues = self._integrity_issues(follow_up)
        if not issues:
            raise ApplicationError(
                409,
                "NO_CASEWORK_INCONSISTENCY",
                "This record does not require integrity recovery.",
            )
        if payload.action == "ALIGN":
            self._scheduling_gate(follow_up.intervention)
            self._advisor(
                follow_up.intervention.assigned_to, "INVALID_FOLLOW_UP_ASSIGNEE"
            )
            follow_up.assigned_to = follow_up.intervention.assigned_to
        else:
            if "TERMINAL_PARENT" not in issues:
                raise ApplicationError(
                    409,
                    "INVALID_RECOVERY_ACTION",
                    "Align this contact with its nonterminal parent first.",
                )
            if payload.action == "COMPLETE":
                if payload.outcome is None or payload.notes is None:
                    raise ApplicationError(
                        422,
                        "RECOVERY_OUTCOME_REQUIRED",
                        "A genuine outcome and notes are required.",
                    )
                follow_up.status = FollowUpStatus.COMPLETED
                follow_up.outcome = payload.outcome
                follow_up.notes = payload.notes
                follow_up.completed_at = self._now()
            else:
                follow_up.status = FollowUpStatus.CANCELLED
                follow_up.notes = payload.reason
        follow_up.updated_at = self._now()
        self._mutation.commit()
        return self.follow_up_detail(follow_up_id)

    def integrity_diagnostics(self) -> list[FollowUpRow]:
        rows = self.db.scalars(
            select(FollowUp)
            .join(FollowUp.intervention)
            .where(
                FollowUp.status == FollowUpStatus.SCHEDULED,
                (FollowUp.assigned_to != Intervention.assigned_to)
                | Intervention.status.in_(
                    [InterventionStatus.COMPLETED, InterventionStatus.CANCELLED]
                ),
            )
            .order_by(FollowUp.id)
        )
        return [self.follow_up_detail(item.id) for item in rows]
