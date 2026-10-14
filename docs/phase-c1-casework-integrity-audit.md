# Phase C1 casework integrity audit and proposed contract

## Scope and evidence

Audit base: `cf4432d8caf0bd63b9bf1b7f13e21f02a82a394e`, containing B2
implementation `6727cac3f1aa619e02d384e21a6fe38a44005032`. Audit branch:
`codex/phase-c1-casework-integrity-audit`. This delivery adds characterization
tests and this report only. It changes no production services, frontend actions,
models, migrations, institutional records or deactivation safeguards. No model
training is needed or performed. The B2 final-image Docker gap remains open.

The reviewed sources are the warning/casework/user services, their repositories,
API dependencies and routes, schemas and models, original migrations 0006/0007,
account migration 0009, B2 read projections, account administration documentation,
Phase 7 casework decisions, and frontend warning, intervention, follow-up,
dossier and user actions. All endpoint paths below have prefix `/api/v1`.

Tests in `backend/tests/api/test_casework_integrity_audit_postgres.py` call the
real FastAPI endpoints with signed JWTs and a real per-request SQLAlchemy session.
Each test migrates a new UUID-named disposable PostgreSQL database to
`20261013_0011`, then drops only that database. Historical prediction values are
explicit casework fixtures, not inferred model results; real warning assignment,
review, intervention and follow-up routes create the support graph. The test
module overrides the existing synthetic-training autouse fixture so the audit
does not fit even a temporary model. No SQLite fixture provides this evidence.

## Current endpoint behavior

| Endpoint/action | Actual rule and source evidence |
| --- | --- |
| PATCH `/warnings/{id}/assignment` | Academic Admin only. Nullable assignee permits unassignment. Locks warning, then locks/refetches prospective advisor and requires active Advisor. Does not transfer linked cases or contacts. No actor is passed into `WarningService.assign`. `warning_service.py:125`; `warning_repository.py:29`. |
| POST `/warnings/{id}/reviews` | Assigned Advisor only; requires assignment, decision and nonblank note. Locks/refetches warning; appends `WarningReview`, updates current review state. No check for pending state or active linked cases. `warning_service.py:144`. |
| POST `/interventions` | Academic Admin or assigned warning Advisor; warning must be CONFIRMED and match student. Advisor may assign only self, Admin any active Advisor. Locks warning and prospective assignee. Multiple cases per warning remain permitted. `casework_service.py:243`. |
| PATCH `/interventions/{id}` | Academic Admin or case owner. Terminal cases cannot change. Admin can transfer; active Advisor target required. Only parent assignee changes. Allowed nonterminal transitions: PLANNED → IN_PROGRESS → ACTION_REQUIRED → IN_PROGRESS. `casework_service.py:291`. |
| POST `/interventions/{id}/complete` or `/cancel` | Admin or case owner; any nonterminal status accepted. Completion requires outcome/notes; cancellation requires reason. Only parent changes; scheduled follow-ups remain. Repeat terminal request gives 409. `casework_service.py:386,408`. |
| POST `/interventions/{id}/notes` | Admin or case owner; append-only attributed note. Terminal case notes remain permitted. `casework_service.py:360`. |
| POST `/interventions/{id}/follow-ups` | Admin or parent owner; rejects CANCELLED parent, allows COMPLETED parent. Target must be active Advisor. Admin can select a different advisor from parent; Advisor self only. Parent and target user locked. `casework_service.py:459`. |
| PATCH `/follow-ups/{id}` | SCHEDULED only; Admin or Advisor owning BOTH child and parent. Admin can reassign to any active Advisor, independently of parent. Locks child only, even though ownership depends on parent. `casework_service.py:493`; repository `follow_up:56`. |
| POST `/follow-ups/{id}/complete` | Same dual ownership; SCHEDULED only. Outcome/notes/time stored. Optional successor inherits child assignee and is inserted in same transaction. No parent-terminal or fresh target-user eligibility check. `casework_service.py:533`. |
| POST `/follow-ups/{id}/cancel` | Same dual ownership and SCHEDULED gate; reason stored in notes. Parent terminal state does not prohibit cancellation. `casework_service.py:571`. |
| GET casework/history | All three active roles can read institution-wide, not only own assignments. FKs use RESTRICT and records remain linked. B2 profile returns warning history and support separately from current risk. |
| PATCH `/users/{id}`, POST `/users/{id}/deactivate` | System Admin only. Global administration advisory lock, refreshed actor/token/activity/role, then target user lock. Advisor changes blocked by ANY nondismissed warning, nonterminal intervention or SCHEDULED contact, with counts. Historical-only ownership allowed. Role/deactivation revokes token version; history retained. `user_service.py:43,165,187,219,265`. |

## Findings by requested scenario

### 1. Transfer and follow-up ownership

**D1 — verified functional defect: scheduled work becomes unactionable by either
advisor.** Transferring parent A → B returns 200 while child stays assigned to A.
A fails the parent-owner condition; B fails the child-owner condition. Both
receive 403 `FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR`. No automatic recovery or
advisor acceptance flow exists. Academic Admin can PATCH each scheduled child
to B, after which B can act; Admin can also complete/cancel it directly.

The same mismatch can be created without a transfer: Academic Admin schedules a
contact for B on A's case and gets 201, but both advisors receive 403 when acting.
This is inconsistent with presenting B as the operational contact assignee.
Whether independently delegated contact ownership should be supported is an
unresolved product decision; current dual-owner authorization and independently
editable assignment fields cannot provide that delegation.

Terminal contacts cannot be reassigned (409), and terminal cases cannot be
transferred (409). Their original ownership is history and should remain so.
An active scheduled child under a terminal case can still be manually reassigned
by Academic Admin, which provides recovery from a mismatched historical parent.

**D3 — verified PostgreSQL authorization race:** completion loads/locks child
with parent A, pauses; Admin transfers parent to B and commits; old advisor A
then completes contact and creates a successor for A with 200. Parent ownership
is joined for authorization but is not locked/refreshed after the transfer.
This is demonstrated with real transactions, not inferred from SQLite locks.

### 2. Confirmed warning dismissed with active interventions

**P1 — verified behavior, unresolved lifecycle policy.** The assigned Advisor
can POST another review on a CONFIRMED warning: DISMISSED returns 201; both
reviews remain attributed. Existing PLANNED case and SCHEDULED contact stay
active. Case owner can subsequently start that case with 200. New intervention
creation requires CONFIRMED, but case mutation does not recheck warning state.
There is no automatic closing, deletion or reparenting of support.

Existing written Phase 7 rules require confirmation **at case creation**; they
do not require confirmation throughout the case's lifetime. It would be
incorrect to claim a documented prohibition on later dismissal already exists.
However, frontend `lib/warnings.ts:5` and the warning review modal only expose
review for PENDING_REVIEW. The API supports reversal that ordinary UI hides.
Decide whether reviews are once-only, append-only reversible decisions, or need
a separate explicit reconsideration action; also decide whether active support
blocks dismissal. Do not silently discard the active institutional obligations.

### 3. Terminal intervention with scheduled contacts

**D2 — verified lifecycle gate bypass:** cancelling a case returns 200 and keeps
its contact SCHEDULED. Direct schedule POST then returns 409
`INVALID_FOLLOW_UP_TRANSITION`, consistent with the documented cancellation
rule. Completing the old contact with `next_follow_up_at` nevertheless returns
200 and creates a new SCHEDULED contact under the CANCELLED case. The successor
path bypasses the explicit creation gate. Completion without a successor is
also currently permitted under a cancelled parent.

**P2 — verified behavior, unresolved post-completion policy:** completion of the
parent leaves contacts pending; direct scheduling under COMPLETED returns 201;
contact completion can add another successor. Frontend `lib/follow-ups.ts:68`
and `dossier/case-detail.tsx:292` intentionally exclude CANCELLED only. Completed
case monitoring is therefore an existing supported behavior, not automatically
a defect. A stricter no-new-work-after-completion rule would change that policy.

Existing scheduled contacts still contribute to overdue/due counts and account
deactivation blockers even when parent is terminal. Recording the contact
outcome INTERVENTION_COMPLETED does not complete its parent (Phase 7 decision).

### 4. Account deactivation and role change

**S1 — verified safeguard, preserve it.** For BOTH deactivation and role change,
each isolated blocker independently returns 409
`ADVISOR_HAS_ACTIVE_ASSIGNMENTS`, with correct warning/case/contact counts.
Pending and confirmed warnings both block; dismissed history does not. Any
SCHEDULED contact blocks, including one under a cancelled case; a terminal
parent is not an exemption. Admin must resolve or transfer pending obligations;
merely completing an intervention is insufficient.

After warning dismissal and explicit case/contact cancellation, deactivation or
role change returns 200, old JWT gets 401, and original assignee/reviewer links
remain readable to authorized users. Active-advisor selection uses the directory;
inactive/demoted historical names are still valid historical references. System
self-deactivation and last-active-System-Admin demotion safeguards remain 409.
No user deletion or bulk automatic reassignment is introduced.

### 5. Concurrency, authorization and audit

| Operation | Real lock boundary | Evidence / consequence |
| --- | --- | --- |
| Warning assignment vs review | Both lock same warning with `populate_existing` | Verified both orders: review can commit before transfer; transfer first makes old Advisor review fail 403. Original reviewer remains historical evidence. |
| Assignment vs advisor deactivation | Assignment locks/refetches target user; account mutation locks same target, then counts obligations | Verified both orders with observed PostgreSQL Lock waits: assignment wins → deactivation 409; deactivation wins → assignment 422. Preserve this synchronization. |
| Two completions of same contact | Both lock same follow-up | Verified one 200, other 409; exactly one successor added. Completion and successor are atomic. |
| Parent transfer vs contact completion | Different row locks (parent vs child); ownership depends on unlocked joined parent | D3 above: old owner can finish and schedule successor after transfer commits. |
| Parent cancellation vs contact completion/successor | Parent-only and child-only locks do not serialize lifecycle decisions | Verified cancellation commits while child is locked; child completion still returns 200 and adds scheduled work under CANCELLED. D2 is reproducible concurrently as well as sequentially. |
| Account revocation vs already authenticated casework mutation | General auth reads actor without row lock; casework does not refresh token/activity; account service does refresh its own actor | **G1 verified security boundary gap:** paused Academic Admin request commits a title change with 200 after deactivation or demotion to read-only System Admin has committed. Subsequent requests get 401. Whether in-flight requests may finish is unspecified; choose and document a commit-time cutoff. |

Event-controlled tests pause immediately after actual `FOR UPDATE` acquisition
and before business authorization. They do not replace service results. Safe
serialization tests additionally observe `pg_stat_activity.wait_event_type =
'Lock'`, then release the winner. Thread waits, database lock timeout (5s),
statement timeout (10s), and future deadlines keep failures bounded. This proves
specific interleavings; it is not exhaustive stress or deadlock proof.

Ordinary mutation service commits include their row changes and review/note or
successor insert. Session close rolls back errors before commit. Most mutation
responses refetch after commit; that refetch is a new READ COMMITTED transaction,
so another writer can change response context after the action committed. B2
read-only repeatable snapshots do not serialize these mutation workflows and
must not be mistaken for a casework fix.

**D4 — confirmed source/schema audit evidence gap:** warning reassignment retains
only current assignee/time, not actor or previous owner. Case/contact transfer,
completion and cancellation have no structured action event or acting-user field;
`created_by` identifies creation, not the later decision maker. Free-text notes
are not guaranteed actor-attributed action events. Reviews do preserve reviewer,
decision, note, time; intervention notes preserve author/time. Successful account
changes have same-transaction `user_administration_audit` with before/after
metadata and actor; rejected safeguards do not create success audit rows. The
casework audit test confirms account-audit and note tables are unchanged by
transfers/completion, while original prediction is preserved. Ordinary access
logs cannot reconstruct who changed ownership and what the previous owner was.
No evidence of production exploitation or historical data loss is asserted.

## Proposed ownership and lifecycle contract (not implemented)

Recommended decisions, requiring product acceptance before behavior changes:

1. **Case owner is canonical for scheduled contacts.** Warning owner remains
   independent triage responsibility; warning transfer must not silently transfer
   all existing cases. One warning can have multiple independently owned cases.
   New scheduled contact must use parent case owner. Reject independent
   delegation unless a separate single-contact-owner authorization model is
   deliberately selected.
2. **Explicit atomic case transfer.** Academic Admin transfers active case to an
   active Advisor, with reason, expected resource version and a preview/count of
   affected SCHEDULED contacts. Change parent and all scheduled children in one
   transaction, audit each before/after assignment and one transfer correlation.
   Keep completed/cancelled contacts, reviews, creators, notes and model history
   unchanged. Advisors cannot self-transfer or silently accept another case.
3. **Manual recovery for pre-existing mismatches.** Read-only diagnostic query
   lists parent/child owner mismatch and terminal-parent pending work. Academic
   Admin uses an explicit audited reconcile/resolve action on selected records.
   No startup job, migration backfill or freshness mechanism rewrites old owners.
4. **Warning decisions are attributed and reversible only explicitly.** Preserve
   append-only reviews. Recommend a reasoned reconsideration action with an
   expected version for confirmed/dismissed warnings. Recommended dismissal gate:
   409 while any linked case is active or any linked contact is SCHEDULED, with
   blocking IDs/counts. Resolve support explicitly first; dismissal never cancels
   support automatically. Reconfirmation permits future case creation; original
   human decisions remain history. Pending first review retains current Advisor
   RBAC. This settles P1 but is a proposed policy, not an existing requirement.
5. **Terminal-state scheduling rules must be explicit and identical on both paths.**
   Minimum defect fix: never create a contact or successor under CANCELLED.
   For COMPLETED, choose between existing explicit monitoring and strict closure.
   Recommended strict-closure option: block complete/cancel while SCHEDULED
   contacts remain, returning counts/IDs; complete/cancel contacts first in
   explicit human actions, then close parent. No contact/successor may then be
   scheduled. Historical terminal parents with pending contacts need an Admin
   resolution action; do not mass-cancel or invent outcomes. If monitoring is
   retained instead, label it clearly and allow it identically in direct and
   successor paths, while never relaxing CANCELLED.
6. **Authorization is checked within the committing lock boundary.** Preserve
   current roles and deactivation checks. Recheck fresh actor activity, role,
   required-password state and presented token version while holding actor lock
   until commit. If revocation wins, reject; if casework wins, it must commit
   before revocation can finish. Do not just recheck once and then release lock.
7. **No silent history edits.** Add attributed action events, leave existing
   records intact, keep RESTRICT FKs and required reason/outcome metadata. Notes
   on terminal records may remain append-only. Repeated terminal writes remain
   409; deduplication and automatic intervention/warning closure stay outside scope.

## RBAC matrix

All cells require active account, current JWT and completed first-use password
change. Reads are institution-wide today; row visibility restrictions are not
proposed as part of this narrow correction. Parent-dependent conditions below
must be enforced inside the locking transaction, not only in frontend helpers.

| Action | System Admin | Academic Admin | Academic Advisor | Proposed change |
| --- | --- | --- | --- | --- |
| Read warning/case/contact history | Yes | Yes | Yes | None. |
| Assign/unassign warning | No | Yes | No | Retain independent warning ownership; add action audit/version. |
| First warning review | No | No | Assigned warning owner | Retain. |
| Reconsider reviewed warning | No | No | Currently API permits assigned owner, UI hides | Explicit action and lifecycle blocker policy required. |
| Create intervention | No | Yes, from confirmed warning | Own confirmed warning, self assigned | Retain. |
| Edit/transition/complete/cancel case; append note | No | Yes | Case owner | Retain role gates; parent-terminal/pending-contact policy as selected. |
| Transfer active case | No | Yes | No | Atomic scheduled-contact transfer, explicit reason/version. |
| Create contact | No | Yes | Case owner, self assigned | Require canonical parent owner and shared lifecycle gate. |
| Edit/complete/cancel scheduled contact | No | Yes | BOTH parent and child owner today | Retain dual gate with aligned ownership and parent lock; terminal legacy recovery by Admin only under strict option. |
| Reassign scheduled contact/reconcile mismatch | No | Yes | No | Explicit recovery, require parent-owner alignment, audit. |
| Edit terminal history/erase records | No supported endpoint | No supported endpoint | No supported endpoint | Continue prohibition; terminal notes remain append-only. |
| Manage account, role, activation/deactivation/reset | Yes with existing safeguards | No | No | Preserve all active-assignment, last-admin, self-deactivation and token protections. |

## Narrow implementation and migration plan

This is a proposal only; **no production file or migration is added in this
audit**. Implement after the lifecycle/delegation/reconsideration/cutoff choices
above are accepted, in separately reviewable changes:

1. Consolidate a casework mutation guard and direct/successor scheduling check;
   lock/reload parent as well as child before ownership/lifecycle checks. Keep
   same-row terminal transition checks and completion/successor atomicity.
2. Add explicit transfer/recovery DTOs and audited endpoints. Adjust existing
   generic assignment PATCH semantics to reject mismatches or invoke the same
   transfer operation; avoid maintaining two independent rules. Preserve all
   existing role denials and validate every active target under a user lock.
3. Settle and enforce dismissal/parent-closure gates in both endpoints and UI.
   Refresh dependent records on 409, show blocking obligations, and expose only
   supported reconsideration/recovery actions. Keep current B2 freshness/risk
   selection independent from human support lifecycle.
4. Use one documented lock order across administration and casework. A narrowly
   scoped first implementation can join existing administration advisory lock
   `610110009` for affected account-sensitive mutations, then refreshed actor and
   sorted target users, warning, intervention, sorted follow-up IDs. Preserve
   the administration mutex/last-admin invariant. Parent identity may be read
   first solely to locate locks, but authorize only after locked refetch. Using
   the same mutex avoids an incompatible actor/target order between old and new
   paths; it serializes more writes, so measure contention. A later finer-grain
   scheme must prove a common ordering before removing that serialization.
5. Preserve commit/rollback atomicity: domain changes and action events in one
   transaction; no post-commit cascade. Account deactivation keeps locked target
   and existing counts. Handle deadlock/lock-timeout as explicit retriable
   conflicts; never retry only part of a transfer or successor insertion.

Proposed additive revision after `20261013_0011` (revision ID assigned only when
implemented): add `casework_action_audit` with immutable event UUID, actor FK,
warning/intervention/follow-up FKs as appropriate, constrained action, timestamp,
reason, safe before/after metadata, and transfer/request correlation ID; index
entity/time and actor/time. Keep existing user-administration audit separate.
If optimistic stale-form detection is selected, add nonnegative resource
revision counters with default zero to warning/intervention/contact, increment
under locks, and return expected-version conflicts. Zero denotes adoption of
version checking, not reconstructed historical revisions.

Do not fabricate past action actors, infer old assignments from `created_by`,
backfill model inputs, move warning foreign keys, alter terminal history or add
automatic data cleanup. Cross-row ownership cannot be enforced by a simple
same-row CHECK constraint; service locks/validation and explicit transfer are
needed. Migration tests must upgrade/downgrade populated histories without
changes to existing probabilities, snapshots, reviewer decisions or ownership.

## Required regression and concurrency coverage

Existing audit tests intentionally assert the current undesirable results so
confirmed defects are reproducible. They are **characterization tests**, not
future acceptance criteria; replace their assertions with the accepted contract
when implementing the correction. Do not leave a passing characterization test
as evidence that a defect has been fixed.

Required implementation acceptance cases:

- Transfer parent + multiple scheduled/due/overdue children atomically; terminal
  children/history unchanged; failure rolls back all assignments and events;
  old advisor denied/new owner permitted; duplicate transfer gives documented
  version/no-op behavior. Independently delegated assignment follows whichever
  single authoritative model is accepted, or is rejected.
- First review/reconsideration, confirmed-warning dismissal with active cases
  and terminal cases with pending contacts; error details and preserved review
  history; no automatic closure; same RBAC on global/dashboard/dossier actions.
- Complete/cancel parent with pending children, and both direct/successor
  creation under PLANNED/IN_PROGRESS/ACTION_REQUIRED/COMPLETED/CANCELLED, according
  to accepted monitoring rule. Required outcomes/reasons; no terminal rewrites;
  contact outcome alone never completes parent.
- Each advisor blocker independently for deactivation and demotion, including
  orphan/mismatched scheduled children and completed-parent contacts; historical
  accounts remain referenced/readable; invalid target, expired/revoked JWT,
  required-password and unauthorized roles cannot mutate. Last active admin and
  self-deactivation protections retain concurrency and error contracts.
- PostgreSQL controlled interleavings in both orders: warning assignment vs
  review, dismissal vs case creation, case transfer vs child edit/complete/cancel,
  closure vs direct scheduling/successor, child transfer vs completion, double
  completion/cancellation, and account deactivation/demotion/password reset vs
  assignment and already-authenticated review/case/contact mutation. Explicitly
  inspect locks and test consistent snapshots, not sleep-only races.
- Same-transaction audit before/after/actor/reason and rollback absence; no fake
  success events on rejected writes; never record tokens/passwords; safe read
  access; explicit retry/idempotency policy for response loss after commit.
- Populated additive migration/rollback and historical fixture equality; B2
  dashboard/registry/dossier current-risk selection and support visibility stay
  intact, all three model checksums unchanged. Browser action-gate/error/recovery
  checks after implementation; no frontend-only integrity enforcement.

## Verification results and limits

Native PostgreSQL **18.3**, READ COMMITTED, was available using the existing
dedicated test cluster at `.venv/b1-pg`, loopback port **55449**, role `b1_test`.
The explicit private port was supplied on startup after an initial default-port
launch failed to bind; the normal development server/database was not altered.
`SHOW data_directory` identified the workspace test cluster. Only fresh
`casework_c1_audit_<uuid>` databases were modified or dropped.

Actual commands from `backend/` (PowerShell environment assignment shown):

```powershell
$env:C1_CASEWORK_TEST_DATABASE_URL = 'postgresql+psycopg://b1_test@127.0.0.1:55449/postgres'
..\.venv\Scripts\python.exe -m pytest -q tests/api/test_casework_integrity_audit_postgres.py
..\.venv\Scripts\python.exe -m ruff check tests/api/test_casework_integrity_audit_postgres.py
..\.venv\Scripts\python.exe -m alembic heads
..\.venv\Scripts\python.exe -m app.ml.deployment verify
..\.venv\Scripts\python.exe -m app.ml.outcomes.deployment verify
```

Final results on 14 October 2026:

- **24 passed, zero skipped, 29.54 seconds**: 15 sequential endpoint/safeguard/
  audit cases and nine controlled PostgreSQL concurrency cases. The initial
  harness had eight timing failures because synchronous FastAPI handlers run on
  worker threads rather than the calling executor thread; that test-only gate
  was corrected. The intermediate complete run passed 23 cases before adding
  the extra concurrent cancellation case. No application fix was made to obtain
  the final passing characterization results.
- Ruff check passed. `git diff --check` passed. The only added files are this
  report and the audit test module. The production `backend/app`, migrations,
  `frontend` and original B2 report have no diff from the specified base.
- `alembic heads`: unchanged single head `20261013_0011`; no migration added.
  All three original deployment artifact verifiers passed. Legacy artifact
  SHA-256 remains
  `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8`;
  enrollment remains
  `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602`;
  first semester remains
  `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81`.
- Database cleanup check against `pg_database` for
  `datname LIKE 'casework_c1_audit_%'` returned **zero rows**. Failed harness
  cases were also cleaned by fixture finalizers. No historical institutional
  data was used or rewritten; fixture history preservation and identity checks
  are evidence about the tested endpoints, not a scan of a production dataset.
- No other client connections remained on the dedicated native cluster. The
  test server started for this audit was stopped with `pg_ctl -D .venv/b1-pg -w
  stop`; shutdown completed successfully. Existing test data outside the new
  audit databases was left intact.

Frontend findings are source inspection, not a new browser run. The full backend
suite/frontend build were not rerun for these audit-only additions; the focused
tests execute all audited mutation endpoints and the relevant read profile.
No exhaustive concurrency stress, complete deadlock proof, production database
audit, or policy acceptance is claimed. Required future tests above include
unverified interleavings such as dismissal vs case creation and competing parent
closure/scheduling in both orders. **No Docker result is claimed; the B2 gap
remains open.** Local `main` and cached `origin/main` retain their B2-reported
SHAs. No PR or merge is created.
