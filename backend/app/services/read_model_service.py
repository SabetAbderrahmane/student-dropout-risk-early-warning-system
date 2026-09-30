"""Phase 8 read models; no domain state is changed by these queries."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ApplicationError
from app.ml.feature_schema import PREDICTION_FEATURES
from app.ml.inference_features import assemble_prediction_features
from app.models.admission import AdmissionRecord
from app.models.casework import FollowUp, FollowUpStatus, Intervention, InterventionNote, InterventionStatus
from app.models.import_job import ImportJob, ImportStatus
from app.models.prediction import ModelVersion, PredictionResult, RiskLevel
from app.models.semester_one import FirstSemesterRecord
from app.models.student import Student
from app.models.user import User
from app.models.warning import Warning, WarningReview, WarningReviewState
from app.schemas.read_models import (
    Advisor, AttentionStudent, Counts, Course, DashboardOverview, DataFreshness,
    FollowUpCounts, InterventionActivity, InterventionCounts, ModelSummary,
    PredictionSummary, ProfileAdmission, ProfileFollowUp, ProfileIntervention,
    ProfilePrediction, ProfileReview, ProfileStudent, ProfileWarning, Readiness,
    RegistryAdmission, RegistryIntervention, RegistryPage, RegistryRow,
    RegistrySemesterOne, RegistryWarning, RiskCounts, SemesterOne, StudentProfile,
    TimelineEvent, WarningActivity, WarningCounts,
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
    tables = {"students": Student, "admission_records": AdmissionRecord,
              "first_semester_records": FirstSemesterRecord}
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


def _latest_predictions():
    ranked = select(
        PredictionResult.id.label("id"),
        PredictionResult.student_id.label("student_id"),
        PredictionResult.risk_level.label("risk_level"),
        PredictionResult.probability.label("probability"),
        PredictionResult.predicted_at.label("predicted_at"),
        func.row_number().over(
            partition_by=PredictionResult.student_id,
            order_by=(PredictionResult.predicted_at.desc(), PredictionResult.id.desc()),
        ).label("rank"),
    ).subquery()
    return select(ranked).where(ranked.c.rank == 1).subquery()


def _advisor(user: User | None):
    return Advisor(user_id=user.id, full_name=user.full_name) if user else None


def _rate(record: FirstSemesterRecord):
    # A zero denominator has no meaningful approval rate.
    return record.approved_units / record.enrolled_units if record.enrolled_units > 0 else None


def _semester(record: FirstSemesterRecord):
    return SemesterOne(
        credited_units=record.credited_units, enrolled_units=record.enrolled_units,
        evaluations=record.evaluations, approved_units=record.approved_units,
        average_grade=float(record.average_grade),
        without_evaluations=record.without_evaluations, approval_rate=_rate(record),
    )


def _current_intervention(items: list[Intervention]):
    """Active status (action required, in progress, planned), then newest creation/id."""
    if not items:
        return None
    newest_first = sorted(items, key=lambda item: (item.created_at, str(item.id)), reverse=True)
    return min(newest_first, key=lambda item: STATUS_RANK.get(item.status, 3))


def _current_interventions():
    status_rank = case(
        (Intervention.status == InterventionStatus.ACTION_REQUIRED, 0),
        (Intervention.status == InterventionStatus.IN_PROGRESS, 1),
        (Intervention.status == InterventionStatus.PLANNED, 2), else_=3,
    )
    ranked = select(Intervention.warning_id.label("warning_id"),
        Intervention.status.label("status"),
        func.row_number().over(partition_by=Intervention.warning_id,
            order_by=(status_rank, Intervention.created_at.desc(),
                      Intervention.id.desc())).label("rank")).subquery()
    return select(ranked).where(ranked.c.rank == 1).subquery()


def _utc_date(db: Session, column):
    if db.get_bind().dialect.name == "postgresql":
        return func.date(func.timezone("UTC", column))
    return func.date(column)


class ReadModelService:
    def __init__(self, db: Session):
        self.db = db

    def dashboard(self) -> DashboardOverview:
        latest = _latest_predictions()
        ready = _ready_condition()
        total, ready_count = self.db.execute(
            select(func.count(Student.id), func.coalesce(func.sum(case((ready, 1), else_=0)), 0))
            .outerjoin(AdmissionRecord, AdmissionRecord.student_id == Student.id)
            .outerjoin(FirstSemesterRecord, FirstSemesterRecord.student_id == Student.id)
        ).one()
        risk_rows = self.db.execute(
            select(latest.c.risk_level, func.count()).group_by(latest.c.risk_level)
        ).all()
        risks = {str(level.value if hasattr(level, "value") else level).lower(): count
                 for level, count in risk_rows}
        warning_rows = dict(self.db.execute(
            select(Warning.review_state, func.count()).group_by(Warning.review_state)
        ).all())
        intervention_rows = dict(self.db.execute(
            select(Intervention.status, func.count()).group_by(Intervention.status)
        ).all())
        now = datetime.now(timezone.utc)
        today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        tomorrow = today + timedelta(days=1)
        due, overdue = self.db.execute(select(
            func.coalesce(func.sum(case((and_(FollowUp.status == FollowUpStatus.SCHEDULED,
                FollowUp.scheduled_for >= today, FollowUp.scheduled_for < tomorrow), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(FollowUp.status == FollowUpStatus.SCHEDULED,
                FollowUp.scheduled_for < today), 1), else_=0)), 0),
        )).one()
        model = self.db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
        # Only successful imports count; completed_at is when persistence finished.
        last_import = self.db.scalar(select(func.max(ImportJob.completed_at)).where(
            ImportJob.status == ImportStatus.IMPORTED))
        last_prediction = self.db.scalar(select(func.max(PredictionResult.predicted_at)))
        warning_counts = WarningCounts(
            active=sum(count for state, count in warning_rows.items()
                       if state != WarningReviewState.DISMISSED),
            pending_review=warning_rows.get(WarningReviewState.PENDING_REVIEW, 0),
            confirmed=warning_rows.get(WarningReviewState.CONFIRMED, 0),
            dismissed=warning_rows.get(WarningReviewState.DISMISSED, 0),
        )
        return DashboardOverview(
            students=Counts(total=total, prediction_ready=ready_count,
                            with_latest_prediction=sum(risks.values())),
            risk_distribution=RiskCounts(**{level: risks.get(level, 0)
                                            for level in ("low", "medium", "high")}),
            warnings=warning_counts,
            interventions=InterventionCounts(
                active=sum(intervention_rows.get(s, 0) for s in ACTIVE_STATUSES),
                planned=intervention_rows.get(InterventionStatus.PLANNED, 0),
                in_progress=intervention_rows.get(InterventionStatus.IN_PROGRESS, 0),
                action_required=intervention_rows.get(InterventionStatus.ACTION_REQUIRED, 0),
                completed=intervention_rows.get(InterventionStatus.COMPLETED, 0),
            ),
            follow_ups=FollowUpCounts(due_today=due, overdue=overdue),
            model=ModelSummary(version=model.model_version, name=model.model_name,
                trained_at=model.trained_at, low_threshold=model.low_threshold,
                high_threshold=model.high_threshold) if model else ModelSummary(),
            data_freshness=DataFreshness(last_import_at=last_import,
                                         last_prediction_at=last_prediction),
            warning_activity=self._warning_activity(today),
            intervention_activity=self._intervention_activity(today),
            attention_students=self._attention(latest),
        )

    def _warning_activity(self, today: datetime):
        start = today - timedelta(days=13)
        created_day = _utc_date(self.db, Warning.created_at)
        reviewed_day = _utc_date(self.db, WarningReview.reviewed_at)
        created = self.db.execute(select(created_day, func.count())
            .where(Warning.created_at >= start).group_by(created_day)).all()
        reviewed = self.db.execute(select(reviewed_day,
            WarningReview.decision, func.count()).where(WarningReview.reviewed_at >= start)
            .group_by(reviewed_day, WarningReview.decision)).all()
        buckets = defaultdict(lambda: {"created": 0, "confirmed": 0, "dismissed": 0})
        for day, count in created:
            buckets[str(day)[:10]]["created"] = count
        for day, decision, count in reviewed:
            buckets[str(day)[:10]][decision.value.lower()] = count
        return [WarningActivity(date=day, **values) for day, values in sorted(buckets.items())]

    def _intervention_activity(self, today: datetime):
        start = today - timedelta(days=13)
        created_day = _utc_date(self.db, Intervention.created_at)
        completed_day = _utc_date(self.db, Intervention.completed_at)
        created = self.db.execute(select(created_day, func.count())
            .where(Intervention.created_at >= start)
            .group_by(created_day)).all()
        completed = self.db.execute(select(completed_day, func.count())
            .where(Intervention.completed_at >= start)
            .group_by(completed_day)).all()
        buckets = defaultdict(lambda: {"created": 0, "completed": 0})
        for day, count in created:
            buckets[str(day)[:10]]["created"] = count
        for day, count in completed:
            buckets[str(day)[:10]]["completed"] = count
        return [InterventionActivity(date=day, **values)
                for day, values in sorted(buckets.items())]

    def _attention(self, latest):
        priority = case((Warning.priority == "P1_URGENT", 0),
                        (Warning.priority == "P2_ELEVATED", 1), else_=2)
        pending = case((Warning.review_state == WarningReviewState.PENDING_REVIEW, 0), else_=1)
        rows = self.db.execute(select(Student, PredictionResult, Warning, User)
            .join(latest, latest.c.student_id == Student.id)
            .join(PredictionResult, PredictionResult.id == latest.c.id)
            .join(Warning, Warning.prediction_id == PredictionResult.id)
            .outerjoin(User, User.id == Warning.assigned_to)
            .where(Warning.review_state != WarningReviewState.DISMISSED)
            .order_by(priority, pending, PredictionResult.probability.desc(),
                      Warning.created_at.desc(), Warning.id.desc()).limit(10)).all()
        return [AttentionStudent(student_id=s.id, student_number=s.student_number,
            name=s.name, probability=p.probability, risk_level=p.risk_level.value,
            warning_id=w.id, priority=w.priority.value, review_state=w.review_state.value,
            assigned_advisor=_advisor(u), predicted_at=p.predicted_at,
            top_explanation_factors=(p.explanation or [])[:3]) for s, p, w, u in rows]

    def registry(self, *, page: int, page_size: int, search: str | None,
                 course_code: int | None, risk_level: RiskLevel | None,
                 warning_state: str | None, intervention_state: InterventionStatus | None,
                 prediction_readiness: str | None, sort: str, order: str) -> RegistryPage:
        latest = _latest_predictions()
        current_intervention = _current_interventions()
        query = (select(Student.id).outerjoin(AdmissionRecord, AdmissionRecord.student_id == Student.id)
            .outerjoin(FirstSemesterRecord, FirstSemesterRecord.student_id == Student.id)
            .outerjoin(latest, latest.c.student_id == Student.id)
            .outerjoin(Warning, Warning.prediction_id == latest.c.id)
            .outerjoin(current_intervention,
                       current_intervention.c.warning_id == Warning.id))
        ready = _ready_condition()
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(or_(Student.student_number.ilike(pattern), Student.name.ilike(pattern)))
        if course_code is not None:
            query = query.where(AdmissionRecord.course_code == course_code)
        if risk_level is not None:
            query = query.where(latest.c.risk_level == risk_level)
        if warning_state == "NONE":
            query = query.where(Warning.id.is_(None))
        elif warning_state:
            query = query.where(Warning.review_state == WarningReviewState(warning_state))
        if prediction_readiness:
            query = query.where(ready if prediction_readiness == "READY" else ~ready)
        if intervention_state is not None:
            query = query.where(current_intervention.c.status == intervention_state)
        total = self.db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        sort_columns = {"student_number": Student.student_number, "name": Student.name,
                        "risk_probability": latest.c.probability,
                        "updated_at": Student.updated_at}
        column = sort_columns[sort]
        query = query.order_by(column.asc().nulls_last() if order == "asc" else
                               column.desc().nulls_last(), Student.id.asc())
        ids = self.db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
        if not ids:
            return RegistryPage.create(items=[], page=page, page_size=page_size, total=total)
        students = {s.id: s for s in self.db.scalars(select(Student).where(Student.id.in_(ids))
            .options(selectinload(Student.admission_record),
                     selectinload(Student.first_semester_record))).all()}
        predictions = {p.student_id: p for p in self.db.scalars(
            select(PredictionResult).join(latest, latest.c.id == PredictionResult.id)
            .where(PredictionResult.student_id.in_(ids))).all()}
        warnings = {w.prediction_id: w for w in self.db.scalars(select(Warning)
            .where(Warning.prediction_id.in_([p.id for p in predictions.values()]))).all()}
        interventions = defaultdict(list)
        if warnings:
            for item in self.db.scalars(select(Intervention).where(
                    Intervention.warning_id.in_([w.id for w in warnings.values()]))):
                interventions[item.warning_id].append(item)
        owner_ids = {w.assigned_to for w in warnings.values() if w.assigned_to}
        owner_ids.update(i.assigned_to for group in interventions.values() for i in group)
        users = {u.id: u for u in self.db.scalars(select(User).where(User.id.in_(owner_ids)))}
        activities = self._last_activities(ids)
        rows = []
        for student_id in ids:
            s = students[student_id]
            a, sem = s.admission_record, s.first_semester_record
            p = predictions.get(student_id)
            w = warnings.get(p.id) if p else None
            i = _current_intervention(interventions[w.id]) if w else None
            owner = users.get(i.assigned_to if i and i.status in ACTIVE_STATUSES
                              else w.assigned_to) if w else None
            rows.append(RegistryRow(student_id=s.id, student_number=s.student_number,
                name=s.name,
                course=Course(code=a.course_code, label=category_label("course", a.course_code))
                    if a and a.course_code is not None else None,
                admission=RegistryAdmission(method=a.admission_method,
                    admission_grade=float(a.admission_grade)) if a else None,
                semester_one=RegistrySemesterOne(average_grade=float(sem.average_grade),
                    enrolled_units=sem.enrolled_units, approved_units=sem.approved_units,
                    approval_rate=_rate(sem)) if sem else None,
                prediction_readiness="READY" if assemble_prediction_features(s).ready else "NOT_READY",
                latest_prediction=PredictionSummary(id=p.id, probability=p.probability,
                    risk_level=p.risk_level.value, predicted_at=p.predicted_at) if p else None,
                warning=RegistryWarning(id=w.id, state=w.review_state.value,
                    priority=w.priority.value) if w else None,
                case_owner=_advisor(owner),
                intervention=RegistryIntervention(id=i.id, status=i.status.value) if i else None,
                last_activity_at=activities.get(student_id)))
        return RegistryPage.create(items=rows, page=page, page_size=page_size, total=total)

    def _last_activities(self, ids):
        sources = [(Student.id, Student.updated_at),
                   (PredictionResult.student_id, PredictionResult.predicted_at),
                   (Warning.student_id, Warning.created_at),
                   (Warning.student_id, Warning.updated_at),
                   (Intervention.student_id, Intervention.created_at),
                   (Intervention.student_id, Intervention.updated_at),
                   (FollowUp.student_id, FollowUp.created_at),
                   (FollowUp.student_id, FollowUp.completed_at)]
        selects = [select(id_col.label("student_id"), stamp.label("occurred_at"))
            .where(id_col.in_(ids), stamp.is_not(None)) for id_col, stamp in sources]
        selects.append(select(Warning.student_id, WarningReview.reviewed_at)
            .join(Warning, Warning.id == WarningReview.warning_id)
            .where(Warning.student_id.in_(ids)))
        selects.append(select(Intervention.student_id, InterventionNote.created_at)
            .join(Intervention, Intervention.id == InterventionNote.intervention_id)
            .where(Intervention.student_id.in_(ids)))
        events = union_all(*selects).subquery()
        return dict(self.db.execute(select(events.c.student_id, func.max(events.c.occurred_at))
            .group_by(events.c.student_id)).all())

    def profile(self, student_id: UUID) -> StudentProfile:
        s = self.db.scalar(select(Student).where(Student.id == student_id).options(
            selectinload(Student.admission_record), selectinload(Student.first_semester_record)))
        if s is None:
            raise ApplicationError(404, "STUDENT_NOT_FOUND", "Student not found.")
        a, sem = s.admission_record, s.first_semester_record
        assembly = assemble_prediction_features(s)
        predictions = self.db.scalars(select(PredictionResult).where(
            PredictionResult.student_id == student_id).options(
                selectinload(PredictionResult.model_version))
            .order_by(PredictionResult.predicted_at.desc(), PredictionResult.id.desc())).all()
        warnings = self.db.scalars(select(Warning).where(Warning.student_id == student_id)
            .options(selectinload(Warning.reviews))
            .order_by(Warning.created_at.desc(), Warning.id.desc())).all()
        interventions = self.db.scalars(select(Intervention).where(
            Intervention.student_id == student_id)
            .order_by(Intervention.created_at.desc(), Intervention.id.desc())).all()
        follow_ups = self.db.scalars(select(FollowUp).where(FollowUp.student_id == student_id)
            .order_by(FollowUp.scheduled_for.desc(), FollowUp.id.desc())).all()
        notes = self.db.scalars(select(InterventionNote).where(
            InterventionNote.intervention_id.in_([i.id for i in interventions]))).all()
        review_ids = {r.reviewer_id for w in warnings for r in w.reviews}
        user_ids = review_ids | {w.assigned_to for w in warnings if w.assigned_to}
        user_ids |= {i.assigned_to for i in interventions} | {f.assigned_to for f in follow_ups}
        users = {u.id: u for u in self.db.scalars(select(User).where(User.id.in_(user_ids)))}
        pred_rows = [ProfilePrediction(id=p.id, probability=p.probability,
            risk_level=p.risk_level.value, predicted_at=p.predicted_at,
            model_version=p.model_version.model_version, explanation=p.explanation or [])
            for p in predictions]
        warning_rows = [ProfileWarning(id=w.id, prediction_id=w.prediction_id,
            risk_level=w.risk_level.value, priority=w.priority.value,
            review_state=w.review_state.value, assigned_advisor=_advisor(users.get(w.assigned_to)),
            created_at=w.created_at, reviews=[ProfileReview(id=r.id, decision=r.decision.value,
                note=r.note, reviewer=_advisor(users.get(r.reviewer_id)), reviewed_at=r.reviewed_at)
                for r in sorted(w.reviews, key=lambda x: (x.reviewed_at, str(x.id)), reverse=True)])
            for w in warnings]
        # Current warning belongs to the latest prediction; historical warnings never leak forward.
        current_warning = next((w for w in warning_rows if predictions and
            w.prediction_id == predictions[0].id and w.review_state != "DISMISSED"), None)
        intervention_rows = [ProfileIntervention(id=i.id, warning_id=i.warning_id,
            type=i.type.value, title=i.title, priority=i.priority.value, status=i.status.value,
            assigned_advisor=_advisor(users.get(i.assigned_to)), start_date=i.start_date,
            target_date=i.target_date, created_at=i.created_at, completed_at=i.completed_at,
            completion_outcome=i.completion_outcome.value if i.completion_outcome else None)
            for i in interventions]
        now = datetime.now(timezone.utc)
        follow_rows = [ProfileFollowUp(id=f.id, intervention_id=f.intervention_id,
            scheduled_for=f.scheduled_for, method=f.method.value, purpose=f.purpose,
            effective_status=CaseworkService.effective_status(f, now).value,
            outcome=f.outcome.value if f.outcome else None,
            assigned_advisor=_advisor(users.get(f.assigned_to)), completed_at=f.completed_at)
            for f in follow_ups]
        return StudentProfile(
            student=ProfileStudent.model_validate({k: getattr(s, k) for k in ProfileStudent.model_fields}),
            admission=ProfileAdmission(
                **{k: (float(getattr(a, k)) if getattr(a, k) is not None and k in
                    {"admission_grade", "previous_qualification_grade", "unemployment_rate", "inflation_rate", "gdp"}
                    else getattr(a, k)) for k in ProfileAdmission.model_fields
                    if not k.endswith("_label")},
                application_mode_label=category_label("application_mode", a.application_mode_code),
                course_label=category_label("course", a.course_code),
                previous_qualification_label=category_label("previous_qualification", a.previous_qualification_code),
            ) if a else None,
            semester_one=_semester(sem) if sem else None,
            prediction_readiness=Readiness(status="READY" if assembly.ready else "NOT_READY",
                required_feature_count=len(PREDICTION_FEATURES),
                available_feature_count=len(assembly.values),
                missing_features=list(assembly.missing_features)),
            latest_prediction=pred_rows[0] if pred_rows else None,
            prediction_history=pred_rows, active_warning=current_warning,
            warning_history=warning_rows, interventions=intervention_rows,
            follow_ups=follow_rows,
            timeline=self._timeline(predictions, warnings, interventions, notes, follow_ups),
        )

    @staticmethod
    def _timeline(predictions, warnings, interventions, notes, follow_ups):
        events = []
        def add(kind, at, title, summary, entity_id):
            if at is not None:
                events.append(TimelineEvent(type=kind, occurred_at=at, title=title,
                                            summary=summary, entity_id=entity_id))
        for p in predictions:
            add("PREDICTION_CREATED", p.predicted_at, "Prediction created",
                f"{p.risk_level.value} risk", p.id)
        for w in warnings:
            add("WARNING_CREATED", w.created_at, "Warning created", w.priority.value, w.id)
            for r in w.reviews:
                add("WARNING_REVIEWED", r.reviewed_at, "Warning reviewed", r.decision.value, w.id)
        for i in interventions:
            add("INTERVENTION_CREATED", i.created_at, "Intervention created", i.title, i.id)
            if i.status == InterventionStatus.COMPLETED:
                add("INTERVENTION_COMPLETED", i.completed_at, "Intervention completed", i.title, i.id)
            if i.status == InterventionStatus.CANCELLED:
                add("INTERVENTION_CANCELLED", i.updated_at, "Intervention cancelled", i.title, i.id)
        for n in notes:
            add("INTERVENTION_NOTE_ADDED", n.created_at, "Intervention note added", n.note, n.id)
        for f in follow_ups:
            add("FOLLOW_UP_SCHEDULED", f.created_at, "Follow-up scheduled", f.purpose, f.id)
            if f.status == FollowUpStatus.COMPLETED:
                add("FOLLOW_UP_COMPLETED", f.completed_at, "Follow-up completed", f.purpose, f.id)
            if f.status == FollowUpStatus.CANCELLED:
                add("FOLLOW_UP_CANCELLED", f.updated_at, "Follow-up cancelled", f.purpose, f.id)
        return sorted(events, key=lambda e: (e.occurred_at.replace(tzinfo=timezone.utc)
            if e.occurred_at.tzinfo is None else e.occurred_at, e.type, str(e.entity_id)), reverse=True)
