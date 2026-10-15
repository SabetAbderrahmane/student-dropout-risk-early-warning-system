# B2 and C1 final-source container verification — 2026-10-15

The outstanding B2 final-source Docker verification gap is closed for the
combined B2/C1 application at implementation commit
`9cd8abd63131d5a6d63931045a8796c45475c6ab`. This conclusion comes from the
fresh container workflow below, independently of the earlier C1 smoke checks.
It does not retroactively verify the standalone B2 commit
`6727cac3f1aa619e02d384e21a6fe38a44005032` in containers. The earlier dated B2
failure remains an accurate historical record.

The implementation commit was pushed unchanged to
[`codex/phase-c1-casework-integrity`](https://github.com/SabetAbderrahmane/student-dropout-risk-early-warning-system/tree/codex/phase-c1-casework-integrity).
This follow-up changes documentation/evidence only, in a separate normal commit.
No amendment, history rewrite, PR, merge, or model training was performed.

## Runtime and source provenance

Docker client and server both reported **29.5.3**, using the existing
`desktop-linux` context. The verification started October 14 and resumed October
15 against the same healthy isolated stack. Application source stayed clean at
the implementation SHA throughout the build and workflows.

The new Compose project was `b2-c1-final-6601ccc2`, configured in ignored local
`.venv/b2-c1-final-compose.yaml`. Both application images were rebuilt from this
source. Backend used its production runtime target; frontend used the production
build with API URL `http://localhost:8024/api/v1`. Only loopback ports 8024 and
3024 were published. Neither application container had bind mounts. PostgreSQL
used a separate database and tmpfs data, with no published database port or
persistent volume. Generated credentials stayed in ignored local settings.

| Component | Image tag | Exact running image ID |
| --- | --- | --- |
| Backend | `zak-b2-c1-final-backend:9cd8abd63131` | `sha256:458d46dd7e4da7ccf095ab765fb1fceb73b7f5a53db711a9fd4aca81304c611e` |
| Frontend | `zak-b2-c1-final-frontend:9cd8abd63131` | `sha256:34fff4669fb9aabef907414716e2d1c36a9711a416d0a2d7e911ca7499d3c256` |
| PostgreSQL | `postgres:16-alpine` | `sha256:4e6e670bb069649261c9c18031f0aded7bb249a5b6664ddec29c013a89310d50` |

Both application image revision labels equal the full implementation SHA.
Additionally, all **136 tracked backend runtime files** matched that commit's
Git blobs after normalizing text line endings. The running database reported
**PostgreSQL 16.13** and Alembic **`20261014_0012 (head)`**, confirmed both by
`alembic current` inside the backend and a read-only database query. All three
services became healthy.

Model artifact verification passed during build and inside the running backend:

| Model | Verified SHA-256 |
| --- | --- |
| Legacy binary | `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8` |
| Enrollment multiclass | `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602` |
| First-semester multiclass | `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81` |

## B2 workflow results

The ignored stdlib HTTP harness `.venv/b2-c1-final-workflow.py` used real
container APIs, PostgreSQL, saved prediction snapshots and model inference.
There were no mocked mutation or inference responses. Fixture values came from
the repository's published anonymized inference fixture. Accounts were created
through supported APIs, including mandatory password changes. Model validation
and activation used System Admin endpoints; validation did not save prediction
history for the probe student.

The HTTP harness completed **126 named assertions across 15 checkpoints**,
plus browser and read-only audit checks. This is a targeted integration workflow
count, not a claim that 126 separate automated test cases or the entire suite
ran in containers. The machine-readable
[evidence](b2-c1-final-container-evidence.json) records all assertion names,
checkpoint aggregates, seven immutable prediction records, source/image
provenance and the attributed transfer audit events.

| Action | Operational result |
| --- | --- |
| Real enrollment inference with original confirmed warning and support | `CURRENT`, MEDIUM, `0.2497711730787302` (UI 25%) |
| Admission grade correction 125.5 → 124.25 | `INPUTS_CHANGED`; no current probability |
| Real enrollment reassessment | `CURRENT`, MEDIUM, `0.2606749370181211` (UI 26.1%) |
| Revert inputs to match the older enrollment attempt | `INPUTS_CHANGED`; older attempt is not resurrected |
| Restore inputs matching the newest enrollment attempt | Same newest enrollment prediction becomes current without new inference |
| Record semester-one inputs | `STAGE_REASSESSMENT_REQUIRED`; no enrollment probability presented as current semester risk |
| Real semester inference, followed by newer enrollment inference | Semester remains `CURRENT`, LOW, `0.1819989821172857` (UI 18.2%); newer enrollment is `NOT_SELECTED` |
| Separate student's real same-stage legacy binary fallback | `CURRENT`, `0.3447925421468906`; no invented multiclass probabilities/outcome |
| Change its semester average 12 → 11 | `INPUTS_CHANGED`, changed feature `first_semester_average_grade`; no false model-supersession blocker |
| Restore semester average | Same binary prediction becomes current without new inference |
| Run preferred semester multiclass model | Preferred prediction `CURRENT`, LOW, `0.18011547285576907`; eligible binary becomes historical `NOT_SELECTED` |
| Remove a required semester input | `INPUTS_INCOMPLETE`; no regression to enrollment risk |
| Restore required input | Same preferred semester prediction becomes current without new inference |
| Transfer contacts, resolve obligations, close case and reconsider warning | Main student's same semester prediction remains current at 18.2% |

At every checkpoint, registry and dossier freshness/selection agreed. Dashboard
current counts equaled both the sum of risk buckets and the registry's selected
prediction count; current + reassessment + no-history equaled total students.
Attention probabilities, where present, used operational values. Selected
prediction detail agreed on probability, `CURRENT` and operational selection.
All seven saved predictions retained their original identity, probability,
class probabilities, stage/target, model version, input snapshot, explanation,
timestamp and creator across subsequent input and casework mutations.

The original warning review, intervention and stored contact history remained
unchanged throughout B2 input/stage changes, and ongoing support stayed visible
even after the operational prediction became LOW. The run crossed midnight:
derived due/overdue projections were allowed to advance with the calendar while
stored history was compared unchanged. A later explicit advisor reschedule,
after those B2 preservation checks, ensured the C1 transfer fixture contained
future, due-today and overdue obligations on October 15.

Advisor and System Admin prediction execution returned **HTTP 403** for
enrollment, first-semester and omitted-stage legacy requests. Both roles could
read current semester risk and existing support. At the final checkpoint there
were three synthetic students: two current LOW assessments, no reassessment
required, and one validation probe without prediction history.

## C1 ownership, audit and explicit closure

The academic admin transferred case
`d21947ce-bb25-46a4-b48a-c6430f91c1fc` using the rebuilt frontend's directory
selection, required reason and revision. The case and all three stored
`SCHEDULED` contacts (effective SCHEDULED, DUE and OVERDUE) moved atomically to
the selected active advisor. The previously completed contact retained its
owner, creator, outcome, evidence and revision. Warning triage ownership remained
independent.

Read-only inspection found exactly four `TRANSFER_INTERVENTION` events, one
parent and three pending contacts, with correlation ID
`e517678b-ae2f-441a-ac13-cb81cd56a6f9`, academic actor
`1d0847e7-8055-44ce-a52d-95cf71743de9`, and reason
`Final-source container verification transfer`. All changed owner from
`cbb511b9-db28-4db9-b2a1-3686f2861df4` to
`3a7afe4c-5561-4f2a-9f0b-d995fb3921cc`; every affected revision increased by
one (parent 7 → 8). The terminal contact had no transfer event, and rejected
attempts added no successful transfer event.

Actual API checks also established:

- Stale transfer: 409 `STALE_RESOURCE_REVISION`.
- Old owner's contact completion: 403 `FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR`.
- Advisor transfer: 403 `INSUFFICIENT_PERMISSIONS`.
- Generic assignment PATCH: 409 `EXPLICIT_TRANSFER_REQUIRED`.
- Independent delegated child scheduling: 409 `INDEPENDENT_FOLLOW_UP_DELEGATION`.
- Warning dismissal while support remained active: 409 `WARNING_HAS_ACTIVE_SUPPORT`.
- Parent closure with unresolved scheduled contacts: 409 `INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS`.
- New owner completing a contact with an atomic successor: succeeded, successor
  assigned to the canonical case owner.
- Resolving all remaining contacts, including `INTERVENTION_COMPLETED` contact
  outcomes: parent still PLANNED; no implicit closure.

The new owner then explicitly completed the parent through the rebuilt frontend,
recording `SUPPORT_COMPLETED` and completion notes after all five contacts were
resolved. Scheduling under the completed case returned 409
`INVALID_FOLLOW_UP_TRANSITION`. An append-only terminal note succeeded. A browser
reload showed the completed case, original terminal ownership, new note, and
absence of scheduling, transfer, edit or completion actions; Add Note remained
available. Explicit warning reconsideration then succeeded and retained both
attributed review decisions, including the original note.

The final `/casework/integrity` response was an empty list. Casework mutations
and closure did not alter B2 operational selection or saved prediction facts.

## Browser evidence and execution notes

Playwright drove the production frontend against the rebuilt API. Dossier
checks covered changed inputs/unavailable current risk, enrollment reassessment,
semester reassessment required, current semester risk, historical `NOT_SELECTED`
and changed-input labels, and accurate binary fallback blockers. The registry
showed the original confirmed warning and ongoing intervention alongside the
new LOW semester risk. A 390px viewport check found no root horizontal overflow.
Transfer and explicit parent closure were real browser form submissions.

Local ignored screenshots in `output/playwright/b2-c1-final-*.png` include
`inputs-changed`, `reassessed`, `stage-required`, `semester-current`, `history`,
`history-mobile`, `binary-blocker`, `registry`, `transfer` and `closed`.
The semester-current and settled terminal screenshots were visually inspected.
Observed browser console output had zero errors and existing CSS preload
warnings; those warnings are not claimed fixed. Local screenshots and harnesses
are not committed and are not required to interpret the committed JSON evidence.

Routine harness corrections were confined to ignored files: an initial Compose
placeholder incorrectly replaced the JWT environment key; an initial UI check
expected `25.0%` instead of the observed `25%`; and a closure script initially
lacked the CLI's async-function wrapper. Corrected runs passed, with the terminal
view checked again after its authoritative reload. None required an application
source change.

Representative commands used (from the repository root):

```powershell
docker version
docker compose -f .venv/b2-c1-final-compose.yaml -p b2-c1-final-6601ccc2 build backend frontend
docker compose -f .venv/b2-c1-final-compose.yaml -p b2-c1-final-6601ccc2 up -d
docker compose -f .venv/b2-c1-final-compose.yaml -p b2-c1-final-6601ccc2 exec -T backend alembic current
# Run each HTTP phase once, interleaved with the corresponding browser checks:
# setup, edit, reassess, progress, semester, fallback, fallback_restore, contacts, finish
.venv/Scripts/python.exe .venv/b2-c1-final-workflow.py finish
```

## Scoped cleanup and remaining limits

Before removal, project labels and Compose paths identified the old stopped
`b2-verification` resources as the earlier disposable B2 stack. Its database also
used tmpfs and had no persistent volume. Cleanup ran successfully:

```powershell
docker compose -f .venv/b2-c1-final-compose.yaml -p b2-c1-final-6601ccc2 down --volumes
docker compose -f .venv/b2-compose.yaml -p b2-verification down --volumes
```

Removed new project containers `dd034812c63f`, `b2dc4d0714e4`, `b7740488ffca`
and network `81ee9cfac72a`; removed old disposable containers `9c019e50d3c7`,
`4965a69efc1d`, `238dfc360f85` and network `2002fef05b6e`. Final Docker queries
returned zero containers, networks and volumes for both project labels.
Ports 8024, 3024, 8001 and 3001 had no listeners. The dedicated browser session
was closed. Image tags/build cache and ignored local evidence were retained.
No daemon restart, image prune, shared resource deletion, or institutional/native
database change was performed.

This closes the targeted final-source container workflow gap. It is not a fresh
full backend-suite run inside containers, exhaustive concurrency/load testing,
production-data audit, browser coverage of every C1 cancellation/recovery path,
or a new model-training/accuracy evaluation. The prior native 369-test full run
and subsequent 81-test C1 module run remain separately dated evidence. Their
concurrency/migration/rollback coverage was not relabeled as container coverage.
Only documentation/evidence changes follow the verified implementation SHA.
