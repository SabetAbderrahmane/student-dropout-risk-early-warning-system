from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.prediction import ModelVersion, PredictionResult, RiskLevel
from app.models.student import Student


class PredictionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_model_by_version(self, version: str) -> ModelVersion | None:
        return self.db.scalar(
            select(ModelVersion).where(ModelVersion.model_version == version)
        )

    def get_active_model(self) -> ModelVersion | None:
        return self.db.scalar(
            select(ModelVersion).where(ModelVersion.is_active.is_(True))
        )

    def add_model(self, model: ModelVersion) -> ModelVersion:
        self.db.add(model)
        self.db.flush()
        return model

    def activate_only(self, model: ModelVersion) -> None:
        self.db.execute(
            update(ModelVersion)
            .where(ModelVersion.id != model.id)
            .values(is_active=False)
        )
        model.is_active = True
        self.db.flush()

    def get_student_graph(self, student_id: UUID) -> Student | None:
        return self.db.scalar(
            select(Student)
            .options(
                joinedload(Student.admission_record),
                joinedload(Student.first_semester_record),
            )
            .where(Student.id == student_id)
        )

    def list_student_graphs(self) -> list[Student]:
        return list(
            self.db.scalars(
                select(Student)
                .options(
                    joinedload(Student.admission_record),
                    joinedload(Student.first_semester_record),
                )
                .order_by(Student.student_number, Student.id)
            ).unique()
        )

    def add_prediction(self, prediction: PredictionResult) -> PredictionResult:
        self.db.add(prediction)
        self.db.flush()
        return prediction

    def get_prediction(self, prediction_id: UUID) -> PredictionResult | None:
        return self.db.scalar(
            select(PredictionResult)
            .options(
                joinedload(PredictionResult.student),
                joinedload(PredictionResult.model_version),
            )
            .where(PredictionResult.id == prediction_id)
        )

    def list_predictions(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        risk_level: RiskLevel | None,
        model_version: str | None,
        student_id: UUID | None,
        sort: str,
        order: str,
    ) -> tuple[list[PredictionResult], int]:
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(Student.student_number.ilike(pattern), Student.name.ilike(pattern))
            )
        if risk_level:
            filters.append(PredictionResult.risk_level == risk_level)
        if model_version:
            filters.append(ModelVersion.model_version == model_version)
        if student_id:
            filters.append(PredictionResult.student_id == student_id)

        joined = (
            select(PredictionResult)
            .join(PredictionResult.student)
            .join(PredictionResult.model_version)
            .where(*filters)
        )
        total = (
            self.db.scalar(
                select(func.count(PredictionResult.id))
                .join(PredictionResult.student)
                .join(PredictionResult.model_version)
                .where(*filters)
            )
            or 0
        )
        sort_columns = {
            "predicted_at": PredictionResult.predicted_at,
            "probability": PredictionResult.probability,
            "risk_level": PredictionResult.risk_level,
            "student_number": Student.student_number,
            "model_version": ModelVersion.model_version,
        }
        direction = desc if order == "desc" else asc
        statement = (
            joined.options(
                joinedload(PredictionResult.student),
                joinedload(PredictionResult.model_version),
            )
            .order_by(direction(sort_columns[sort]), desc(PredictionResult.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement).unique()), total

    def list_student_history(
        self, student_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[PredictionResult], int]:
        total = (
            self.db.scalar(
                select(func.count(PredictionResult.id)).where(
                    PredictionResult.student_id == student_id
                )
            )
            or 0
        )
        statement = (
            select(PredictionResult)
            .options(
                joinedload(PredictionResult.student),
                joinedload(PredictionResult.model_version),
            )
            .where(PredictionResult.student_id == student_id)
            .order_by(PredictionResult.predicted_at.desc(), PredictionResult.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement).unique()), total
