# Phase C1 casework integrity implementation

Base: `8485dbdba8b64625a96adf339f9b18d3e5f24f76`.
Branch: `codex/phase-c1-casework-integrity`.
Scope: C1 only. No PR, merge, subsequent phase, production data repair, deployment-model
retraining or artifact replacement. Existing suite fixtures fit temporary synthetic
models outside deployment artifact paths. The B2 final-source Docker workflow gap in
`phase-b2-prediction-freshness.md` remains open; the C1 checks below do not close it.

## Ownership and intentional API changes

The intervention owner is canonical for every stored `SCHEDULED` follow-up.
`DUE` and `OVERDUE` are read projections of that same stored state. Warning
assignment remains independent triage responsibility.

- `POST /api/v1/interventions/{id}/transfer`: Academic Admin only. Requires
  `assigned_to`, nonblank `reason`, and nonnegative `expected_revision` of the
  intervention. Locks/refetches and validates the active Advisor target. Changes
  the parent and every scheduled contact in one transaction; each receives a new
  revision and an action event sharing one correlation UUID. Completed/cancelled
  contact assignments and their domain history remain unchanged. A transfer to
  the existing owner returns 409 `INTERVENTION_ALREADY_ASSIGNED`.
- Generic intervention PATCH rejects assignment fields with
  `EXPLICIT_TRANSFER_REQUIRED`. Generic follow-up PATCH rejects assignment fields
  with `EXPLICIT_RECOVERY_REQUIRED` (existing advisor role denials still apply).
  Direct scheduling rejects independent delegation with
  `INDEPENDENT_FOLLOW_UP_DELEGATION`; the client uses the case owner.
- Intervention complete/cancel returns 409
  `INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS` with `follow_ups` count and
  `follow_up_ids`. Contacts require their own explicit outcomes/cancellation
  reasons first. Both direct scheduling and successor insertion use the same
  nonterminal-parent gate and return `INVALID_FOLLOW_UP_TRANSITION` for completed
  or cancelled parents. Completion plus optional successor is atomic. A contact
  outcome, including `INTERVENTION_COMPLETED`, never changes parent status.
- Terminal intervention notes remain append-only under the existing owner/Admin
  RBAC. There is no terminal intervention reopen/reassign operation.
- `POST /api/v1/warnings/{id}/reviews` now handles `PENDING_REVIEW` only;
  reviewed warnings return `EXPLICIT_RECONSIDERATION_REQUIRED`.
- `POST /api/v1/warnings/{id}/reconsider`: currently assigned active Academic
  Advisor only; requires decision, nonblank note/reason and expected warning
  revision. Appends a review, preserving previous reviewers/decisions. Both paths
  block dismissal with 409 `WARNING_HAS_ACTIVE_SUPPORT`, including counts and IDs
  for nonterminal interventions and scheduled contacts under any linked parent.
  Nothing automatically cancels support. Reconfirmation permits new case creation
  under the existing confirmed-warning rules.

Historical dismissed warnings and their existing support remain readable.
Existing warning/prediction links, snapshots, model identity and review/note/account
history are retained. Current operational risk still uses the B2 selector; warning
risk remains historical and is labelled as such in the warning detail.

## Historical inconsistencies and explicit recovery

No migration, startup task or read query rewrites inconsistent records.
`GET /api/v1/casework/integrity` is a read-only institution-wide diagnostic for
all existing read roles. Follow-up responses also expose `parent_status`,
`parent_assigned_to`, and `integrity_issues` (`OWNER_MISMATCH`, `TERMINAL_PARENT`).

`POST /api/v1/follow-ups/{id}/recover` is Academic-Admin-only and requires a
nonblank reason and expected contact revision:

- `ALIGN` changes only a scheduled contact to its active, nonterminal parent's
  Advisor owner. It cannot assign an arbitrary owner or repair a terminal parent.
- `COMPLETE` resolves a scheduled contact under a historical terminal parent,
  requiring a genuine outcome and nonblank evidence notes.
- `CANCEL` resolves such a contact with its explicit cancellation reason.

Extra fields, including successor scheduling, are rejected on recovery DTOs.
Ordinary child mutations reject unresolved integrity issues with
`CASEWORK_RECOVERY_REQUIRED`. Recovery audits the prior contact owner and values;
terminal parents retain their status, owner and historical completion data. No
successor is inserted. Recovery only increments the changed contact's revision.
Scheduled historical obligations remain visible and block their assigned advisor's
deactivation/demotion until resolved. Original case and contact ownership may
therefore legitimately reference different historical users after resolution.

The Follow-Ups page includes diagnostics and selected-record recovery controls.
The dossier and global casework views share those supported action rules. Transfer
shows the affected scheduled count; reasons and active-advisor selection use the
existing form components. There is no completed-case monitoring/scheduling control.

## Transaction and authorization boundary

`casework_mutation.py` guards all service writes for warning assignment, initial
review, reconsideration, case creation/edit/note/closure/transfer, child
creation/edit/completion/cancellation and recovery. Database sessions preserve the
presented `(subject, token_version)` claims separately in `Session.info`; refreshing
an ORM actor cannot replace the presented version with a newly revoked version.

Lock order:

1. Transaction-scoped administration advisory mutex **610110009**.
2. Actor and relevant target/owner users, sorted by UUID. Actor activity, current
   role, password-change requirement and presented token version are revalidated.
3. Warning.
4. Parent intervention.
5. Follow-up, or scheduled transfer contacts sorted by UUID.

Identity reads after the mutex only locate the rows to lock; they confer no
permission. Parent identity reads refresh cached ORM values. Child authorization
occurs only after locked parent refetch. Existing service re-locks occur on rows
already held by the guard. User administration now also prelocks actor/target in
UUID order under the same mutex. Password change joins that mutex before its
user lock. Bootstrap already uses it. Login takes only user locks and never
acquires the mutex/domain locks afterward, so it introduces no reverse order.
Read-only B2 snapshots do not take this mutation mutex.

All authorization locks remain held through commit/rollback:

- **Revocation wins:** the already-authenticated pending mutation rejects after
  the guard refreshes the actor; it leaves no domain changes or success events.
- **Guarded casework wins:** the mutation commits before revocation can finish.
  Deactivation/demotion still independently checks all active assignments and can
  remain blocked. Password reset revokes tokens and requires a password change.

Existing last-System-Admin, self-deactivation, role, assignment and historical-FK
safeguards remain enforced. The global mutex intentionally serializes unrelated
casework/account writes and may cause contention. It is a correctness-first C1
boundary, not a throughput optimization. Each participating transaction has a
five-second PostgreSQL lock timeout. SQLSTATE `55P03`, `40P01`, and `40001` become
409 `CASEWORK_RETRYABLE_CONFLICT` with `retryable: true` after whole-transaction
rollback. There is no automatic or partial transaction retry. These tests do not
constitute exhaustive load testing or a proof against every possible external
writer/deadlock; future writers must join the documented order.

## Revisions, stale writes and audit migration

`20261014_0012` follows `20261013_0011` and adds nonnegative integer revisions to
warnings/interventions/follow-ups, plus `casework_action_audit`. Existing rows
start at **zero**, denoting adoption only; the migration inserts no historical
events and never infers actors from `created_by`.

Transfer, reconsideration and recovery require an expected revision. Other
existing editable actions accept it optionally for compatibility. When supplied,
a mismatch returns 409 `STALE_RESOURCE_REVISION` with entity ID, expected/current
revision and `retryable: false`; omitted versions mean an explicit serialized
operation against the latest locked state, not stale-form protection. First-review
and lifecycle gates still prevent repeated terminal decisions. New clients pass
revisions from displayed authoritative resources (parent revision for scheduling,
child revision for child edits). Creation of a case rechecks its locked warning.

Successful guarded actions advance the affected revision; ordinary child writes
also advance their parent, case creation advances the warning, and note append
advances the intervention. This deliberately invalidates transfer/closure forms
when child obligations change. Even a permitted no-op edit/assignment advances
its root revision and records the successful action. New casework resources created by guarded actions start with a creation
action/revision. Automatically generated prediction warnings remain at zero until
their first C1 human action; no artificial creation history is inferred.

The UI refreshes authoritative records on conflicts and requires a new user
submission. It never silently repeats a mutation. Dashboard/dossier dialogs that
hold stale warning snapshots close while refreshing; warning detail and follow-up
views refresh their resource. Structured blocker counts/IDs reach existing alert
surfaces. A lost response after commit has no general request-id deduplication:
refresh before deciding whether to submit a new action. Required-version actions
reject replays of the previous version; terminal transition gates protect repeated
completion/cancellation. Append-only notes should be checked before resubmission.

Events contain an event UUID, actor FK, constrained action, warning/case/contact
links as applicable, server timestamp, explicit reason when required, safe domain
before/after values, and request correlation UUID. No user credential/JWT columns
are read into event metadata. Revisions, domain changes and events commit together;
injected persistence failures prove that no success audit survives rollback.
Existing review/note/user-administration tables remain separate and retained.
There are no event edit/delete endpoints.

Upgrade is additive, taking ordinary DDL table locks; schedule it appropriately.
Downgrade removes only C1 revision columns and the new action table (and therefore
loses C1 action history/version values). It never changes historical domain
columns. Export C1 action history before a deliberate downgrade if it is needed.
No operational database was migrated during verification; disposable fixtures only.

## Verification and limitations (14 October 2026)

Final results and cleanup are recorded below. Source-level changes to older tests
retain their original safeguard/history assertions while updating the migration
head, actor-aware direct service call, and explicitly selected historical columns.
The C1 audit characterization assertions have been replaced by regression
assertions; none continue to assert that a stranded transfer or unsafe terminal
successor is accepted.

The PostgreSQL matrix uses real FastAPI endpoints, signed tokens, per-request
sessions and UUID-named disposable databases. Timing gates pause actual row-lock
boundaries and observe `pg_stat_activity` lock waits before releasing the winner.
The revocation-wins scenario additionally pauses after authentication but before
guard entry, allowing account revocation to commit first. No service results or
PostgreSQL locks are substituted. Historical inconsistency fixtures are explicit
test setup, not a production repair path.

Coverage includes multi-contact transfer, completed/cancelled contact preservation,
old/new advisor permissions, delegation rejection, blocked closure/dismissal,
identical direct/successor gates for every parent state, reasoned reconsideration,
audited recovery, actor role/activity/password/token refresh, every original
account safeguard, and transfer/successor/audit rollback. Controlled interleavings
cover both orders of transfer vs child edit/complete/cancel/successor, closure vs
scheduling/resolution, warning assignment vs review, dismissal vs case creation,
recovery vs child completion, and account changes vs assignment/authenticated
casework writes. Competing child terminal actions and real lock timeout are covered.
Populated migration round-tripping checks original domain column equality and
zero initial revisions/no fabricated events on re-upgrade.

Native commands from `backend/` (all six database URL variables point to the same
**dedicated CREATE DATABASE server**, never an institutional database):

```powershell
$pg = 'postgresql+psycopg://b1_test@127.0.0.1:55449/postgres'
$env:C1_CASEWORK_TEST_DATABASE_URL = $pg
$env:FRESHNESS_TEST_DATABASE_URL = $pg
$env:MODEL_TEST_DATABASE_URL = $pg
$env:DUAL_STAGE_TEST_DATABASE_URL = $pg
$env:STAGED_IMPORT_TEST_DATABASE_URL = $pg
$env:USER_MANAGEMENT_TEST_DATABASE_URL = $pg
$env:RUN_MODEL_INTEGRATION = '1'
..\.venv\Scripts\python.exe -m pytest -q --tb=short
..\.venv\Scripts\python.exe -m app.ml.deployment verify
..\.venv\Scripts\python.exe -m app.ml.outcomes.deployment verify
..\.venv\Scripts\python.exe -m alembic heads
```

From the repository root:

```powershell
npm --prefix frontend run typecheck
npm --prefix frontend run build
# Changed Python files; B008/SIM102/C408 are inherited project idioms.
.venv\Scripts\python.exe -m ruff check --extend-ignore B008,SIM102,C408 <changed-python-files>
git diff --check
docker build --target runtime -t zak-c1-backend:verification backend
docker build -t zak-c1-frontend:verification frontend
docker run --rm zak-c1-backend:verification python -m app.ml.deployment verify
docker run --rm zak-c1-backend:verification python -m app.ml.outcomes.deployment verify
```

Playwright CLI used an isolated browser session against frontend port 3012 and
backend port 8012, backed by a disposable PostgreSQL database. It exercised actual
sign-in, Admin transfer/recovery, blocked closure, stale edit refresh without retry,
old-owner denial, new-owner completion, explicit case closure, removed terminal
scheduling controls, blocked and successful reconsideration, preserved review
history, and desktop/mobile layouts (390 px, no horizontal document overflow).
Screenshots/scripts are local verification artifacts in ignored `output/playwright/`.
Expected 403/409 requests appeared in the browser network console; no unexpected
application error was observed in the completed workflows.

C1 container checks build the runtime images, execute the three artifact verifiers,
then use an isolated network, a PostgreSQL 16 container with tmpfs data (no volume),
and C1 backend/frontend containers. Smoke checks verify readiness, migrated head,
empty initial action audit, and frontend HTTP 200. They do **not** run the B2
cross-screen freshness/reassessment workflow and do not close its documented gap.
The full regression suite and browser workflows are **native PostgreSQL 18**
evidence, not container regression/browser evidence.

Original model SHA-256 values remain:

- Legacy: `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8`
- Enrollment: `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602`
- First semester: `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81`

A changed-file manifest is `phase-c1-changed-files.txt`. Final commit identity is
reported in the delivery message (the commit cannot contain its own hash).


### Recorded results

- Full backend suite with all PostgreSQL integration URL variables and
  `RUN_MODEL_INTEGRATION=1`: **369 passed, zero skipped**, 434.27 seconds.
  The existing suite emitted 238 pandas/sklearn fixture warnings; deployed
  artifacts passed verification and were not modified. This run includes B2
  risk selection, institution-wide support visibility, account safeguards and
  the C1 concurrency/migration tests.
- A subsequent final C1 module run covers the added pending-review dismissal
  assertion and strengthened multi-record rollback/terminal-history fixtures;
  its result is recorded with cleanup below. No backend runtime change followed
  the successful full-suite run.
- Native frontend typecheck and production build: passed. Changed-file Ruff
  check and `git diff --check`: passed. Artifact verifiers: all three passed
  both natively and in the rebuilt C1 backend image.
- Browser workflows: passed (real API/database, no mutation-result mocks).
  Stale edit retained the competing authoritative value, with no automatic
  mutation retry; expected blocker/permission responses were exercised.
- C1 runtime images rebuilt after implementation: backend
  `sha256:ec2b5788369ab5d8b975080da9f60cdc5907179d38cbff6070048a1f6dc89a14`,
  frontend
  `sha256:4a2c1846f15d0806ae31491248875f9058932049ad85827f75bc8d490577f490`.
  The isolated final image smoke passed readiness, schema head `20261014_0012`,
  zero initial C1 events, and frontend HTTP 200. C1 containers and network
  `6783793bc7ef` were removed; the earlier smoke's `8c937faf863e` resources were
  also removed. Both used tmpfs PostgreSQL data and no persistent volume.
  Verification image tags/cache are retained locally; no shared images or old
  B2 project resources were removed.

The first broad run had four obsolete harness failures (old schema head/column
comparisons, and a direct assignment service call without its now-required actor).
These were updated while preserving the original domain-history and account
safeguard checks; the complete rerun passed. Early C1 test harness corrections
included explicitly typed PostgreSQL enum fixtures, valid test password hashes,
parent-context vs stored-contact comparisons, and expecting stale transfer forms
when a child mutation wins. No defect-characterization assertion was retained as
an assertion that unsafe behavior should succeed.


Final C1 module result: **81 passed, zero skipped**, 119.54 seconds. This was
run after strengthening the terminal-history/multi-contact rollback fixtures and
adding the initial-review dismissal blocker regression (one test beyond the 369-test
full run). All current tests were exercised across these runs.

Cleanup confirmed `SHOW data_directory` points to the dedicated workspace
`.venv/b1-pg` cluster, PostgreSQL 18.3. Queries returned **zero** databases under
`casework_c1_audit_`, `freshness_b2_test_`, `outcomes_b1_test_`, `users_a2_test_`,
and `model_a1_test_`, **zero** `staged_test_` schemas, and no other client connections.
The browser fixture database was dropped by its finalizer; its backend and the
port-3012 frontend were stopped, and the isolated Playwright session was closed.
The native test server started for C1 was shut down with `pg_ctl -D .venv/b1-pg -w
stop`; its existing data directory was retained. No institutional database,
shared image, or unrelated B2 resource was changed during cleanup.

Remaining limits: the shared mutex trades write throughput for straightforward
serialization; no exhaustive stress/production-data audit or distributed
idempotency facility is claimed. Existing warnings in synthetic model tests are
unchanged. The B2 final-source container freshness workflow remains unverified by
this C1 delivery, despite successful C1 image smoke checks.
