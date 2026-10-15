# D1.1: transactional Academic Admin write authorization

Base branch: `origin/codex/phase-d1-release-readiness-audit`, fetched and resolved
before editing to **`bea3570b497e99d6903ea904bba694c6803dc889`**. Its audited
application ancestor is `68faf1d62cc37acf9074fcff00f61ac0aa420698`.
Implementation branch: `codex/phase-d1-academic-write-authorization`.
Implementation/source commit: **`b45058c02c731a5913221aa85a3f1247910c6c77`**,
whose parent is the resolved base above. This evidence report is committed
separately; the implementation commit is not amended or rewritten.

This fixes **D1-01**. It does not complete the remaining D1 findings or authorize
internet deployment. No PR, merge, dependency upgrade, CI change, migration or
registered artifact change is included. The attached isolated audit worktree was
reused after confirming it was clean; the original checkout was preserved.

Changed files (19):

- Routes: `backend/app/api/v1/students.py`, `backend/app/api/v1/predictions.py`.
- Services: `backend/app/services/mutation_authorization.py` (new),
  `auth_service.py`, `casework_mutation.py`, `user_service.py`,
  `student_service.py`, `import_service.py`, `staged_import_service.py`,
  `prediction_service.py`, `outcome_prediction_service.py` (all under that same
  services directory).
- Tests: `backend/tests/api/test_d1_authorization_postgres.py`,
  `test_freshness.py`, `test_freshness_postgres.py`, `test_users_postgres.py`,
  `test_staged_imports_postgres.py`, `test_outcomes_postgres.py` (all under that
  same API test directory),
  plus new `backend/tests/auth_context.py`.
- Report: `docs/phase-d1-academic-write-authorization.md`.

## Covered endpoint and service boundaries

All paths below have `/api/v1` prefix. Existing entry-point role dependencies and
read access remain. Each committing Academic Admin transaction also checks the
authenticated actor inside its persistence boundary.

| Method/path | Explicit service actor / persistence boundary |
| --- | --- |
| POST `/students` | `StudentService.create_student(..., actor=...)` |
| PATCH `/students/{id}` | `StudentService.update_student(..., actor=...)` |
| DELETE `/students/{id}` | `StudentService.delete_student(..., actor=...)` |
| PUT `/students/{id}/admission` | `StudentService.upsert_admission(..., actor=...)`; both insert and update |
| PUT `/students/{id}/semester-1` | `StudentService.upsert_first_semester(..., actor=...)`; both insert and update |
| POST `/imports/csv` | `ImportService.import_csv(upload, actor)` parses first, then guarded `_persist_rows(..., actor=...)` |
| POST `/imports/staged/csv` | `StagedImportService.stage(upload, actor)` parses first, then guarded `_persist_stage(..., actor=...)` |
| PATCH `/imports/staged/{batch}/rows/{row}` | Guarded `correct(..., actor)` covers correction, exclusion and restoration |
| POST `/imports/staged/{batch}/commit` | Guarded `commit(..., actor)` covers successful commit, already-committed receipt and legitimate rejected-commit diagnostics |
| POST `/imports/staged/{batch}/cancel` | Guarded `cancel(..., actor)` |
| POST `/students/{id}/predictions` | `PredictionService.predict_student(..., actor=...)`; explicit stages delegate to guarded `OutcomePredictionService.predict_stage(..., actor=...)` |
| POST `/predictions/batch` | `PredictionService.predict_batch(..., actor=...)`; explicit stages delegate to guarded `OutcomePredictionService.predict_stage_batch(..., actor=...)` |

Prediction coverage includes explicit ENROLLMENT and FIRST_SEMESTER multiclass
plus omitted-stage legacy binary, for both single and batch requests. Public
request/response JSON is unchanged. Attribution is derived from the locked
actor; service callers can no longer authorize a prediction by supplying only
`created_by=<UUID>`.

Additional Academic Admin writes were traced rather than assumed safe: warning
assignment, intervention create/edit/note/complete/cancel/transfer, follow-up
create/edit/complete/cancel/recovery are already covered by C1's guarded service
decorator. Their domain locking, revisions, constrained action events, ownership
and historical records remain in that decorator. System Admin user/model
administration and self-service password change now share the extracted actor
primitive as well. Read-time/startup synchronization of the fixed trusted model
catalog and operator bootstrap remain their existing housekeeping operations;
they are not new Academic Admin bypasses or user-selected artifact writers.

## Shared authorization and lock-order contract

`services/mutation_authorization.py` contains a small authorization primitive,
`MutationAuthorization`, a transaction rollback/error boundary `academic_write`,
and a synchronous persistence decorator `academic_mutation`. It performs no
casework auditing, revisions, inference, retry or implicit commit.

1. Require the verified immutable `(subject UUID, token_version)` tuple already
   captured in `Session.info['presented_auth']` by request authentication. The
   explicit actor argument must match that subject. Missing context is 401; an
   arbitrary active ORM User is insufficient. Capture the version **before**
   any `populate_existing` or refresh can change the ORM object.
2. Acquire the existing transaction-scoped administration advisory mutex
   **610110009**, with the existing five-second PostgreSQL lock timeout.
3. Lock/refetch the actor and related users in sorted UUID order. Revalidate
   current activity, the original presented credential version, password-change
   requirement and allowed role. Academic persistence requires ACADEMIC_ADMIN.
4. Acquire domain locks/write rows afterward, retaining authorization locks
   until that transaction commits or rolls back.

C1 uses the same two-step primitive: acquire the mutex, read identities only to
locate relevant user/domain locks, lock sorted users and authorize, then lock
warning → intervention → sorted follow-ups. Its audit/revision logic is unchanged.
User administration prelocks sorted actor/target users before its safeguards;
model administration then follows its existing registry/model ordering.
Password change is the one intentional `allow_password_change` use, so required
temporary-password replacement continues to work. It still verifies the old
password, revokes old credentials and records its existing account audit.

Staged mutations take the mutex and actor lock before their existing batch row
lock/CAS and row validation. All participating academic/C1/account writers thus
use the same outer order. No outer route guard also acquires these write locks,
and stage delegation does not acquire a second guard around the same committing
unit. Read snapshots remain independent of this mutation mutex.

Error contracts:

- Lost activity/subject/credential version at transaction entry: 401
  `AUTHENTICATION_REQUIRED`, matching C1's pending-write revalidation contract.
- Required password replacement: 403 `PASSWORD_CHANGE_REQUIRED`.
- Current role denied: 403 `INSUFFICIENT_PERMISSIONS`.
- SQLSTATE `55P03`, `40P01`, `40001` escaping the academic write boundary cause
  whole-transaction rollback and 409 `ACADEMIC_WRITE_RETRYABLE_CONFLICT`, with
  `retryable: true`. No automatic retry is performed.
- C1 retains `CASEWORK_RETRYABLE_CONFLICT`; the existing staged batch reservation
  handler retains `STAGED_IMPORT_BUSY` for its domain-lock conflict. Stale
  versions, validation and lifecycle errors keep their existing codes.

The old fallback that could derive authorization claims from a refreshed ORM
actor is removed from shared account/casework/password guards. Older direct
service fixtures now establish an explicit verified token context using
`tests/auth_context.py`; that helper is test-only. New interleaving regressions
authenticate through the real HTTP login endpoint. No production “trusted
direct caller” switch or optional actor bypass is provided.

## Upload, commit and batch semantics

Both upload entry points first perform the existing bounded filename/content
read and structural CSV parse. They acquire **no authorization mutex/user row
lock while awaiting upload content**. Once parsed, they enter the synchronous
guarded persistence method and revalidate the request's original claims. Invalid
file structure may still fail before persistence/locking, with no domain writes.

Every internal commit was inspected:

| Existing transaction unit | D1.1 behavior |
| --- | --- |
| Student CRUD/upsert | One guarded mutation transaction; post-commit refresh is a read. |
| Immediate CSV import | Existing job/validation and per-row savepoints, followed by its existing outer commit. Valid rows and invalid-row diagnostics retain their original partial-result meaning. Savepoint rollback does not release the outer authorization locks. |
| Staged upload/correction/cancel | Existing single committing transaction after authorization. |
| Staged commit | Existing atomic student-graph savepoint and batch CAS. Authorized validation/unique-conflict rejection can still commit its rejection diagnostic/audit and then return 409. No later mutation follows that commit. An unauthorized request fails before reservation, version changes or audit. |
| Already-committed staged retry | Reauthorize before returning the existing receipt; no duplicate graph/job/action or version advance. Request-session close releases the read transaction/locks. |
| Legacy single/batch registry synchronization | Preserve `synchronize_registry()`'s existing internal commit, under its own authorized unit. |
| Legacy prediction persistence after synchronization | Start a **new** authorization unit, rechecking the original presented version before inserting any prediction/warning. A registry commit never authorizes this next transaction. |
| Multiclass single/batch | Existing committing prediction/warning transaction, now guarded. Model activation metadata is locked after authorization. |

At this fetched base, prediction batches already collect eligible students and
commit their prediction/warning group once; they report skipped-not-ready counts
and append again on repeated runs. D1.1 does **not** introduce a new per-record
commit loop, new all-or-nothing wrapping, deduplication or retries. Those existing
payload commit units and partial eligibility/count semantics are retained. Legacy
execution additionally retains its earlier registry synchronization commit.

Revocation before a unit's authorization rejects it with no unauthorized domain,
batch-version or success-action persistence. Revocation while a guarded payload
unit owns the locks must wait until that unit commits/rolls back; it does not
interrupt between records inside that same transaction. Revocation can win in
the gap after legacy registry synchronization: previously authorized catalog
work may remain, but **no prediction/warning** may be written by the next unit.
The regression suite explicitly controls and verifies this gap.

Successful and rejected imports retain their existing schema/limits, duplicate
rules, canonical values, atomic graph behavior and diagnostics. Global writer
serialization means two ordinary staged commits with the same student number
now normally discover the loser during revalidation (`STAGED_IMPORT_NOT_READY`)
rather than by forcing both past validation simultaneously. A real external
fixture writer separately exercises the existing unique-constraint/savepoint
`STAGED_IMPORT_COMMIT_CONFLICT` path; that fallback remains intact.

Prediction feature assembly, model/stage selection, probabilities, explanations,
warnings and append-only history are unchanged. B2's operational freshness and
support selection are not rewritten. C1's domain action list, revisions,
structured history, explicit closure/recovery and account safeguards are not
expanded to students/imports/predictions. No schema migration is needed.

## Compatibility and contention

Internal service APIs intentionally require `actor` and an authenticated session
context. Callers of the old UUID-only prediction signature or actor-less student
methods must be updated; HTTP API payloads and permissions stay the same. A
request authenticated before a concurrent password reset/role change can now
receive the intended 401 when its persistence unit begins. A caller must refresh
and make an explicit new decision after a retryable conflict.

The required shared mutex serializes unrelated academic/account/C1 writes.
Large imports and inference batches can hold it through CPU work and persistence,
so competing requests may exceed the five-second lock timeout and return 409.
This is a correctness-first tradeoff, not a throughput improvement. Bounded
upload reading occurs outside the mutex, but database-aware validation and actual
inference remain inside their persistence units. No exhaustive stress or
multi-process external-writer correctness proof is claimed. Future committing
writers must join the documented order and reauthorize after any internal commit.

Lost responses after a successful commit retain the existing request-retry
limitations; predictions remain append-only rather than automatically idempotent.
Existing staged receipt retries are preserved. No new distributed idempotency
facility is introduced.

## Verification, artifact integrity and cleanup

The former six unsafe D1 PostgreSQL characterization cases are replaced with
regressions. The expanded module contains 163 cases:

- 126 interleavings: 21 operation variants × deactivation/demotion/password reset
  × both commit orders. These use real HTTP login and account-management
  endpoints, separate request/database sessions and observed PostgreSQL lock
  waits. Revocation-first additionally refreshes the ORM actor before the guard
  to prove that refreshed token versions cannot replace the original claims.
- Six legacy registry/payload transaction-gap cases and six delayed-upload
  cases. Upload tests inspect granted advisory locks while reading is paused.
- Nine current activity/role/required-password checks without a token-version
  bump, six direct-service no-authentication-context denials, three real lock
  timeouts with successful explicit retries, six actual database-failure
  rollbacks, and one actual staged unique-constraint/savepoint collision.

Denied/rolled-back requests compare complete persisted public-table snapshots,
excluding only legitimate account/login/account-audit changes from revocation.
Successful predictions assert the requested real model family and batch counts.
No successful authorization, inference or persistence is substituted in these
interleavings. Existing C1 and staged receipt/concurrency suites also run.

Verification uses Python 3.11.9, the pinned backend environment and a disposable
native PostgreSQL 18.3 cluster on port 55479. Each D1 case migrates a random
`d11_authorization_*` database to head and drops it in fixture cleanup. Other
PostgreSQL fixtures retain their existing disposable database/schema cleanup.
Private connection settings and logs stay under ignored `.venv`; credentials
and tokens are not report evidence or tracked files.

Actual commands (repository root unless stated otherwise):

```powershell
# From backend; private local settings select only the owned disposable cluster.
$qa = Get-Content ../.venv/d1-settings.json | ConvertFrom-Json
$env:D1_AUDIT_TEST_DATABASE_URL = $qa.database_url
$env:RUN_MODEL_INTEGRATION = '1'
../.venv/Scripts/python.exe -m pytest -q tests/api/test_d1_authorization_postgres.py -x
../.venv/Scripts/python.exe -m pytest -q tests/api/test_d1_authorization_postgres.py -k 'is_active or authorized_staged_unique_collision' -x

# Relevant HTTP/domain regression suite.
../.venv/Scripts/python.exe -m pytest -q tests/api/test_students.py tests/api/test_imports.py tests/api/test_staged_imports.py tests/api/test_predictions.py tests/api/test_outcome_predictions.py tests/api/test_users.py tests/api/test_auth.py tests/api/test_freshness.py

# C1/account/staged PostgreSQL checks: respective URLs set to the same disposable server.
foreach ($setting in @('C1_CASEWORK_TEST_DATABASE_URL','USER_MANAGEMENT_TEST_DATABASE_URL','STAGED_IMPORT_TEST_DATABASE_URL')) {
  [Environment]::SetEnvironmentVariable($setting, $qa.database_url, 'Process')
}
../.venv/Scripts/python.exe -m pytest -q tests/api/test_casework_integrity_audit_postgres.py tests/api/test_users_postgres.py tests/api/test_staged_imports_postgres.py -x
../.venv/Scripts/python.exe -m pytest -q tests/api/test_outcomes_postgres.py::test_concurrent_activation_is_audited_once_and_scope_uniqueness_is_enforced

# Full backend: no PostgreSQL group or real-model integration disabled.
foreach ($setting in @('MODEL_TEST_DATABASE_URL','DUAL_STAGE_TEST_DATABASE_URL','STAGED_IMPORT_TEST_DATABASE_URL','USER_MANAGEMENT_TEST_DATABASE_URL','FRESHNESS_TEST_DATABASE_URL','C1_CASEWORK_TEST_DATABASE_URL','D1_AUDIT_TEST_DATABASE_URL')) {
  [Environment]::SetEnvironmentVariable($setting, $qa.database_url, 'Process')
}
../.venv/Scripts/python.exe -m pytest -q

../.venv/Scripts/python.exe -m app.ml.deployment verify
../.venv/Scripts/python.exe -m app.ml.outcomes.deployment verify
../.venv/Scripts/python.exe -m alembic heads

# From repository root; Ruff 0.17.1 is isolated from application dependencies.
.venv/audit-tools/Scripts/ruff.exe check backend/app --select F,E9
.venv/audit-tools/Scripts/ruff.exe check backend/tests/api/test_d1_authorization_postgres.py backend/tests/auth_context.py --select F,E9
$changedPython = @(git diff --name-only -- '*.py') + @('backend/app/services/mutation_authorization.py','backend/tests/auth_context.py')
.venv/audit-tools/Scripts/ruff.exe check $changedPython --select E9,F63,F7,F82
.venv/audit-tools/Scripts/ruff.exe format --check $changedPython
git diff --check
```

Verification results:

The first full attempt completed with 543 passed and one failure (298 warnings,
985.80 s): an older direct model-activation concurrency fixture still supplied
only an ORM actor and was correctly denied by the extracted guard. That fixture
now verifies its explicit token context before both validation and concurrent
activation; its original concurrency/scope assertions and production guard are
unchanged. The focused corrected case passed, and the full suite was restarted
against implementation/source commit `b45058c02c731a5913221aa85a3f1247910c6c77`.

| Check | Result |
| --- | --- |
| Targeted D1 PostgreSQL module, initial 160-case collection | 160 passed, zero skipped, 458.39 s |
| Added inactive-account cases plus unique-collision regression | 4 passed, 159 deselected, 15.67 s |
| Relevant student/import/prediction/account/auth/freshness tests | 144 passed, 48 warnings, 147.46 s |
| C1/account/staged PostgreSQL suites | 94 passed, zero skipped, 203.79 s |
| Model-activation concurrency fixture after explicit auth-context update | 1 passed, zero skipped, 6.00 s |
| Final full backend, all seven PostgreSQL URLs and real models enabled | **544 passed, zero skipped**, 298 warnings, 983.62 s; includes all 163 D1.1 PostgreSQL cases |
| Focused Ruff lint, changed-file formatting and `git diff --check` | Passed |
| All three artifact verifiers | Passed; no artifact/registry changes |
| Alembic head | `20261014_0012` |

An independent read-only connection during the final full run also executed
`SELECT version_num FROM alembic_version` against live fixture
`d11_authorization_308e979f16cd4e228dff6b0e05e55a01` and observed
**`20261014_0012`**. This confirms an actually migrated database, in addition to
the configured single head and the migration assertions in the existing suites.

The three verified artifact SHA-256 values, independently hashed on disk:

| Registered model | SHA-256 |
| --- | --- |
| `dropout-logistic-regression-v1` | `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8` |
| `enrollment-outcome-v1` | `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602` |
| `first-semester-outcome-v1` | `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81` |

Frontend typecheck/build was not rerun: no frontend files or frontend-facing JSON
contracts changed. Registered artifacts were neither retrained nor replaced;
dependency specifications remain unchanged.

Docker was checked again after the implementation was complete:
`docker desktop status` reports **stopped** and
`docker version --format '{{json .Server}}'` exits 1 with
`Docker Desktop is unable to start`. No D1.1 final-source containers could be
built or exercised, so there are no D1.1 image IDs or container-smoke results.
Native PostgreSQL/real-artifact results are the verification evidence for this
change; prior C1/B2 container smoke is not presented as D1.1 verification.

The unavailable engine also prevents ownership-label inspection of residual
project `d1-audit-8ff43a5b`. Its cleanup remains unconfirmed. No cleanup was
attempted against that project in this delivery because ownership could not be
checked. No shared service was restarted, no context was changed, no resources
were pruned and no previously blocked deletion command was repeated.

The final run's 298 warnings come from the existing pandas explanation-feature
dtype perturbation and synthetic probability-test checks. They were not hidden
or repaired through unrelated model/dependency changes.

After pytest completed its tests and fixture teardown, a read-only ownership
check confirmed PostgreSQL's `data_directory` resolved exactly to this worktree's
`.venv/d1-pg`. The cluster contained **zero disposable databases**, **zero other
client connections**, only its default `public` non-system schema and **zero
tables** in `postgres/public`. All generated fixture databases/schemas had been
dropped. The owned cluster was then stopped and port **55479 had zero listeners**.

Actual cleanup commands, from this worktree root:

```powershell
# Private local QA helper asserts the exact data directory, queries pg_database,
# pg_stat_activity and information_schema, and refuses to proceed if data/clients remain.
.venv/Scripts/python.exe .venv/d11-cleanup-check.py
& 'C:/Program Files/PostgreSQL/18/bin/pg_ctl.exe' -D .venv/d1-pg -m smart -w stop
@(Get-NetTCPConnection -LocalPort 55479 -State Listen -ErrorAction SilentlyContinue).Count
```

The ignored native-cluster directory, private settings, prior audit dump and
verification logs/helpers are retained locally. No recursive filesystem removal
was retried. The original checkout and other infrastructure were left alone.
Docker project cleanup remains the separate unconfirmed limitation above.

## Remaining D1 findings

The original [D1 audit](phase-d1-release-readiness-audit.md) remains a dated
historical record. Only D1-01 is addressed here. D1-02 login abuse controls,
D1-03 public deployment configuration, D1-04 secret provisioning/validation,
D1-05 stage-aware aggregate readiness, D1-06 CI/skip gates, D1-07 dependency
advisories, D1-08 dependency provenance, D1-09 primary model handoff,
D1-10 operating/recovery runbooks and optional D1-11 canonical-export guidance
remain outside this delivery. Their unrelated characterization tests are not
changed to imply those findings are fixed. The previously closed B2 targeted
container verification gap remains closed.
