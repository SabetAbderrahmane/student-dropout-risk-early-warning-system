# Stitch UI ↔ FastAPI Contract v1

Status: **FROZEN FOR IMPLEMENTATION**

Date: 2026-09-30

Base backend: `main@330be7b7ef2eb5693a74b479c3cd3883c90a1d05`

Source UI: Stitch export **Academic Early Warning / Student Retention Decision Support**.

## 1. Purpose

This document freezes the backend-facing contract required to implement the approved Stitch visual identity without changing the thesis into a different product.

The Stitch export is the **visual and interaction specification**. The FastAPI domain model, UCI dataset 697 feature contract, persisted prediction history, and human-in-the-loop early-warning workflow remain the **factual system specification**.

The frontend must never display invented institutional telemetry simply because it appears in the Stitch mockups.

## 2. Architectural rule

Keep the current modular-monolith architecture.

```
Next.js Stitch UI
        ↓
typed frontend API client / view-model adapters
        ↓
FastAPI /api/v1
        ↓
service layer
        ↓
repositories
        ↓
PostgreSQL + versioned ML artifact
```

Do not redesign persistence around individual visual cards.

Existing normalized write/detail APIs remain valid. Add purpose-built **read models** for dense registry/dashboard/profile screens where a single aggregate response prevents excessive client-side joins.

## 3. Existing API contracts that remain stable

These endpoints remain the foundation and should not be broken merely to match Stitch layout:

```
POST /api/v1/auth/login
GET  /api/v1/auth/me

GET    /api/v1/students
POST   /api/v1/students
GET    /api/v1/students/{student_id}
PATCH  /api/v1/students/{student_id}
DELETE /api/v1/students/{student_id}

GET /api/v1/students/{student_id}/admission
PUT /api/v1/students/{student_id}/admission

GET /api/v1/students/{student_id}/semester-1
PUT /api/v1/students/{student_id}/semester-1

GET  /api/v1/imports/template
POST /api/v1/imports/csv
GET  /api/v1/imports
GET  /api/v1/imports/{import_id}
GET  /api/v1/imports/{import_id}/errors
```

The current CSV contract remains **34 columns**: 4 operational/domain fields + 30 canonical prediction features. Do not change this contract for visual convenience.

## 4. Global UI vocabulary

### Risk levels

Use exactly:

```
LOW
MEDIUM
HIGH
```

Risk thresholds come from the active model metadata. Do not hard-code Stitch's 40%/70% thresholds in React.

### Workflow priority

Priority is distinct from risk level:

```
P1_URGENT
P2_ELEVATED
P3_STANDARD
```

### Warning review state

Use:

```
PENDING_REVIEW
CONFIRMED
DISMISSED
```

### Intervention state

Use:

```
PLANNED
IN_PROGRESS
ACTION_REQUIRED
COMPLETED
CANCELLED
```

### Follow-up state

Use:

```
SCHEDULED
DUE
OVERDUE
COMPLETED
CANCELLED
```

## 5. Data that Stitch must NOT assume exists

The current thesis dataset/backend does not provide the following. These fields must not appear as live institutional facts unless a future phase explicitly implements a new source:

- Canvas/LMS access telemetry
- class or lab attendance percentages
- individual course assessments or midterms
- per-course grades
- cumulative institutional GPA
- total credits toward a 120-credit degree
- bursar balances or registration holds
- housing information
- phone numbers
- emergency contacts
- FERPA proxy data
- course instructors
- SMS/email sending integrations
- Zoom/LTI integrations
- degree-audit prerequisites
- student email addresses
- demographic-parity metrics unless a formal fairness evaluation is implemented
- individual prediction confidence intervals unless a defensible uncertainty method is implemented

Do not synthesize these values.

## 6. Data Stitch may display from the current domain

The approved factual student profile can use:

### Student identity / status

- internal UUID
- student_number
- name
- legacy display gender if available
- marital_status_code
- nationality_code
- displaced
- educational_special_needs
- debtor
- tuition_fees_up_to_date
- gender_code
- scholarship_holder
- age_at_enrollment
- international_student

### Enrollment/admission

- admission_method
- admission_grade
- previous_qualification
- previous_qualification_grade
- application_mode_code
- application_order
- course_code
- daytime_evening_attendance
- previous_qualification_code
- mother/father qualification codes
- mother/father occupation codes
- unemployment_rate
- inflation_rate
- gdp

### First semester

- credited_units
- enrolled_units
- evaluations
- approved_units
- average_grade
- without_evaluations

### Derived non-ML display values

Backend read models may derive:

- approval_rate = approved_units / enrolled_units when enrolled_units > 0
- prediction_readiness
- human-readable course label from canonical UCI mapping
- human-readable categorical labels from canonical feature metadata
- latest prediction probability/risk when prediction records exist
- latest warning state
- assigned case owner from active warning/intervention
- last meaningful system activity timestamp

These are view-model fields, not new ML inputs.

---

# 7. Screen contract: Overview / Dashboard

Stitch screen: **Academic Risk Overview Dashboard**

## Required endpoint

```
GET /api/v1/dashboard/overview
```

RBAC:

- SYSTEM_ADMIN: read
- ACADEMIC_ADMIN: read
- ACADEMIC_ADVISOR: read

Response shape:

```json
{
  "students": {
    "total": 4424,
    "prediction_ready": 4301,
    "with_latest_prediction": 4288
  },
  "risk_distribution": {
    "low": 0,
    "medium": 0,
    "high": 0
  },
  "warnings": {
    "active": 0,
    "pending_review": 0,
    "confirmed": 0,
    "dismissed": 0
  },
  "interventions": {
    "active": 0,
    "planned": 0,
    "in_progress": 0,
    "action_required": 0,
    "completed": 0
  },
  "follow_ups": {
    "due_today": 0,
    "overdue": 0
  },
  "model": {
    "version": null,
    "name": null,
    "trained_at": null,
    "low_threshold": null,
    "high_threshold": null
  },
  "data_freshness": {
    "last_import_at": null,
    "last_prediction_at": null
  },
  "warning_activity": [],
  "intervention_activity": [],
  "attention_students": []
}
```

`attention_students` is a limited read-model list, ordered by workflow priority then latest probability.

Do not report fictional LMS/midterm/attendance drivers. Primary drivers must come from persisted model explanations.

## Mutation

```
POST /api/v1/predictions/batch
```

Academic Admin only.

This prototype processes synchronously. The UI action should be **Run Batch Risk Assessment**, not fake an asynchronous worker.

Response:

```json
{
  "assessed": 4200,
  "skipped_not_ready": 224,
  "created_predictions": 4200,
  "created_warnings": 612,
  "model_version": "dropout-xgb-v1",
  "completed_at": "..."
}
```

Warnings are created only for predictions meeting the frozen warning rule.

---

# 8. Screen contract: Students Registry

Stitch screen: **Students Management Registry**

Keep existing `GET /students` for simple list/search compatibility.

Add a dedicated registry read model:

```
GET /api/v1/student-registry
```

Query parameters:

```
page
page_size
search
course_code
risk_level=LOW|MEDIUM|HIGH
warning_state=PENDING_REVIEW|CONFIRMED|DISMISSED|NONE
intervention_state
prediction_readiness=READY|NOT_READY
sort=student_number|name|risk_probability|updated_at
order=asc|desc
```

Response row:

```json
{
  "student_id": "...",
  "student_number": "STU-...",
  "name": "Student Name",
  "course": {
    "code": 9119,
    "label": "Informatics Engineering"
  },
  "admission": {
    "method": "General admission",
    "admission_grade": 145.5
  },
  "semester_one": {
    "average_grade": 11.8,
    "enrolled_units": 6,
    "approved_units": 4,
    "approval_rate": 0.6667
  },
  "prediction_readiness": "READY",
  "latest_prediction": {
    "id": "...",
    "probability": 0.78,
    "risk_level": "HIGH",
    "predicted_at": "..."
  },
  "warning": {
    "id": "...",
    "state": "PENDING_REVIEW"
  },
  "case_owner": {
    "user_id": "...",
    "full_name": "..."
  },
  "last_activity_at": "..."
}
```

The Stitch registry must replace unsupported GPA / attendance / total-credit columns with:

- first-semester average grade
- approved/enrolled units
- approval rate
- prediction readiness

Do not add student email merely to match the mockup.

Server-side export may later be exposed as:

```
GET /api/v1/student-registry/export.csv
```

but export is not a prerequisite for prediction implementation.

---

# 9. Screen contract: Data Import

Stitch screen: **CSV Data Import & Validation**

Existing Phase 4B endpoints remain authoritative.

The Stitch four-stage interaction maps to:

1. Upload CSV
2. Structural validation
3. Row validation
4. Import results

Do not implement:

- browser-side row editing as source of truth
- auto-fix
- overwrite existing student
- schema remapping
- background-worker claims
- automatic inference coupled to import

After a successful import the UI may offer a separate button:

```
Run Risk Assessment
```

which invokes `POST /predictions/batch`.

Optional export endpoint:

```
GET /api/v1/imports/{import_id}/errors.csv
```

This is useful for the Stitch “Exception Log” action but is not required to alter the existing import persistence model.

---

# 10. Screen contract: Risk Predictions & Model Performance

Stitch screen: **Risk Predictions & Model Performance**

## Active model

```
GET /api/v1/models/current
```

Response:

```json
{
  "id": "...",
  "name": "XGBoost",
  "version": "dropout-xgb-v1",
  "trained_at": "...",
  "dataset": {
    "name": "UCI Predict Students' Dropout and Academic Success",
    "dataset_id": 697
  },
  "feature_schema_version": "uci697-first-semester-v1",
  "low_threshold": 0.31,
  "high_threshold": 0.67,
  "artifact_available": true
}
```

## Model evaluation

```
GET /api/v1/models/current/performance
```

Metrics are from the locked held-out final test set, **not from the current student cohort**.

Response:

```json
{
  "evaluation_scope": "FINAL_TEST_SET",
  "sample_size": 885,
  "accuracy": 0.0,
  "precision": 0.0,
  "recall": 0.0,
  "f1": 0.0,
  "roc_auc": 0.0,
  "pr_auc": 0.0,
  "brier_score": 0.0,
  "confusion_matrix": {
    "tp": 0,
    "fp": 0,
    "fn": 0,
    "tn": 0
  },
  "global_feature_importance": [
    {
      "feature": "first_semester_approved_units",
      "label": "First-semester approved units",
      "importance": 0.0
    }
  ]
}
```

Do not show:

- a current-cohort confusion matrix without observed outcomes
- invented AUC values
- invented model names
- editable production thresholds
- demographic parity unless explicitly implemented
- prediction confidence intervals

## Prediction registry

```
GET /api/v1/predictions
```

Filters:

```
page
page_size
search
risk_level
warning_state
course_code
model_version
sort
order
```

Each row includes student identity, probability, risk level, model version, top explanation drivers, prediction timestamp, and workflow state.

## Single prediction

```
GET /api/v1/predictions/{prediction_id}
```

Every prediction is immutable historical evidence.

Persist:

- student_id
- probability
- risk_level
- model_version_id
- feature_snapshot JSON/JSONB
- explanation JSON/JSONB
- predicted_at

Do not overwrite a student's previous prediction.

---

# 11. Screen contract: Student Profile

Stitch screen: **Student Profile**

Add an aggregate read endpoint:

```
GET /api/v1/students/{student_id}/profile
```

This endpoint is optimized for the profile page and does not replace normalized student/admission/semester endpoints.

Response sections:

```json
{
  "student": {},
  "admission": {},
  "semester_one": {},
  "prediction_readiness": {
    "status": "READY",
    "missing_features": []
  },
  "latest_prediction": {},
  "prediction_history": [],
  "active_warning": {},
  "warning_history": [],
  "interventions": [],
  "follow_ups": [],
  "timeline": []
}
```

Profile tabs should be renamed to factual domains:

- Overview & Risk Analytics
- Student & Enrollment Data
- First-Semester Performance
- Warnings & Review History
- Interventions & Advisor Notes
- Scheduled Follow-Ups

The Stitch “Academic Coursework & LMS Telemetry” tab is prohibited for this thesis version.

The risk-factor decomposition uses stored local explanation values from the prediction record.

The longitudinal risk chart uses immutable prediction history.

---

# 12. Prediction readiness

Add:

```
GET /api/v1/students/{student_id}/prediction-readiness
```

Response:

```json
{
  "status": "READY",
  "required_feature_count": 30,
  "available_feature_count": 30,
  "missing_features": []
}
```

This should be derived from `PREDICTION_FEATURES`, never a second feature list.

A student manually created through CRUD may exist before becoming prediction-ready.

---

# 13. Early Warnings

Stitch screen: **Early Warnings Triage Workspace**

## List

```
GET /api/v1/warnings
```

Filters:

```
page
page_size
search
risk_level
review_state
priority
assigned_to
sort
order
```

## Detail

```
GET /api/v1/warnings/{warning_id}
```

Must include:

- warning
- linked prediction
- student summary
- top prediction drivers
- assigned advisor
- review history
- linked intervention summary

## Review

```
POST /api/v1/warnings/{warning_id}/reviews
```

Academic Advisor only for academic disposition. Academic Admin may have read access but must not silently replace advisor judgment.

Request:

```json
{
  "decision": "CONFIRMED",
  "note": "Advisor reviewed the prediction and student record."
}
```

or:

```json
{
  "decision": "DISMISSED",
  "note": "Context reviewed; warning does not require intervention."
}
```

Each review is append-only/auditable.

Do not bulk confirm/dismiss warnings.

## Assignment

```
PATCH /api/v1/warnings/{warning_id}/assignment
```

May assign an Academic Advisor.

---

# 14. Interventions

Stitch screen: **Academic Interventions & Casework**

## List

```
GET /api/v1/interventions
```

## Create

```
POST /api/v1/interventions
```

Request:

```json
{
  "student_id": "...",
  "warning_id": "...",
  "type": "ACADEMIC_TUTORING",
  "title": "First-semester academic support",
  "description": "...",
  "priority": "P2_ELEVATED",
  "assigned_to": "...",
  "start_date": "2026-10-01",
  "target_date": "2026-10-15"
}
```

Allowed intervention categories for the thesis:

```
ACADEMIC_TUTORING
ACADEMIC_ADVISING
STUDY_PERFORMANCE_PLAN
FINANCIAL_SUPPORT_REFERRAL
ADMINISTRATIVE_SUPPORT_REFERRAL
OTHER
```

The system records referrals; it does not pretend to integrate with financial, counseling, LMS, or registrar systems.

## Detail/update

```
GET   /api/v1/interventions/{intervention_id}
PATCH /api/v1/interventions/{intervention_id}
```

## Notes

```
POST /api/v1/interventions/{intervention_id}/notes
GET  /api/v1/interventions/{intervention_id}/notes
```

Notes are attributable and timestamped. Do not overwrite previous advisor notes.

---

# 15. Follow-Ups

Stitch screen: **Follow-Up Schedule & Outcomes Workspace**

## List

```
GET /api/v1/follow-ups
```

Filters should support:

- due date range
- status
- assigned advisor
- student search
- intervention_id

## Create

```
POST /api/v1/interventions/{intervention_id}/follow-ups
```

Request:

```json
{
  "scheduled_for": "...",
  "method": "IN_PERSON",
  "purpose": "Review intervention progress",
  "assigned_to": "..."
}
```

Methods:

```
IN_PERSON
PHONE
EMAIL
ONLINE_MEETING
OTHER
```

These values record the intended/contact method. They do not imply that the application sends the communication.

## Update / complete

```
PATCH /api/v1/follow-ups/{follow_up_id}

POST /api/v1/follow-ups/{follow_up_id}/complete
```

Completion request:

```json
{
  "outcome": "PROGRESS_OBSERVED",
  "notes": "...",
  "next_follow_up_at": null
}
```

Outcome enum:

```
COMPLETED
PROGRESS_OBSERVED
NO_RESPONSE
RESCHEDULED
ESCALATION_REQUIRED
INTERVENTION_COMPLETED
```

Every follow-up must remain linked to its intervention and therefore to the originating warning/prediction chain.

---

# 16. Administration screens

The Stitch sidebar contains Users, Roles & Permissions, System Configuration, and Audit Logs. These are legitimate administration screens but should remain narrower than a full IAM platform.

## Users

System Admin only:

```
GET   /api/v1/admin/users
POST  /api/v1/admin/users
GET   /api/v1/admin/users/{user_id}
PATCH /api/v1/admin/users/{user_id}
```

Support:

- username
- email
- full_name
- role
- is_active
- password creation/reset by explicit action

Prefer deactivation over destructive deletion.

## Roles & Permissions

Roles are fixed by the thesis contract.

```
GET /api/v1/admin/roles
```

Return the static role/permission matrix. Do not build dynamic permission editing unless the thesis requirements change.

## System Configuration

```
GET /api/v1/admin/system-info
```

Read-only operational metadata:

- app version
- environment
- active model version
- database health
- feature schema version

Do not provide UI controls that arbitrarily edit calibrated ML thresholds. Thresholds belong to versioned model metadata.

## Audit Logs

```
GET /api/v1/admin/audit-logs
```

Audit at minimum:

- user creation/update/deactivation
- imports
- prediction runs
- warning reviews
- warning assignment
- intervention creation/update
- follow-up completion

---

# 17. RBAC matrix

| Capability | System Admin | Academic Admin | Academic Advisor |
|---|---:|---:|---:|
| Login / self profile | yes | yes | yes |
| Read students | yes | yes | yes |
| Create/edit/delete student domain | no | yes | no |
| CSV template/history | yes | yes | no |
| CSV upload | no | yes | no |
| Run prediction batch | no | yes | no |
| Read predictions/model metrics | yes | yes | yes |
| Read warnings | yes | yes | yes |
| Review warning | no | no | yes |
| Assign warning/case owner | optional admin oversight | yes | limited/self workflow |
| Create/update intervention | no | yes | yes |
| Manage follow-ups | no | yes | yes |
| User administration | yes | no | no |
| Audit logs | yes | limited if required | limited to own casework if required |

Backend permissions are authoritative; frontend visibility is only a UX convenience.

---

# 18. Database additions implied by this contract

Future migrations should add these resources in implementation phases, not all at once:

### Model / prediction

- model_versions
- prediction_results
- optional prediction_runs

Recommended prediction fields:

- id
- student_id
- model_version_id
- probability
- risk_level
- feature_snapshot JSONB
- explanation JSONB
- predicted_at
- created_by nullable if batch/system-generated

### Warning

- warnings
- warning_reviews

### Casework

- interventions
- intervention_notes
- follow_ups

### Administration

- audit_logs

Keep `assigned_to` foreign keys pointed to `users.id` and validate role semantics in the service layer.

---

# 19. Model metadata rules

There must be one backend source of truth for:

- model name
- model version
- training timestamp
- dataset identity
- feature schema version
- low threshold
- high threshold
- final-test metrics
- artifact path
- preprocessing contract

React must never hard-code:

- XGBoost / LightGBM model names
- AUC values
- threshold values
- SHAP version strings
- confusion-matrix counts

The final winning model may be Logistic Regression, Random Forest, or XGBoost.

---

# 20. Human-in-the-loop invariant

The platform must preserve this chain:

```
Student data
→ prediction
→ LOW / MEDIUM / HIGH
→ qualifying warning
→ advisor review
→ confirm or dismiss
→ optional intervention
→ follow-up
→ recorded outcome
```

Machine learning may:

- calculate probability
- assign risk tier
- create a warning candidate/record according to the locked threshold rule
- provide explanation values

Machine learning must not:

- automatically impose an intervention
- automatically determine academic standing
- mark a student disciplined/probationary
- automatically complete casework

The Stitch ethical-decision-support messaging should remain, but its explanatory text must reference the actual 30-feature UCI/first-semester model rather than fictional LMS/attendance feeds.

---

# 21. Implementation sequencing

The contract should be implemented in this order:

### Phase 5A — Offline ML pipeline

- UCI source ingestion
- locked binary target
- anti-leakage feature selection from `PREDICTION_FEATURES`
- stratified 80/20 final holdout
- 5-fold stratified development CV
- Logistic Regression / Random Forest / XGBoost
- class weighting
- model selection
- threshold calibration
- final test evaluation
- model artifact + metadata

### Phase 5B — Model integration & prediction APIs

- model_versions
- prediction_results
- model loading once at FastAPI startup
- readiness endpoint
- single/batch inference
- model/performance endpoints
- prediction registry/history/explanations

### Phase 6 — Warnings

- warning generation
- warning list/detail
- assignment
- append-only advisor reviews
- confirm/dismiss

### Phase 7 — Interventions & follow-ups

- interventions
- notes
- follow-ups
- outcome recording

### Phase 8 — Stitch read models & dashboard completion

- dashboard aggregate endpoint
- student registry read model
- student profile aggregate read model
- exports where justified
- final Stitch frontend integration

### Phase 9 — Administration & audit

- user management
- static role matrix
- audit log
- system-info screen

This sequencing preserves the existing verified backend and avoids creating placeholder/fake dashboard data before the underlying domain exists.

---

# 22. Acceptance rules for frontend implementation

A Stitch screen is considered integrated only when:

1. every displayed operational value comes from a real API response or an explicitly labeled empty/loading state;
2. no mock values remain in production components;
3. risk labels use LOW/MEDIUM/HIGH consistently;
4. model names, versions, metrics, and thresholds come from backend metadata;
5. unsupported LMS/attendance/course/bursar/contact fields are removed or replaced;
6. backend RBAC is enforced independently of hidden frontend buttons;
7. advisor actions create persistent auditable records;
8. prediction history is immutable;
9. warnings remain human-reviewed before intervention;
10. the interface continues to follow the approved Stitch design system.

## 23. Frozen decision

The approved direction is:

**Preserve Stitch's visual identity; adapt the backend through stable domain APIs plus dedicated read models; never alter the factual ML/data scope to imitate fictional mockup telemetry.**
