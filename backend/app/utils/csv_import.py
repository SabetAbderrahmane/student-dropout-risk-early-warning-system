import csv
import io
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Final

from app.ml.feature_schema import (
    PREDICTION_FEATURES,
    FeatureDataType,
    validate_feature_value,
)

SYSTEM_DOMAIN_FIELDS: Final[tuple[str, ...]] = (
    "student_number",
    "name",
    "admission_method",
    "previous_qualification",
)
CSV_HEADERS: Final[tuple[str, ...]] = SYSTEM_DOMAIN_FIELDS + tuple(
    feature.name for feature in PREDICTION_FEATURES
)
MAX_DATA_ROWS: Final = 5_000
MAX_UPLOAD_BYTES: Final = 5 * 1024 * 1024

_TEXT_LIMITS: Final = MappingProxyType(
    {
        "student_number": 50,
        "name": 200,
        "admission_method": 100,
        "previous_qualification": 200,
    }
)


class CsvStructureError(ValueError):
    def __init__(self, code: str, message: str, details: object | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CsvDataRow:
    row_number: int
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class RowValidationIssue:
    row_number: int
    field_name: str | None
    error_code: str
    error_message: str


@dataclass(frozen=True, slots=True)
class ValidatedImportRow:
    row_number: int
    student_number: str
    values_by_table: dict[str, dict[str, object]]


def csv_template_bytes() -> bytes:
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\r\n").writerow(CSV_HEADERS)
    return stream.getvalue().encode("utf-8")


def parse_csv(content: bytes) -> list[CsvDataRow]:
    if not content:
        raise CsvStructureError("CSV_EMPTY", "The uploaded CSV file is empty.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvStructureError(
            "CSV_INVALID_ENCODING", "The CSV file must use UTF-8 encoding."
        ) from exc
    if not text.strip():
        raise CsvStructureError("CSV_EMPTY", "The uploaded CSV file is empty.")

    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if header is None or not any(header):
            raise CsvStructureError("CSV_EMPTY", "The uploaded CSV file is empty.")
        duplicates = sorted(
            name for name, count in Counter(header).items() if count > 1
        )
        if duplicates:
            raise CsvStructureError(
                "CSV_DUPLICATE_HEADER",
                "The CSV header contains duplicate column names.",
                {"columns": duplicates},
            )

        expected = set(CSV_HEADERS)
        received = set(header)
        missing = sorted(expected - received)
        if missing:
            raise CsvStructureError(
                "CSV_MISSING_COLUMNS",
                "The CSV file is missing required columns.",
                {"columns": missing},
            )
        unknown = sorted(received - expected)
        if unknown:
            raise CsvStructureError(
                "CSV_UNKNOWN_COLUMNS",
                "The CSV file contains unknown columns.",
                {"columns": unknown},
            )

        rows: list[CsvDataRow] = []
        for row_number, row in enumerate(reader, start=2):
            if not row or not any(value.strip() for value in row):
                continue
            if len(row) != len(header):
                raise CsvStructureError(
                    "CSV_PARSE_ERROR",
                    f"CSV row {row_number} has {len(row)} values; expected {len(header)}.",
                )
            rows.append(CsvDataRow(row_number, dict(zip(header, row, strict=True))))
            if len(rows) > MAX_DATA_ROWS:
                raise CsvStructureError(
                    "CSV_TOO_MANY_ROWS",
                    f"A CSV import may contain at most {MAX_DATA_ROWS} data rows.",
                )
    except csv.Error as exc:
        raise CsvStructureError(
            "CSV_PARSE_ERROR", "The CSV file could not be parsed."
        ) from exc
    return rows


def validate_rows(
    rows: list[CsvDataRow], existing_student_numbers: set[str]
) -> tuple[list[ValidatedImportRow], list[RowValidationIssue]]:
    numbers = [row.values["student_number"].strip() for row in rows]
    duplicate_numbers = {
        number for number, count in Counter(numbers).items() if number and count > 1
    }
    valid_rows: list[ValidatedImportRow] = []
    issues: list[RowValidationIssue] = []

    for row in rows:
        row_issues: list[RowValidationIssue] = []
        text_values: dict[str, str] = {}
        for field_name in SYSTEM_DOMAIN_FIELDS:
            value = row.values[field_name].strip()
            text_values[field_name] = value
            if not value:
                row_issues.append(
                    _issue(
                        row.row_number,
                        field_name,
                        "REQUIRED_VALUE_MISSING",
                        f"{field_name} is required.",
                    )
                )
            elif len(value) > _TEXT_LIMITS[field_name]:
                row_issues.append(
                    _issue(
                        row.row_number,
                        field_name,
                        "INVALID_FEATURE_VALUE",
                        f"{field_name} exceeds {_TEXT_LIMITS[field_name]} characters.",
                    )
                )

        student_number = text_values["student_number"]
        if student_number in duplicate_numbers:
            row_issues.append(
                _issue(
                    row.row_number,
                    "student_number",
                    "DUPLICATE_STUDENT_NUMBER_IN_FILE",
                    "student_number appears more than once in this CSV file.",
                )
            )
        elif student_number in existing_student_numbers:
            row_issues.append(
                _issue(
                    row.row_number,
                    "student_number",
                    "STUDENT_NUMBER_ALREADY_EXISTS",
                    "A student with this student_number already exists.",
                )
            )

        parsed_features: dict[str, object] = {}
        for feature in PREDICTION_FEATURES:
            raw_value = row.values[feature.name].strip()
            if not raw_value:
                row_issues.append(
                    _issue(
                        row.row_number,
                        feature.name,
                        "REQUIRED_VALUE_MISSING",
                        f"{feature.name} is required.",
                    )
                )
                continue
            try:
                value: int | Decimal
                if feature.data_type is FeatureDataType.INTEGER:
                    value = int(raw_value)
                else:
                    value = Decimal(raw_value)
                    if not value.is_finite():
                        raise InvalidOperation
            except ValueError:
                row_issues.append(
                    _issue(
                        row.row_number,
                        feature.name,
                        "INVALID_INTEGER",
                        f"{feature.name} must be an integer.",
                    )
                )
                continue
            except InvalidOperation:
                row_issues.append(
                    _issue(
                        row.row_number,
                        feature.name,
                        "INVALID_NUMBER",
                        f"{feature.name} must be a finite number.",
                    )
                )
                continue
            try:
                validate_feature_value(feature.name, value)
            except ValueError as exc:
                row_issues.append(
                    _issue(
                        row.row_number,
                        feature.name,
                        "INVALID_FEATURE_VALUE",
                        str(exc),
                    )
                )
                continue
            parsed_features[feature.name] = value

        if row_issues:
            issues.extend(row_issues)
            continue

        values_by_table: dict[str, dict[str, object]] = {
            "students": {
                "student_number": student_number,
                "name": text_values["name"],
            },
            "admission_records": {
                "admission_method": text_values["admission_method"],
                "previous_qualification": text_values["previous_qualification"],
            },
            "first_semester_records": {},
        }
        for feature in PREDICTION_FEATURES:
            values_by_table[feature.storage_table][feature.storage_column] = (
                parsed_features[feature.name]
            )
        valid_rows.append(
            ValidatedImportRow(row.row_number, student_number, values_by_table)
        )

    return valid_rows, issues


def _issue(
    row_number: int, field_name: str | None, error_code: str, error_message: str
) -> RowValidationIssue:
    return RowValidationIssue(row_number, field_name, error_code, error_message)
