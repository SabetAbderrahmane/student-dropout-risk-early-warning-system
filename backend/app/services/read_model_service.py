"""Phase 8 read models; no domain state is changed by these queries."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ApplicationError
from app.ml.feature_schema import PREDICTION_FEATURES
from app.ml.inference_features import assemble_prediction_features
from app.ml.outcomes.contracts import ModelTargetType, PredictionStage
from app.models.admission import AdmissionRecord
from app.models.casework import (
    FollowUp,
    FollowUpStatus,
    Intervention,
    InterventionNote,
    InterventionStatus,
)
from app.models.import_job import ImportJob, ImportStatus
from app.models.prediction import ModelVersion, PredictionResult, RiskLevel
from app.models.semester_one import FirstSemesterRecord
from app.models.student import Student
from app.models.user import User
from app.models.warning import Warning, WarningReview, WarningReviewState
from app.schemas.read_models import (
    Advisor,
    AttentionStudent,
    Counts,
    Course,
    DashboardOverview,
    DataFreshness,
    FollowUpCounts,
    InterventionActivity,
    InterventionCounts,
    ModelSummary,
    PredictionSummary,
    ProfileAdmission,
    ProfileFollowUp,
    ProfileIntervention,
    ProfilePrediction,
    ProfileReview,
    ProfileStudent,
    ProfileWarning,
    Readiness,
    RegistryAdmission,
    RegistryIntervention,
    RegistryPage,
    RegistryRow,
    RegistrySemesterOne,
    RegistryWarning,
    RiskCounts,
    SemesterOne,
    StudentProfile,
    TimelineEvent,
    WarningActivity,
    WarningCounts,
)
from app.services.assessment_service import (
    assessment_fields,
    input_changes,
    prediction_metadata,
    projection,
)
from app.services.casework_service import CaseworkService
from app.utils.category_labels import category_label

ACTIVE_STATUSES = (
    InterventionStatus.ACTION_REQUIRED,
    InterventionStatus.IN_PROGRESS,
    InterventionStatus.PLANNED,
)
STATUS_RANK = {status: rank for rank, status in enumerate(ACTIVE_STATUSES)}


def _ready_condition():
    """SQL counterpart of canonical feature assembly, generated from its feature list."""
    tables = {
        "students": Student,
        "admission_records": AdmissionRecord,
        "first_semester_records": FirstSemesterRecord,
    }
    checks = []
    for feature in PREDICTION_FEATURES:
        column = getattr(tables[feature.storage_table], feature.storage_column)
        checks.append(column.is_not(None))
        if feature.allowed_values is not None:
            checks.append(column.in_(feature.allowed_values))
        if feature.minimum is not None:
            checks.append(column >= feature.minimum)
        if feature.maximum is not None:
            checks.append(column <= feature.maximum)
    return and_(*checks)


def _latest_predictions(*, legacy_only=False):
    ranked = select(
        PredictionResult.id.label("id"),
        PredictionResult.student_id.label("student_id"),
        PredictionResult.risk_level.label("risk_level"),
        PredictionResult.probability.label("probability"),
        PredictionResult.predicted_at.label("predicted_at"),
        func.row_number()
        .over(
            partition_by=PredictionResult.student_id,
            order_by=(PredictionResult.predicted_at.desc(), PredictionResult.id.desc()),
        )
        .label("rank"),
    )
    if legacy_only:
        ranked = ranked.where(
            PredictionResult.model_target_type == ModelTargetType.BINARY_DROPOUT,
            PredictionResult.prediction_stage == PredictionStage.FIRST_SEMESTER,
        )
    ranked = ranked.subquery()
    return select(ranked).where(ranked.c.rank == 1).subquery()


def _advisor(user: User | None):
    return Advisor(user_id=user.id, full_name=user.full_name) if user else None


def _rate(record: FirstSemesterRecord):
    # A zero denominator has no meaningful approval rate.
    return (
        record.approved_units / record.enrolled_units
        if record.enrolled_units > 0
        else None
    )


def _semester(record: FirstSemesterRecord):
    return SemesterOne(
        credited_units=record.credited_units,
        enrolled_units=record.enrolled_units,
        evaluations=record.evaluations,
        approved_units=record.approved_units,
        average_grade=float(record.average_grade),
        without_evaluations=record.without_evaluations,
        approval_rate=_rate(record),
    )


def _current_intervention(items: list[Intervention]):
    """Active status (action required, in progress, planned), then newest creation/id."""
    if not items:
        return None
    newest_first = sorted(
        items, key=lambda item: (item.created_at, str(item.id)), reverse=True
    )
    return min(newest_first, key=lambda item: STATUS_RANK.get(item.status, 3))


def _current_interventions():
    status_rank = case(
        (Intervention.status == InterventionStatus.ACTION_REQUIRED, 0),
        (Intervention.status == InterventionStatus.IN_PROGRESS, 1),
        (Intervention.status == InterventionStatus.PLANNED, 2),
        else_=3,
    )
    ranked = select(
        Intervention.id.label("id"),
        Intervention.warning_id.label("warning_id"),
        Intervention.status.label("status"),
        func.row_number()
        .over(
            partition_by=Intervention.warning_id,
            order_by=(
                status_rank,
                Intervention.created_at.desc(),
                Intervention.id.desc(),
            ),
        )
        .label("rank"),
    ).subquery()
    return select(ranked).where(ranked.c.rank == 1).subquery()


def _support_warnings():
    ongoing = (
        select(Intervention.id)
        .where(
            Intervention.warning_id == Warning.id,
            Intervention.status.in_(ACTIVE_STATUSES),
        )
        .exists()
    )
    ranked = select(
        Warning.id.label("id"),
        Warning.student_id.label("student_id"),
        func.row_number()
        .over(
            partition_by=Warning.student_id,
            order_by=(
                case(
                    (ongoing, 0),
                    (Warning.review_state != WarningReviewState.DISMISSED, 1),
                    else_=2,
                ),
                Warning.created_at.desc(),
                Warning.id.desc(),
            ),
        )
        .label("rank"),
    ).subquery()
    return select(ranked).where(ranked.c.rank == 1).subquery()


def _utc_date(db: Session, column):
    if db.get_bind().dialect.name == "postgresql":
        return func.date(func.timezone("UTC", column))
    return func.date(column)


class ReadModelService:
    def __init__(self, db: Session):
        self.db = db

    def dashboard(self, prediction_scope="OPERATIONAL_CURRENT") -> DashboardOverview:
        assessment = projection(self.db)
        legacy = _latest_predictions(legacy_only=True)
        latest = (
            legacy if prediction_scope == "LEGACY_BINARY_FIRST_SEMESTER" else assessment
        )
        ready = _ready_condition()
        total, ready_count = self.db.execute(
            select(
                func.count(Student.id),
                func.coalesce(func.sum(case((ready, 1), else_=0)), 0),
            )
            .outerjoin(AdmissionRecord, AdmissionRecord.student_id == Student.id)
            .outerjoin(
                FirstSemesterRecord, FirstSemesterRecord.student_id == Student.id
            )
        ).one()
        risk_rows = self.db.execute(
            select(latest.c.risk_level, func.count())
            .where(latest.c.risk_level.is_not(None))
            .group_by(latest.c.risk_level)
        ).all()
        risks = {
            str(level.value if hasattr(level, "value") else level).lower(): count
            for level, count in risk_rows
        }
        current, reassessment, absent, historically_assessed, stage_ready = (
            self.db.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case((assessment.c.operational_id.is_not(None), 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case((assessment.c.reassessment_required, 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case((assessment.c.historical_id.is_(None), 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case((assessment.c.historical_id.is_not(None), 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    or_(
                                        assessment.c.enrollment_ready,
                                        assessment.c.first_semester_ready,
                                        assessment.c.legacy_ready,
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                )
            ).one()
        )
        legacy_risks = dict(
            self.db.execute(
                select(legacy.c.risk_level, func.count()).group_by(legacy.c.risk_level)
            ).all()
        )
        warning_rows = dict(
            self.db.execute(
                select(Warning.review_state, func.count()).group_by(
                    Warning.review_state
                )
            ).all()
        )
        intervention_rows = dict(
            self.db.execute(
                select(Intervention.status, func.count()).group_by(Intervention.status)
            ).all()
        )
        now = datetime.now(timezone.utc)
        today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        tomorrow = today + timedelta(days=1)
        due, overdue = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    FollowUp.status == FollowUpStatus.SCHEDULED,
                                    FollowUp.scheduled_for >= today,
                                    FollowUp.scheduled_for < tomorrow,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    FollowUp.status == FollowUpStatus.SCHEDULED,
                                    FollowUp.scheduled_for < today,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
        ).one()
        model = self.db.scalar(
            select(ModelVersion).where(
                ModelVersion.is_active.is_(True),
                ModelVersion.model_target_type == ModelTargetType.BINARY_DROPOUT,
                ModelVersion.prediction_stage == PredictionStage.FIRST_SEMESTER,
            )
        )
        # Only successful imports count; completed_at is when persistence finished.
        last_import = self.db.scalar(
            select(func.max(ImportJob.completed_at)).where(
                ImportJob.status == ImportStatus.IMPORTED
            )
        )
        activity = select(func.max(PredictionResult.predicted_at))
        if prediction_scope == "LEGACY_BINARY_FIRST_SEMESTER":
            activity = activity.where(
                PredictionResult.model_target_type == ModelTargetType.BINARY_DROPOUT
            )
        last_prediction = self.db.scalar(activity)
        warning_counts = WarningCounts(
            active=sum(
                count
                for state, count in warning_rows.items()
                if state != WarningReviewState.DISMISSED
            ),
            pending_review=warning_rows.get(WarningReviewState.PENDING_REVIEW, 0),
            confirmed=warning_rows.get(WarningReviewState.CONFIRMED, 0),
            dismissed=warning_rows.get(WarningReviewState.DISMISSED, 0),
        )
        return DashboardOverview(
            students=Counts(
                total=total,
                prediction_ready=ready_count
                if prediction_scope == "LEGACY_BINARY_FIRST_SEMESTER"
                else stage_ready,
                with_latest_prediction=sum(risks.values())
                if prediction_scope == "LEGACY_BINARY_FIRST_SEMESTER"
                else historically_assessed,
                current_assessed=current,
                reassessment_required=reassessment,
                without_predictions=absent,
            ),
            risk_distribution=RiskCounts(
                **{level: risks.get(level, 0) for level in ("low", "medium", "high")}
            ),
            warnings=warning_counts,
            interventions=InterventionCounts(
                active=sum(intervention_rows.get(s, 0) for s in ACTIVE_STATUSES),
                planned=intervention_rows.get(InterventionStatus.PLANNED, 0),
                in_progress=intervention_rows.get(InterventionStatus.IN_PROGRESS, 0),
                action_required=intervention_rows.get(
                    InterventionStatus.ACTION_REQUIRED, 0
                ),
                completed=intervention_rows.get(InterventionStatus.COMPLETED, 0),
            ),
            follow_ups=FollowUpCounts(due_today=due, overdue=overdue),
            model=ModelSummary(
                version=model.model_version,
                name=model.model_name,
                trained_at=model.trained_at,
                low_threshold=model.low_threshold,
                high_threshold=model.high_threshold,
            )
            if model
            else ModelSummary(),
            data_freshness=DataFreshness(
                last_import_at=last_import, last_prediction_at=last_prediction
            ),
            warning_activity=self._warning_activity(today),
            intervention_activity=self._intervention_activity(today),
            attention_students=self._attention(assessment),
            prediction_scope=prediction_scope,
            legacy_risk_distribution=RiskCounts(
                **{
                    k: legacy_risks.get(RiskLevel(k.upper()), 0)
                    for k in ("low", "medium", "high")
                }
            ),
        )

    def _warning_activity(self, today: datetime):
        start = today - timedelta(days=13)
        created_day = _utc_date(self.db, Warning.created_at)
        reviewed_day = _utc_date(self.db, WarningReview.reviewed_at)
        created = self.db.execute(
            select(created_day, func.count())
            .where(Warning.created_at >= start)
            .group_by(created_day)
        ).all()
        reviewed = self.db.execute(
            select(reviewed_day, WarningReview.decision, func.count())
            .where(WarningReview.reviewed_at >= start)
            .group_by(reviewed_day, WarningReview.decision)
        ).all()
        buckets = defaultdict(lambda: {"created": 0, "confirmed": 0, "dismissed": 0})
        for day, count in created:
            buckets[str(day)[:10]]["created"] = count
        for day, decision, count in reviewed:
            buckets[str(day)[:10]][decision.value.lower()] = count
        return [
            WarningActivity(date=day, **values)
            for day, values in sorted(buckets.items())
        ]

    def _intervention_activity(self, today: datetime):
        start = today - timedelta(days=13)
        created_day = _utc_date(self.db, Intervention.created_at)
        completed_day = _utc_date(self.db, Intervention.completed_at)
        created = self.db.execute(
            select(created_day, func.count())
            .where(Intervention.created_at >= start)
            .group_by(created_day)
        ).all()
        completed = self.db.execute(
            select(completed_day, func.count())
            .where(Intervention.completed_at >= start)
            .group_by(completed_day)
        ).all()
        buckets = defaultdict(lambda: {"created": 0, "completed": 0})
        for day, count in created:
            buckets[str(day)[:10]]["created"] = count
        for day, count in completed:
            buckets[str(day)[:10]]["completed"] = count
        return [
            InterventionActivity(date=day, **values)
            for day, values in sorted(buckets.items())
        ]

    def _attention(self, assessment):
        support = _support_warnings()
        overdue = (
            select(FollowUp.id)
            .where(
                FollowUp.student_id == Student.id,
                FollowUp.status == FollowUpStatus.SCHEDULED,
                FollowUp.scheduled_for < datetime.now(timezone.utc),
            )
            .exists()
        )
        priority = case(
            (assessment.c.risk_level == "HIGH", 0),
            (assessment.c.risk_level == "MEDIUM", 1),
            (assessment.c.reassessment_required, 2),
            else_=3,
        )
        rows = self.db.execute(
            select(
                Student,
                PredictionResult,
                Warning,
                User,
                assessment.c.assessment_status,
                assessment.c.reassessment_required,
            )
            .join(assessment, assessment.c.student_id == Student.id)
            .outerjoin(
                PredictionResult, PredictionResult.id == assessment.c.operational_id
            )
            .outerjoin(support, support.c.student_id == Student.id)
            .outerjoin(Warning, Warning.id == support.c.id)
            .outerjoin(User, User.id == Warning.assigned_to)
            .where(
                or_(
                    assessment.c.risk_level.in_(("HIGH", "MEDIUM")),
                    assessment.c.reassessment_required,
                    overdue,
                )
            )
            .order_by(priority, Student.student_number, Student.id)
            .limit(10)
        ).all()
        return [
            AttentionStudent(
                student_id=student.id,
                student_number=student.student_number,
                name=student.name,
                probability=pred.probability if pred else None,
                risk_level=pred.risk_level.value if pred else None,
                warning_id=warning.id if warning else None,
                priority=warning.priority.value if warning else None,
                review_state=warning.review_state.value if warning else None,
                assigned_advisor=_advisor(owner),
                predicted_at=pred.predicted_at if pred else None,
                top_explanation_factors=(pred.explanation or [])[:3] if pred else [],
                assessment_status=status,
                attention_reason="CURRENT_RISK"
                if pred and pred.risk_level != RiskLevel.LOW
                else "REASSESSMENT_REQUIRED"
                if reassessment
                else "OVERDUE_SUPPORT",
                prediction_stage=pred.prediction_stage if pred else None,
            )
            for student, pred, warning, owner, status, reassessment in rows
        ]

    @staticmethod
    def _prediction_summary(pred, metadata):
        if pred is None:
            return None
        return PredictionSummary(
            id=pred.id,
            probability=pred.probability,
            risk_level=pred.risk_level.value,
            predicted_at=pred.predicted_at,
            prediction_stage=pred.prediction_stage,
            model_target_type=pred.model_target_type,
            predicted_outcome=pred.predicted_outcome,
            class_probabilities=pred.class_probabilities,
            model_version=pred.model_version.model_version,
            **metadata.get(pred.id, {}),
        )

    def registry(
        self,
        *,
        page,
        page_size,
        search,
        course_code,
        risk_level,
        warning_state,
        intervention_state,
        prediction_readiness,
        sort,
        order,
        assessment_state=None,
        prediction_stage=None,
        stage_readiness=None,
        current_risk=None,
    ):
        assessment = projection(self.db)
        support = _support_warnings()
        current_intervention = _current_interventions()
        query = (
            select(Student.id)
            .join(assessment, assessment.c.student_id == Student.id)
            .outerjoin(AdmissionRecord, AdmissionRecord.student_id == Student.id)
            .outerjoin(support, support.c.student_id == Student.id)
            .outerjoin(Warning, Warning.id == support.c.id)
            .outerjoin(
                current_intervention, current_intervention.c.warning_id == Warning.id
            )
        )
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(Student.student_number.ilike(pattern), Student.name.ilike(pattern))
            )
        if course_code is not None:
            query = query.where(AdmissionRecord.course_code == course_code)
        if risk_level is not None or current_risk is not None:
            risk = current_risk or risk_level.value
            query = query.where(
                assessment.c.risk_level.is_(None)
                if risk == "NONE"
                else assessment.c.risk_level == risk
            )
        if assessment_state:
            condition = (
                assessment.c.operational_id.is_not(None)
                if assessment_state == "CURRENT"
                else assessment.c.historical_id.is_(None)
                if assessment_state == "NOT_ASSESSED"
                else assessment.c.reassessment_required
            )
            query = query.where(condition)
        if prediction_stage and not stage_readiness:
            selected_stage = case(
                (assessment.c.operational_id == assessment.c.candidate_2, "ENROLLMENT"),
                (assessment.c.operational_id.is_not(None), "FIRST_SEMESTER"),
                else_=None,
            )
            query = query.where(selected_stage == prediction_stage.value)
        if stage_readiness:
            if prediction_stage is None:
                raise ApplicationError(
                    422,
                    "STAGE_REQUIRED",
                    "Stage readiness filtering requires prediction_stage.",
                )
            stage_ready = (
                assessment.c.enrollment_ready
                if prediction_stage == PredictionStage.ENROLLMENT
                else assessment.c.first_semester_ready
            )
            query = query.where(
                stage_ready if stage_readiness == "READY" else ~stage_ready
            )
        elif prediction_readiness:
            ready = or_(
                assessment.c.enrollment_ready,
                assessment.c.first_semester_ready,
                assessment.c.legacy_ready,
            )
            query = query.where(ready if prediction_readiness == "READY" else ~ready)
        if warning_state == "NONE":
            query = query.where(Warning.id.is_(None))
        elif warning_state:
            query = query.where(
                Warning.review_state == WarningReviewState(warning_state)
            )
        if intervention_state is not None:
            query = query.where(current_intervention.c.status == intervention_state)
        total = (
            self.db.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            )
            or 0
        )
        columns = {
            "student_number": Student.student_number,
            "name": Student.name,
            "risk_probability": assessment.c.probability,
            "updated_at": Student.updated_at,
        }
        column = columns[sort]
        ids = self.db.scalars(
            query.order_by(
                column.asc().nulls_last()
                if order == "asc"
                else column.desc().nulls_last(),
                Student.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        if not ids:
            return RegistryPage.create(
                items=[], page=page, page_size=page_size, total=total
            )
        facts = {
            r["student_id"]: r
            for r in self.db.execute(
                select(assessment).where(assessment.c.student_id.in_(ids))
            ).mappings()
        }
        students = {
            student.id: student
            for student in self.db.scalars(
                select(Student)
                .where(Student.id.in_(ids))
                .options(
                    selectinload(Student.admission_record),
                    selectinload(Student.first_semester_record),
                )
            )
        }
        prediction_ids = {
            value
            for fact in facts.values()
            for value in (fact["operational_id"], fact["historical_id"])
            if value
        }
        predictions = {
            pred.id: pred
            for pred in self.db.scalars(
                select(PredictionResult)
                .where(PredictionResult.id.in_(prediction_ids))
                .options(selectinload(PredictionResult.model_version))
            )
        }
        metadata = prediction_metadata(self.db, prediction_ids, assessment=assessment)
        warnings = {
            warning.student_id: warning
            for warning in self.db.scalars(
                select(Warning)
                .join(support, support.c.id == Warning.id)
                .where(Warning.student_id.in_(ids))
            )
        }
        interventions = {
            item.warning_id: item
            for item in self.db.scalars(
                select(Intervention)
                .join(
                    current_intervention, current_intervention.c.id == Intervention.id
                )
                .where(Intervention.student_id.in_(ids))
            )
        }
        owner_ids = {w.assigned_to for w in warnings.values() if w.assigned_to} | {
            i.assigned_to for i in interventions.values()
        }
        users = {
            user.id: user
            for user in self.db.scalars(select(User).where(User.id.in_(owner_ids)))
        }
        activities = self._last_activities(ids)
        rows = []
        for student_id in ids:
            student, fact = students[student_id], facts[student_id]
            admission, semester = (
                student.admission_record,
                student.first_semester_record,
            )
            historical = self._prediction_summary(
                predictions.get(fact["historical_id"]), metadata
            )
            operational = self._prediction_summary(
                predictions.get(fact["operational_id"]), metadata
            )
            warning = warnings.get(student_id)
            intervention = interventions.get(warning.id) if warning else None
            owner = (
                users.get(
                    intervention.assigned_to
                    if intervention and intervention.status in ACTIVE_STATUSES
                    else warning.assigned_to
                )
                if warning
                else None
            )
            rows.append(
                RegistryRow(
                    student_id=student_id,
                    student_number=student.student_number,
                    name=student.name,
                    course=Course(
                        code=admission.course_code,
                        label=category_label("course", admission.course_code),
                    )
                    if admission and admission.course_code is not None
                    else None,
                    admission=RegistryAdmission(
                        method=admission.admission_method,
                        admission_grade=float(admission.admission_grade),
                    )
                    if admission
                    else None,
                    semester_one=RegistrySemesterOne(
                        average_grade=float(semester.average_grade),
                        enrolled_units=semester.enrolled_units,
                        approved_units=semester.approved_units,
                        approval_rate=_rate(semester),
                    )
                    if semester
                    else None,
                    prediction_readiness="READY"
                    if fact["enrollment_ready"]
                    or fact["first_semester_ready"]
                    or fact["legacy_ready"]
                    else "NOT_READY",
                    latest_prediction=historical,
                    latest_historical_prediction=historical,
                    operational_prediction=operational,
                    warning=RegistryWarning(
                        id=warning.id,
                        state=warning.review_state.value,
                        priority=warning.priority.value,
                    )
                    if warning
                    else None,
                    intervention=RegistryIntervention(
                        id=intervention.id, status=intervention.status.value
                    )
                    if intervention
                    else None,
                    case_owner=_advisor(owner),
                    last_activity_at=activities.get(student_id),
                    **assessment_fields(fact),
                )
            )
        return RegistryPage.create(
            items=rows, page=page, page_size=page_size, total=total
        )

    def _last_activities(self, ids):
        sources = [
            (Student.id, Student.updated_at),
            (PredictionResult.student_id, PredictionResult.predicted_at),
            (Warning.student_id, Warning.created_at),
            (Warning.student_id, Warning.updated_at),
            (Intervention.student_id, Intervention.created_at),
            (Intervention.student_id, Intervention.updated_at),
            (FollowUp.student_id, FollowUp.created_at),
            (FollowUp.student_id, FollowUp.completed_at),
        ]
        selects = [
            select(id_col.label("student_id"), stamp.label("occurred_at")).where(
                id_col.in_(ids), stamp.is_not(None)
            )
            for id_col, stamp in sources
        ]
        selects.append(
            select(Warning.student_id, WarningReview.reviewed_at)
            .join(Warning, Warning.id == WarningReview.warning_id)
            .where(Warning.student_id.in_(ids))
        )
        selects.append(
            select(Intervention.student_id, InterventionNote.created_at)
            .join(Intervention, Intervention.id == InterventionNote.intervention_id)
            .where(Intervention.student_id.in_(ids))
        )
        events = union_all(*selects).subquery()
        return dict(
            self.db.execute(
                select(events.c.student_id, func.max(events.c.occurred_at)).group_by(
                    events.c.student_id
                )
            ).all()
        )

    def profile(self, student_id: UUID) -> StudentProfile:
        assessment = projection(self.db, student_ids=[student_id])
        fact = self.db.execute(select(assessment)).mappings().first()
        s = self.db.scalar(
            select(Student)
            .where(Student.id == student_id)
            .options(
                selectinload(Student.admission_record),
                selectinload(Student.first_semester_record),
            )
        )
        if s is None:
            raise ApplicationError(404, "STUDENT_NOT_FOUND", "Student not found.")
        a, sem = s.admission_record, s.first_semester_record
        assembly = assemble_prediction_features(s)
        predictions = self.db.scalars(
            select(PredictionResult)
            .where(PredictionResult.student_id == student_id)
            .options(selectinload(PredictionResult.model_version))
            .order_by(PredictionResult.predicted_at.desc(), PredictionResult.id.desc())
        ).all()
        warnings = self.db.scalars(
            select(Warning)
            .where(Warning.student_id == student_id)
            .options(selectinload(Warning.reviews))
            .order_by(Warning.created_at.desc(), Warning.id.desc())
        ).all()
        interventions = self.db.scalars(
            select(Intervention)
            .where(Intervention.student_id == student_id)
            .order_by(Intervention.created_at.desc(), Intervention.id.desc())
        ).all()
        follow_ups = self.db.scalars(
            select(FollowUp)
            .where(FollowUp.student_id == student_id)
            .order_by(FollowUp.scheduled_for.desc(), FollowUp.id.desc())
        ).all()
        notes = self.db.scalars(
            select(InterventionNote).where(
                InterventionNote.intervention_id.in_([i.id for i in interventions])
            )
        ).all()
        review_ids = {r.reviewer_id for w in warnings for r in w.reviews}
        user_ids = review_ids | {w.assigned_to for w in warnings if w.assigned_to}
        user_ids |= {i.assigned_to for i in interventions} | {
            f.assigned_to for f in follow_ups
        }
        users = {
            u.id: u for u in self.db.scalars(select(User).where(User.id.in_(user_ids)))
        }
        metadata = prediction_metadata(
            self.db, [p.id for p in predictions], assessment=assessment
        )
        pred_rows = [
            ProfilePrediction(
                id=p.id,
                probability=p.probability,
                risk_level=p.risk_level.value,
                predicted_at=p.predicted_at,
                model_version=p.model_version.model_version,
                explanation=p.explanation or [],
                prediction_stage=p.prediction_stage,
                model_target_type=p.model_target_type,
                predicted_outcome=p.predicted_outcome,
                class_probabilities=p.class_probabilities,
                feature_snapshot=p.feature_snapshot,
                explanation_method=p.model_version.metadata_json.get(
                    "explanation_method"
                ),
                **metadata.get(p.id, {}),
                **input_changes(s, p),
            )
            for p in predictions
        ]
        prediction_by_id = {p.id: p for p in predictions}
        warning_rows = [
            ProfileWarning(
                id=w.id,
                prediction_id=w.prediction_id,
                risk_level=w.risk_level.value,
                priority=w.priority.value,
                review_state=w.review_state.value,
                assigned_advisor=_advisor(users.get(w.assigned_to)),
                prediction_stage=prediction_by_id[w.prediction_id].prediction_stage,
                model_target_type=prediction_by_id[w.prediction_id].model_target_type,
                model_version=prediction_by_id[
                    w.prediction_id
                ].model_version.model_version,
                created_at=w.created_at,
                reviews=[
                    ProfileReview(
                        id=r.id,
                        decision=r.decision.value,
                        note=r.note,
                        reviewer=_advisor(users.get(r.reviewer_id)),
                        reviewed_at=r.reviewed_at,
                    )
                    for r in sorted(
                        w.reviews,
                        key=lambda x: (x.reviewed_at, str(x.id)),
                        reverse=True,
                    )
                ],
            )
            for w in warnings
        ]
        # Current warning belongs to the latest prediction; historical warnings never leak forward.
        current_warning = next(
            (
                w
                for w in warning_rows
                if predictions
                and w.prediction_id == predictions[0].id
                and w.review_state != "DISMISSED"
            ),
            None,
        )
        intervention_rows = [
            ProfileIntervention(
                id=i.id,
                warning_id=i.warning_id,
                type=i.type.value,
                title=i.title,
                priority=i.priority.value,
                status=i.status.value,
                assigned_advisor=_advisor(users.get(i.assigned_to)),
                start_date=i.start_date,
                target_date=i.target_date,
                created_at=i.created_at,
                completed_at=i.completed_at,
                completion_outcome=i.completion_outcome.value
                if i.completion_outcome
                else None,
            )
            for i in interventions
        ]
        now = datetime.now(timezone.utc)
        follow_rows = [
            ProfileFollowUp(
                id=f.id,
                intervention_id=f.intervention_id,
                scheduled_for=f.scheduled_for,
                method=f.method.value,
                purpose=f.purpose,
                effective_status=CaseworkService.effective_status(f, now).value,
                outcome=f.outcome.value if f.outcome else None,
                assigned_advisor=_advisor(users.get(f.assigned_to)),
                completed_at=f.completed_at,
            )
            for f in follow_ups
        ]
        from app.services.outcome_prediction_service import OutcomePredictionService

        stage_service = OutcomePredictionService(self.db)
        return StudentProfile(
            student=ProfileStudent.model_validate(
                {k: getattr(s, k) for k in ProfileStudent.model_fields}
            ),
            admission=ProfileAdmission(
                **{
                    k: (
                        float(getattr(a, k))
                        if getattr(a, k) is not None
                        and k
                        in {
                            "admission_grade",
                            "previous_qualification_grade",
                            "unemployment_rate",
                            "inflation_rate",
                            "gdp",
                        }
                        else getattr(a, k)
                    )
                    for k in ProfileAdmission.model_fields
                    if not k.endswith("_label")
                },
                application_mode_label=category_label(
                    "application_mode", a.application_mode_code
                ),
                course_label=category_label("course", a.course_code),
                previous_qualification_label=category_label(
                    "previous_qualification", a.previous_qualification_code
                ),
            )
            if a
            else None,
            semester_one=_semester(sem) if sem else None,
            prediction_readiness=Readiness(
                status="READY" if assembly.ready else "NOT_READY",
                required_feature_count=len(PREDICTION_FEATURES),
                available_feature_count=len(assembly.values),
                missing_features=list(assembly.missing_features),
            ),
            latest_prediction=pred_rows[0] if pred_rows else None,
            latest_historical_prediction=pred_rows[0] if pred_rows else None,
            operational_prediction=next(
                (p for p in pred_rows if p.id == fact["operational_id"]), None
            ),
            **assessment_fields(fact),
            prediction_history=pred_rows,
            active_warning=current_warning,
            warning_history=warning_rows,
            open_warnings=[w for w in warning_rows if w.review_state != "DISMISSED"],
            interventions=intervention_rows,
            follow_ups=follow_rows,
            timeline=self._timeline(
                predictions, warnings, interventions, notes, follow_ups
            ),
            stage_readiness=[
                stage_service.stage_readiness(student_id, stage)
                for stage in PredictionStage
            ],
        )

    @staticmethod
    def _timeline(predictions, warnings, interventions, notes, follow_ups):
        events = []

        def add(kind, at, title, summary, entity_id):
            if at is not None:
                events.append(
                    TimelineEvent(
                        type=kind,
                        occurred_at=at,
                        title=title,
                        summary=summary,
                        entity_id=entity_id,
                    )
                )

        for p in predictions:
            add(
                "PREDICTION_CREATED",
                p.predicted_at,
                "Prediction created",
                f"{p.prediction_stage.value} · {p.model_target_type.value} · {p.risk_level.value} risk · {p.model_version.model_version}",
                p.id,
            )
        for w in warnings:
            add(
                "WARNING_CREATED",
                w.created_at,
                "Warning created",
                w.priority.value,
                w.id,
            )
            for r in w.reviews:
                add(
                    "WARNING_REVIEWED",
                    r.reviewed_at,
                    "Warning reviewed",
                    r.decision.value,
                    w.id,
                )
        for i in interventions:
            add(
                "INTERVENTION_CREATED",
                i.created_at,
                "Intervention created",
                i.title,
                i.id,
            )
            if i.status == InterventionStatus.COMPLETED:
                add(
                    "INTERVENTION_COMPLETED",
                    i.completed_at,
                    "Intervention completed",
                    i.title,
                    i.id,
                )
            if i.status == InterventionStatus.CANCELLED:
                add(
                    "INTERVENTION_CANCELLED",
                    i.updated_at,
                    "Intervention cancelled",
                    i.title,
                    i.id,
                )
        for n in notes:
            add(
                "INTERVENTION_NOTE_ADDED",
                n.created_at,
                "Intervention note added",
                n.note,
                n.id,
            )
        for f in follow_ups:
            add(
                "FOLLOW_UP_SCHEDULED",
                f.created_at,
                "Follow-up scheduled",
                f.purpose,
                f.id,
            )
            if f.status == FollowUpStatus.COMPLETED:
                add(
                    "FOLLOW_UP_COMPLETED",
                    f.completed_at,
                    "Follow-up completed",
                    f.purpose,
                    f.id,
                )
            if f.status == FollowUpStatus.CANCELLED:
                add(
                    "FOLLOW_UP_CANCELLED",
                    f.updated_at,
                    "Follow-up cancelled",
                    f.purpose,
                    f.id,
                )
        return sorted(
            events,
            key=lambda e: (
                e.occurred_at.replace(tzinfo=timezone.utc)
                if e.occurred_at.tzinfo is None
                else e.occurred_at,
                e.type,
                str(e.entity_id),
            ),
            reverse=True,
        )
