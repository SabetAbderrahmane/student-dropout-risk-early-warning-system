# Thesis demonstration RC1: startup, presentation and shutdown

Target branch: `release/thesis-demo-rc1`. This procedure runs the approved local
academic application with synthetic records and all three approved models. It
uses the existing E1 tooling; no application feature or configuration contract
has been added. See the [release inventory](../release/thesis-demo-rc1.json) and
[final verification](phase-e3-release-candidate.md).

## Prerequisites

- A Git checkout of `release/thesis-demo-rc1`, with Git LFS unnecessary for these
  small tracked outcome artifacts. Authenticate repository access using the
  institution/operator's authorized account; do not change repository visibility.
- Docker Engine with Linux containers (Docker Desktop Linux engine on the tested
  Windows host). The operator must be allowed to build/run containers. Ensure
  adequate disk/RAM for PostgreSQL, the two application images and test runner.
  Package/container downloads require network access during preparation.
- Python **3.11.9** for the standard-library orchestration/provisioning scripts.
  Native backend packages and a native PostgreSQL installation are not required
  for this Docker procedure. Full backend verification runs inside Python 3.11.9
  containers.
- Node **22** and npm for the browser suite (the container frontend uses Node 22).
  Node 24.14.0 was also exercised by the native frontend checks. Use the existing
  lockfiles with `npm ci`; do not run uncontrolled dependency updates.
- The **authorized retained legacy model file**, supplied privately by its
  custodian. Its approved SHA-256 is listed in the inventory. It is not in Git.
  Obtain it before arriving at the demonstration. The two outcome model files
  are already tracked. Do not download an arbitrary pickle or retrain a substitute.
- Chromium for the pinned Playwright 1.64.1 package. The installation command
  below provisions the approved browser revision. On Linux, install Playwright's
  browser OS dependencies as well (`npx playwright install --with-deps chromium`,
  using the host's approved package-installation permissions).

Do not populate `.env`, use institutional student data, or change shared Docker
settings. No `.env` file, static password, custom database service or manually
selected host port is needed. The helper generates per-invocation credentials,
an owned tmpfs database/network and random ports bound only to `127.0.0.1`.
The PostgreSQL port is not published. Frontend API URL and CORS are configured
automatically for those actual ports at build/start time.

## Clean checkout and verified startup (Windows PowerShell)

```powershell
git clone --branch release/thesis-demo-rc1 --single-branch https://github.com/SabetAbderrahmane/student-dropout-risk-early-warning-system.git thesis-demo-rc1
Set-Location thesis-demo-rc1
python --version
docker version
node --version

# Replace only this file argument with the privately supplied approved artifact.
python scripts/ci/provision_models.py --source C:\private\approved-legacy-model.joblib
if ($LASTEXITCODE -ne 0) { throw 'Approved model provisioning failed' }
python scripts/ci/provision_models.py --verify-only
if ($LASTEXITCODE -ne 0) { throw 'Model integrity failed' }
python scripts/acceptance/stack.py up
if ($LASTEXITCODE -ne 0) { throw 'Isolated stack startup failed' }

Set-Location acceptance
npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Acceptance dependencies failed' }
npx.cmd playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Browser installation failed' }
npm.cmd test
if ($LASTEXITCODE -ne 0) { throw 'Acceptance failed: preserve logs and inspect the failing scenario' }
Set-Location ..
```

On Bash/Linux, use `npm`/`npx` instead of `npm.cmd`/`npx.cmd`, the appropriate
private file path and `set -e` so any failed step stops the procedure. This is a
networked preparation followed by a loopback demonstration; the application does
not need an external inference service or a live dataset download.

`up` automatically applies all migrations to the new `e1_demo` database and
bootstraps `e1_system`. The acceptance suite performs the required first-password
replacement, creates the academic/advisor accounts, validates and activates both
outcome models, imports synthetic students and executes the complete workflow.
It deliberately preserves its E1 account/project naming for compatibility.
All nine scenarios must pass; do not present an incomplete run as verified.

The helper prints the frontend and API locations, not passwords. Its ignored
`.venv/e1/session.json` contains the private account credentials and project/URL
state. After the suite, use these final-password entries locally:

| Role | Username | Private value to read locally |
| --- | --- | --- |
| System Administrator | `e1_system` | `users.system.password` |
| Academic Administrator | `e1_academic` | `users.academic.password` |
| Academic Advisor | `e1_advisor` | `users.advisor.password` |

Keep this file on the authorized host; do not commit it, project it, include it in
screenshots or send it with the thesis. Use a local editor to retrieve each value
and enter it in the actual sign-in form. The other-advisor account is deliberately
deactivated by acceptance; disposable test accounts are not presentation accounts.
Use separate browser profiles or sign out before changing roles. Session expiry
is normally 30 minutes; sign in again when the UI returns to login.

## What to demonstrate

After the automated run, the application contains three synthetic students and
an intact completed case for **E1-001 / E1 Synthetic Amira**. Present the actual
application, not a mocked page:

1. As System Admin, inspect Users and Risk Predictions: three verified model
   entries, stage validations/activation, and the retained binary model.
2. As Academic Admin, inspect Data Import's committed staged batch and student
   registry. Open E1-001's dossier, its recorded enrollment Medium-risk result and
   non-causal explanation factors. Distinguish historical results from current
   first-semester risk.
3. Show the assigned, confirmed warning, intervention ownership, attributed
   advisor note and completed progress follow-up. Its temporary ownership
   transfers and final advisor are persisted and tested.
4. Show the semester edit, old assessment marked `INPUTS_CHANGED`, new Low-risk
   reassessment and case history. Earlier predictions and completed support
   records remain; probabilities from different models are not averaged.
5. Switch to the Advisor and review the same completed case. Demonstrate the
   normal role restrictions without using a privileged token or bypassing UI.

The CSV contract includes semester fields. Enrollment may therefore be displayed
as historical with “Reassessment required” until a current semester assessment is
selected. This is the approved freshness contract, not a failed prediction.
Explain the models' benchmark scope and recorded non-causal factors; no claim of
validation on the university's own population is made by this release.

### Re-enact the workflow from blank data

First run `python scripts/acceptance/stack.py reset-demo` from the repository
root. It verifies ownership and replaces only this invocation's `e1_demo`
database. It does not affect any institutional/shared database or the separately
used regression root. All accounts and model activations are fresh afterward;
the system administrator again uses `users.system.initial` and must change it.

Create an Academic Admin and Advisor through Users, giving each a private
temporary password and completing their required password changes. As Academic
Admin, stage [the validation CSV](../release/demo-students-validation.csv).
Physical CSV row 3 has the sole intentional error: change `age_at_enrollment`
from `not-a-number` to **24**, save the correction and commit. Alternatively,
[the valid CSV](../release/demo-students.csv) commits two valid synthetic rows.
Do not import either into an already populated E1-001/E1-002 registry.

As System Admin, validate and activate the Enrollment and First semester models
using E1-001. As Academic Admin, run Enrollment prediction, inspect the Medium
warning and assign the advisor. As Advisor, confirm the warning; create an
Academic Advising intervention, start it, add a note and schedule an in-person
follow-up. Complete the follow-up with `PROGRESS_OBSERVED` and the intervention
with `SUPPORT_COMPLETED`. As Academic Admin, run an initial semester assessment,
then edit Semester 1 to credited **0**, enrolled **6**, evaluations **7**, approved
**6**, average grade **15**, without evaluations **0**. Observe stale history,
run reassessment, then inspect the new current result and preserved case history.
The unchanged executable suite is the precise reference for all form labels and
assertions: [acceptance.spec.ts](../acceptance/tests/acceptance.spec.ts).

For a deterministic automated repeat after reset, simply run `npm.cmd test` from
`acceptance`. Do not run the serial suite twice on populated data without reset.

## Release verification and shutdown

To run the backend gate on this invocation, from repository root:

```powershell
python scripts/acceptance/stack.py regress
if ($LASTEXITCODE -ne 0) { throw 'Backend release gate failed' }
```

It provisions the existing test dependencies in a disposable runner, uses all
seven PostgreSQL settings and `RUN_MODEL_INTEGRATION=1`, runs the migration checks
and refuses missing mandatory suites or any skips. The runner is retained for
evidence; execute regression once per new invocation. See the inventory/report
for frontend, release-control and independent Docker HTTP-smoke gate commands.

Capture only synthetic, credential-free evidence before shutdown. Then:

```powershell
python scripts/acceptance/stack.py down
if ($LASTEXITCODE -ne 0) { throw 'Ownership-checked cleanup needs inspection' }
```

This removes only owned containers, the empty invocation network and owned image
references, archives its private state and stops the loopback listeners. There is
no Docker prune, volume deletion or shared-container mutation. The database uses
tmpfs: **shutdown discards the synthetic records**. Re-run `up` and the suite for
a later demonstration. Do not describe this ephemeral verification setup as a
backup/recovery solution or an internet deployment configuration.

If preparation fails, preserve ignored logs/state and identify the failed gate.
Do not lower audit thresholds, skip models, use `development` as the backend
deployment target, prune shared Docker data or continue with a partial seed.
Host/package download or permission issues are environment prerequisites; hosted
GitHub plan limitations are separate from local application functionality.
