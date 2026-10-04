# Staged CSV import backend and Screen 5 integration contract

Backend-only change on `feat/backend-staged-csv-import`. Screen 5 and the
existing frontend were not changed. The existing `POST /api/v1/imports/csv`
still immediately persists valid rows and reports invalid rows exactly as
before. Staged imports are an explicit separate workflow.

## Authoritative data and lifecycle

Upload uses the existing parser, official 34-column template (four system
fields and 30 prediction features), canonical feature validators and limits:
UTF-8 with optional BOM, 5 MiB, 5,000 nonblank data rows, exact canonical column
set with flexible input order, and existing CSV field/structure rules. Get the
header from `GET /api/v1/imports/template`; never invent fields or missing values.

Staging writes only staged batches, staged rows and audit records. It does not
create/update students, admissions or semester records, create an import-history
entry, or advance dashboard import freshness. Original parsed string values are
stored separately from edited string values, including whitespace. Successful
persistence uses the original import validator's normalization and conversion.
The original file bytes are not retained.

States are separate from `ImportStatus`:

```text
REVIEW_REQUIRED ⇄ READY_TO_COMMIT → COMMITTED
       └─────────────┴──────────→ CANCELLED
```

`READY_TO_COMMIT` means at least one included row and zero invalid included rows
at the most recent validation. Database conflicts can arise later; commit
always revalidates. Header-only files create a zero-row `REVIEW_REQUIRED` batch,
and cannot commit. Committed/cancelled batches cannot be edited, restored,
excluded or cancelled again. A committed batch permits read/export and
idempotent successful commit retries.

| Batch field | Meaning |
| --- | --- |
| `total_rows` | All staged nonblank data rows, including excluded rows |
| `included_rows`, `excluded_rows` | Inclusion counts; sum to total |
| `valid_rows`, `invalid_rows` | Validation status across all rows; sum to total |
| `valid_included_rows`, `invalid_included_rows` | Validation status among included rows only |
| `validation_issue_count` | Number of issues across all rows, not number of invalid rows |
| `included_issue_count` | Number of issues among included rows |
| `version` | Batch revision, starts at 1 |
| `last_commit_error` | Most recent rejected commit message, otherwise null |
| `import_job_id`, `import_job` | Linked existing import-history receipt after success, otherwise null |

Rows contain `id`, `batch_id`, physical CSV `row_number` (first data row is 2),
`version`, `original_values`, `edited_values`, `included`, `is_valid`, and
`issues`. Each issue contains `row_number`, `field_name`, `error_code`, and
`error_message`. Batch timestamps include creation/update, successful completion
and cancellation. UUID actor fields identify the actual uploader and action actor.

## Permissions and routes

Every route requires JWT bearer authentication. System Admin and Academic Admin
can read staged batches, rows, template, audit actions and exports. Academic
Admin alone can upload/correct/exclude/restore/commit/cancel. Academic Advisor
has no staged-import access. These permissions are enforced by FastAPI.

| Method and route | Request / response |
| --- | --- |
| `POST /api/v1/imports/staged/csv` | Multipart `file`; 201 batch response |
| `GET /api/v1/imports/staged` | Paginated batches, optional exact `status` enum |
| `GET /api/v1/imports/staged/{batch_id}` | Batch totals, version, timestamps and commit receipt |
| `GET /api/v1/imports/staged/{batch_id}/rows` | Paginated row response with `batch_version` |
| `PATCH /api/v1/imports/staged/{batch_id}/rows/{row_id}` | Correction request; returns `{batch, row}` |
| `POST /api/v1/imports/staged/{batch_id}/commit` | Expected batch version; returns committed batch/receipt |
| `POST /api/v1/imports/staged/{batch_id}/cancel` | Expected batch version; returns cancelled batch |
| `GET /api/v1/imports/staged/{batch_id}/export` | Edited canonical UTF-8 CSV, included rows only |
| `GET /api/v1/imports/staged/{batch_id}/actions` | Paginated append-only action audit |

All paginated endpoints accept `page >= 1` (default 1) and `1 <= page_size <= 100`
(default 25), and return `items`, `page`, `page_size`, `total`, `total_pages`.
An empty result has `total_pages: 0`. Rows are ordered by source row number;
batches by newest creation then UUID; audit actions by batch revision then UUID.
Filtering and pagination run in SQL. Staged routes are registered before the
existing dynamic `/{import_id}` routes, so `/staged` is never interpreted as a UUID.

Row filters combine with AND:

- `included=true|false`: inclusion status.
- `valid=true|false`: validation status, including excluded rows unless separately filtered.
- `search=<text>`: case-insensitive substring of edited student number or name, max 200 characters. `%` and `_` are literal text.

No issue-code, academic-term, GPA, advisor or degree-catalog filter is implied.

## Request and response examples

`$token`, `$batchId`, `$rowId` and version numbers below are values from real
authentication and preceding responses. Responses shown below are abridged;
OpenAPI `/docs` supplies the complete typed contract. Canonical maps in real row
responses contain all 34 original/edited fields.

Upload the completed official template:

```bash
curl -H "Authorization: Bearer $token" \
  -F "file=@students.csv" \
  http://localhost:8000/api/v1/imports/staged/csv
```

For two rows with one valid row and one row missing name and GDP:

```json
{
  "status": "REVIEW_REQUIRED",
  "version": 1,
  "total_rows": 2,
  "included_rows": 2,
  "excluded_rows": 0,
  "valid_rows": 1,
  "invalid_rows": 1,
  "valid_included_rows": 1,
  "invalid_included_rows": 1,
  "validation_issue_count": 2,
  "included_issue_count": 2,
  "last_commit_error": null,
  "import_job_id": null,
  "import_job": null
}
```

Read review work with SQL filters:

```text
GET /api/v1/imports/staged?status=REVIEW_REQUIRED&page=1&page_size=25
GET /api/v1/imports/staged/{batch_id}
GET /api/v1/imports/staged/{batch_id}/rows?included=true&valid=false&page=1&page_size=25
```

An abridged invalid row response:

```json
{
  "batch_version": 1,
  "page": 1,
  "page_size": 25,
  "total": 1,
  "total_pages": 1,
  "items": [{
    "row_number": 3,
    "version": 1,
    "included": true,
    "is_valid": false,
    "issues": [
      {"row_number": 3, "field_name": "name", "error_code": "REQUIRED_VALUE_MISSING", "error_message": "name is required."},
      {"row_number": 3, "field_name": "gdp", "error_code": "REQUIRED_VALUE_MISSING", "error_message": "gdp is required."}
    ]
  }]
}
```

Correct real source values, never synthesized defaults:

```text
PATCH /api/v1/imports/staged/{batch_id}/rows/{row_id}
```

```json
{
  "expected_batch_version": 1,
  "expected_row_version": 1,
  "values": {"name": "Correct source name", "gdp": "1.5"}
}
```

All values are strings, including numeric CSV cells. Partial canonical updates
are merged into the edited map. Unknown fields, nonstring values, extra request
keys, oversized CSV cells and empty change requests return 422. Invalid but
well-shaped canonical corrections are accepted as draft edits and return their
authoritative validation issues, rather than persisting a student.

Example abridged correction response:

```json
{
  "batch": {"version": 2, "status": "READY_TO_COMMIT", "invalid_included_rows": 0, "included_issue_count": 0},
  "row": {"version": 2, "included": true, "is_valid": true, "issues": []}
}
```

Exclude or restore (use current revisions):

```json
{"expected_batch_version": 2, "expected_row_version": 2, "included": false}
```

```json
{"expected_batch_version": 3, "expected_row_version": 3, "included": true}
```

One PATCH can contain both `values` and `included`. Every accepted action
revalidates the entire batch. Included duplicate student numbers invalidate
every conflicting included row; existing database numbers remain conflicts.
Excluded rows do not participate in batch duplicate checks, but retain their
individual field/database validation issues. There is no overwrite/upsert.

Commit uses only the batch revision:

```text
POST /api/v1/imports/staged/{batch_id}/commit
```

```json
{"expected_batch_version": 4}
```

Successful response includes:

```json
{
  "status": "COMMITTED",
  "version": 5,
  "last_commit_error": null,
  "import_job": {
    "filename": "students.csv",
    "status": "IMPORTED",
    "total_rows": 2,
    "valid_rows": 2,
    "invalid_rows": 0
  }
}
```

It also supplies the linked import job UUID and completion timestamps. Repeating
a successful commit request, even with the original precommit revision, returns
the original receipt without importing rows or appending another commit action.

Cancellation uses `POST /.../{batch_id}/cancel` with the same version-request
shape, returning `status: CANCELLED`, an incremented revision and `cancelled_at`.
It disables the pending operation; it never deletes committed students.

Audit and export:

```text
GET /api/v1/imports/staged/{batch_id}/actions?page=1&page_size=25
GET /api/v1/imports/staged/{batch_id}/export
```

Audit records include UUIDs, actual actor, timestamp, action, batch revision and
relevant changes. Corrections record before/after values; exclusion/restoration
records inclusion changes; batch-wide revalidation records changed row issues.
Actions are `UPLOADED`, `CORRECTED`, `EXCLUDED`, `RESTORED`, `COMMIT_REJECTED`,
`COMMITTED`, `CANCELLED`. A correction combined with an inclusion change is
`CORRECTED`, with both changes in the payload.

## Errors, revisions and transactions

Errors use the existing `{error: {code, message, details?}}` envelope:

| HTTP / code | Handling |
| --- | --- |
| 401 / existing auth error | Clear session and redirect to login |
| 403 / existing RBAC error | Permission denied; do not offer write actions |
| 404 / `STAGED_IMPORT_NOT_FOUND`, `STAGED_ROW_NOT_FOUND` | Missing batch or row outside this batch |
| 409 / `STAGED_IMPORT_STALE`, `STAGED_ROW_STALE` | Reload batch and row pages before retrying; details may include current revision |
| 409 / `STAGED_IMPORT_IMMUTABLE` | Terminal state; read-only |
| 409 / `STAGED_IMPORT_NOT_READY` | Empty selection or invalid included rows; details contain refreshed full batch |
| 409 / `STAGED_IMPORT_COMMIT_CONFLICT` | Whole graph set rolled back; details contain refreshed batch; fetch rows for actual conflict issues |
| 409 / `STAGED_IMPORT_BUSY` | Competing transaction; reload and retry |
| 400 / existing `CSV_*` structural errors | Repair upload; no staged batch persisted |
| 413 / `CSV_FILE_TOO_LARGE` | Existing 5 MiB limit |
| 422 / `VALIDATION_ERROR` | Malformed correction/version/filter request |

Batch writers acquire a PostgreSQL row lock and compare-and-swap the expected
revision. PATCH additionally checks the row revision. Changed sibling issues
advance sibling row revisions. Stale requests do not change data or audit.
Read row pages and exports hold a shared batch lock for coherent values and
revisions. Row versions advance for direct edits/inclusion changes or changed
validation issues, not unrelated batch edits.

Commit revalidates all included rows against current database state under the
batch lock. All graphs and the history job are written within one savepoint in
the batch transaction. A uniqueness violation rolls back the entire graph set,
revalidates against the now-current database, and persists conflict feedback
and a rejected-commit audit. No partially imported graph or history job remains.
For a nonidentifier integrity failure, the general `last_commit_error` remains
without inventing a student-number conflict. All batches remain available for
review/retry. Known rejected commits consume a batch revision because updated
validation/error/audit information is persisted; clients must reload.

Different-batch races rely on the existing unique student-number constraint.
Same-batch concurrent commits return one receipt with one import-history job.
Unrelated unexpected exceptions roll back the request transaction when its
session closes; clients should refetch after an uncertain network outcome.

## History, freshness, export and retention

One successful staged commit creates one existing `ImportJob` with original
uploader, filename, `IMPORTED` status and completion time. Its `total_rows` is the
included rows actually submitted to persistence, `valid_rows` is that same
successfully imported count, and `invalid_rows` is zero. Excluded rows remain
counted in the staged batch, and are never mislabeled as failed imports.
Historical immediate-import counts/errors are unchanged. Existing history
detail/error endpoints remain usable, and the dashboard's existing last-import
query includes successful staged commits without modification. Cancelling or
staging does not advance freshness.

Export omits excluded rows and retains source-row order. It uses the official
header order and exact edited string values, including currently invalid drafts
and negative numbers. No correction is synthesized. This is machine-readable
canonical CSV for re-import, not a spreadsheet diagnostics export; values are
not prefixed or altered for spreadsheet rendering. Formula-like text remains
literal canonical source text. Audit/issue diagnostics are JSON and do not
offer a spreadsheet CSV export. Any future spreadsheet-oriented diagnostics
export must escape formula-leading text in its display copy without changing
canonical stored values or this re-import contract.

Retention is explicit: staged original/edited values and audit records are
retained indefinitely in this version, including after commit/cancellation.
Cancellation marks the operation discarded; it does not purge source/audit.
There is no public delete/purge endpoint or background purge. Access remains
restricted to the two administrative roles. Operational retention limits and
any audited purge must be approved separately before adding a retention job.

## Verification and changed files

Changed files:

- `backend/app/services/import_service.py`: extract shared upload/parser entrypoint; keep immediate import persistence behavior.
- `backend/app/api/v1/imports.py`: register staged routes before dynamic history IDs.
- `backend/app/models/__init__.py`: register staged models.
- `backend/app/models/staged_import.py`: separate batch lifecycle, original/edited rows, counts/revisions and action audit.
- `backend/app/schemas/staged_import.py`: typed requests, responses, corrections and pagination.
- `backend/app/services/staged_import_service.py`: authoritative validation, corrections, SQL queries, locks/CAS, atomic commit/retry, export and audit.
- `backend/app/api/v1/staged_imports.py`: backend RBAC and staged endpoints.
- `backend/alembic/versions/20261004_0008_staged_csv_import.py`: additive migration with reversible staged tables; existing tables/statuses untouched.
- `backend/tests/api/test_staged_imports.py`: workflow, compatibility, RBAC, versions, rollback, history/freshness, pagination and export tests.
- `backend/tests/api/test_staged_imports_postgres.py`: real concurrent commit/edit and uniqueness-race tests, plus upgrade/downgrade/re-upgrade with historical import preservation and metadata comparison.
- `docs/staged-csv-import-api.md`: this implementation report and frontend contract.

Commands executed from `backend` using the existing `.venv` Python:

```powershell
& '..\.venv\Scripts\python.exe' -m pytest tests/api/test_imports.py -q
& '..\.venv\Scripts\python.exe' -m pytest tests/api/test_staged_imports.py tests/api/test_imports.py -q --tb=short
$env:STAGED_IMPORT_TEST_DATABASE_URL = 'postgresql+psycopg://staged_test@127.0.0.1:55439/postgres'
& '..\.venv\Scripts\python.exe' -m pytest tests/api/test_staged_imports_postgres.py -q --tb=short
& '..\.venv\Scripts\python.exe' -m pytest tests/api/test_imports.py tests/api/test_staged_imports.py tests/api/test_staged_imports_postgres.py tests/api/test_read_models.py tests/api/test_students.py -q --tb=short
& '..\.venv\Scripts\python.exe' -m pytest -q --tb=short
$env:DATABASE_URL = $env:STAGED_IMPORT_TEST_DATABASE_URL
& '..\.venv\Scripts\python.exe' -m alembic upgrade head
& '..\.venv\Scripts\python.exe' -m alembic check
```

Results:

- Existing immediate import suite: **23 passed**.
- Immediate + staged workflow suite: **45 passed**.
- Initial PostgreSQL concurrency checks: **3 passed**; migration roundtrip was then added and passed in the broader suites.
- Relevant API/migration/concurrency/student/read-model suite: **86 passed in 26.64 seconds**.
- Full backend suite including all four PostgreSQL tests: **156 passed in 58.82 seconds**.
- Real PostgreSQL 18 migration upgrade: passed; `alembic check` found **no new upgrade operations**.
- Upgrade/downgrade/re-upgrade test preserved pre-existing history counts and found no model/migration differences.
- Ruff import/unused-symbol checks (`--select F,I`), formatting checks and `git diff --check`: passed.

The PostgreSQL tests used an isolated temporary PostgreSQL 18 cluster bound to
`127.0.0.1:55439`, initialized with `initdb` and started/stopped with `pg_ctl`.
This test-only local URL is not an application configuration change. Each
concurrency/migration test also used its own temporary schema. No existing
database, credentials or service configuration was changed. Test files skip
these four PostgreSQL checks when `STAGED_IMPORT_TEST_DATABASE_URL` is absent;
the ordinary API tests continue to use the existing SQLite fixtures.

Formatting/lint commands from the repository root applied only to the ten
changed/new Python files listed above:

```powershell
uv tool run --from ruff ruff check --select F,I --fix <changed Python files>
uv tool run --from ruff ruff format <changed Python files>
uv tool run --from ruff ruff check --select F,I <changed Python files>
uv tool run --from ruff ruff format --check <changed Python files>
git diff --check
```

No frontend implementation, PR or merge to main was performed. Apply migration
`20261004_0008` to the intended application database before using staged routes;
the task's migration execution was confined to the disposable test cluster.

## Screen 5 frontend handoff

1. Reuse existing JWT, sessionStorage, `NEXT_PUBLIC_API_URL` and API error handling.
2. Keep immediate import on `/imports/csv`; use `/imports/staged/csv` explicitly for the review workflow.
3. Fetch batch and paginated rows; display backend totals and issue counts separately.
4. Display original values alongside editable canonical strings. Render only the official template fields.
5. PATCH using the displayed batch/row revisions; show returned backend issues.
6. After any correction/exclusion/restore, use returned batch revision and refetch row pages, since sibling duplicates/issues/revisions may have changed. Do not update only the edited row optimistically.
7. Enable commit only for Academic Admin with returned `READY_TO_COMMIT`; still handle commit-time revalidation failure.
8. On stale/busy responses, reload before resubmitting. On rejected commit, use `error.details` for batch feedback and reload rows. Never auto-retry a stale edit.
9. Successful commit shows the existing history receipt. Retries are safe; do not invent asynchronous job progress.
10. Terminal batches are read-only. Cancel is unavailable after commit and cannot delete students.
11. Export is the real edited included canonical CSV. Keep spreadsheet diagnostic exports separate if added later.
12. System Admin sees read/export/template/audit actions; Academic Advisor has no staged workflow.

No Screen 5 UI, prototype semantics or frontend dependency changes are included.
