# E3 thesis demonstration release candidate RC1

Date: 2026-10-23, Africa/Casablanca. Target:
`release/thesis-demo-rc1`. Base and immutable application source:
`e80114ddbad85ec48d53a42a80a0e6c7b354e308` (E1.1).

**Demonstration readiness: GO** for the tested local, synthetic-data thesis
demonstration with trusted operators and loopback-only services. No unresolved
local functional blocker was observed. This is not approval for internet
exposure or real institutional records. Hosted plan restrictions are not local
application failures.

Deliverables: [startup/presentation/shutdown runbook](thesis-demo-rc1-runbook.md),
[exact release inventory](../release/thesis-demo-rc1.json),
[valid synthetic CSV](../release/demo-students.csv) and
[validation/correction CSV](../release/demo-students-validation.csv).
The Git commit containing these documents identifies the release packaging;
`git rev-parse HEAD` identifies that exact checkout. The inventory separately
pins the immutable tested application commit and source-tree IDs. E3 makes only
documentation, evidence line-ending configuration, inventory and synthetic presentation-fixture additions; application,
test, workflow, migration and scientific source trees remain identical to E1.1.

## Consolidation and source coverage

Ancestor checks cover the original backend/read-model work, integrated frontend,
dark mode, approved artifact delivery/account management, B1, B2, C1, D1 audit,
D1.1, D1.2, E1 and E1.1. Their exact full commits and subjects are in the inventory.
No force merge, history rewrite, model retraining or scientific result change
was performed. All three model byte checksums, registry/manifests and scientific
dependency pins remain unchanged.

The separate `codex/frontend-usability-onboarding` branch (`2d10cda`) remains
excluded, as required. Its optional guide/icon additions are not an ancestor of
this application. The complete approved academic workflow passes without them.
This is explicitly not a claim that every historical experimental branch is merged.

Historical D1, D1.1, D1.2, E1 and E1.1 reports are preserved. The unchanged browser
suite reuses its historical output path, so fresh results were copied to E3's
ignored evidence directory and historical tracked E1 images restored. New
credential-free synthetic screenshots are retained under `docs/evidence/rc1`.

## Clean installation and configuration inspection

A fresh managed Git checkout was created directly at E1.1. Its initial tracked
status was clean, with no frontend dependencies, root/backend `.env`, generated
session state or retained private legacy artifact. The two approved outcome
artifacts were present through Git. Verification correctly failed without the
private legacy bytes; supplying the authorized retained file through the existing
checksum-enforcing provisioner verified all three artifacts. No other private
configuration or prior database was copied into the checkout.

The existing standard-library helper built the production Docker images, generated
new credentials, migrated/bootstrap-created the new database and selected random
loopback-only ports. PostgreSQL was tmpfs and not exposed on the host. The frontend
compiled its actual API URL and the backend CORS matched it. Actual browser login,
password change, model validation/activation and synthetic business writes all
used the real application.

One release-documentation discrepancy was corrected: the README previously led
operators to development Compose and offline model reproduction. The unmodified
development Compose publishes `5432`, `8000` and `3000` on all interfaces and uses
development settings. RC1 now prominently directs operators to the isolated
runbook and privately provisioned existing artifact. The development configuration
is preserved for its original purpose; it is not the thesis-release procedure.

A second release discrepancy was reproduced in the clean Windows checkout:
`core.autocrlf` converted two historical E1.1 audit JSON files to CRLF, causing
their raw working-file SHA-256 values to differ from the recorded LF evidence.
Their Git blobs still matched the original recorded hashes exactly; the four
E1.1 PNGs and all 39 E1 PNGs were unchanged. Narrow `.gitattributes` rules now
force LF for evidence JSON and release JSON/CSV, preserving those original bytes
on Windows and Linux. Historical report values and Git blobs were not rewritten.
The Git checkout filter is verified with Windows CRLF settings enabled.
Inventory hashes for pre-existing textual dependency/scientific files use the
canonical Git blob bytes; observed working-copy hashes are distinguished. Model
binary hashes always describe the actual approved binary bytes.

All prerequisites are explicit: repository access, Python 3.11.9, Docker Linux
engine/build permission/resources, Node/npm, pinned browser/system dependencies,
network access for preparation and authorized model custody. No manually edited
environment file or institutional database is needed. The inventory lists runtime
variables, whether secret, and how the helper supplies each, plus the seven
disposable PostgreSQL regression settings.

The CSV files contain only synthetic identities and the existing public inference
fixture's numeric features. Both were checked with the actual backend parser.
The valid file has two valid rows; the correction file has exactly one error at
physical row 3, `age_at_enrollment`, corrected to 24 in the demonstrated workflow.
An initial fixture export used `1.0` strings for strict integer fields; exporting
integral numbers as integer strings corrected the release fixture. This was a
packaging diagnostic; no application validation or scientific values were changed.

## Verification evidence

The final results and durations are recorded in the inventory. Required checks:

| Check | Result / evidence |
| --- | --- |
| Fresh-checkout prerequisite/legacy-artifact refusal | PASS; no hidden model fallback |
| Three raw model checksums and production deployment verifiers | PASS; unchanged approved bytes |
| Frontend clean install, full low-threshold security audit, typecheck and production build | PASS; Next.js 16.4.2 and zero reported vulnerabilities |
| Independent D1.2 Docker HTTP smoke gate | PASS; bootstrap, forced password change, unauthenticated denial, readiness, model catalog and frontend headers |
| Full Docker application and actual API/CORS integration | PASS; production frontend/backend and isolated PostgreSQL |
| Existing E1 Playwright suite | **9 passed**, 93.111 seconds, zero skipped/unexpected/flaky tests; one worker, zero retries |
| D1.2 release-control regressions | **24 passed**, 3.42 seconds |
| Targeted Python lint | PASS; existing Ruff F,E9 targets |
| Backend mandatory release gate | **544 passed, zero skips**, 784.08 seconds, Python 3.11.9; exit 0; [summary](evidence/rc1/backend-summary.json) and per-module counts in inventory |
| Alembic | Single `20261014_0012` head; fresh upgrade/current/drift and empty downgrade/re-upgrade/drift checks |
| Presentation CSV parser checks | PASS; two valid rows / sole intentional invalid age |

The backend retained 298 existing pandas/sklearn warnings, matching E1/E1.1's
warning count; none was suppressed or treated as a skip. All executable required
gates completed successfully. No generated fixture databases or public tables
remained in the disposable regression root. Checks explicitly outside the local
scope below were not executed and are not counted as passed.

The nine unchanged UI scenarios cover all three operational roles, required
password changes and account management, approved model activation, CSV staging
and correction/commit, student creation/editing, enrollment explanation/warning,
advisor assignment, intervention and notes, ownership transfers, completed
follow-up/case, semester update/reassessment and preserved history. They also
cover navigation, desktop/tablet themes, empty/loading/offline-retry states,
unauthorized writes, expired sessions and deactivated-account denial. Successful
responses are never mocked. The existing negative/fault-injection boundaries
retain their exact E1 semantics.

Read the [E1 acceptance matrix](phase-e1-acceptance-matrix.md) for detailed cases;
RC1 executes the identical suite. New screenshots show
[enrollment explanations](evidence/rc1/06-enrollment-assessment-explanation.png),
[completed support](evidence/rc1/10-completed-intervention.png),
[history](evidence/rc1/11-durable-case-history.png) and
[dark tablet overview](evidence/rc1/tablet-dark-dashboard.png).

The complete backend gate uses Python 3.11.9, `RUN_MODEL_INTEGRATION=1`, all seven
disposable PostgreSQL variables and mandatory-suite/zero-skip enforcement. Its
`APP_ENV=test` and `ML_MODEL_REQUIRED=false` allow existing startup-negative
fixtures, while model provisioning/verifiers and real integration remain
mandatory. The production image retains required-model mode. Generated regression
databases are checked for cleanup separately from the persisted demonstration.

### Exact gate commands

From `frontend`, the independent gate was `npm ci`,
`npm audit --audit-level=low --json`, `npm run typecheck` and `npm run build`.
From `acceptance`, it was `npm ci`, `npx playwright install chromium` and
`npm test`. Windows invocation used the `.cmd` executables. From repository root:

```powershell
python scripts/acceptance/stack.py regress
python scripts/ci/docker_smoke.py --project e3-rc1-20261023 --evidence .venv/e3/docker-smoke.json
```

The independent HTTP smoke additionally gives every invocation a random ownership
token and cleans only matching resources. Its safe result is retained as
[docker-smoke.json](evidence/rc1/docker-smoke.json); the full audit result is
[npm-audit.json](evidence/rc1/npm-audit.json).

The native QA environment used Python 3.11.9 and Ruff 0.17.1, with dependencies
declared by `backend/requirements-packaging.txt` and
`backend/requirements-dev.txt`. To prepare a separate QA virtual environment,
install those two files in that order from `https://pypi.org/simple`, then
`ruff==0.17.1`, as specified by the existing
[release workflow](../.github/workflows/release.yml). Native QA tooling is
separate from the Docker-only application installation. Run:

```powershell
python -m pytest -q scripts/ci/test_release_controls.py
python -m ruff check backend/app scripts/ci scripts/acceptance --select F,E9
python -m ruff check backend/tests/api/test_d1_authorization_postgres.py backend/tests/auth_context.py --select F,E9
git diff --check
```

## Reproduction limits and handoff

This was a clean source checkout on an authorized host with installed tooling and
Docker/browser download caches; it was not an air-gapped or pristine-OS test.
The startup procedure and local academic workflow are reproducible, not a claim
of bit-identical future container builds: non-scientific backend dependencies
retain approved version ranges, and Docker base tags can move. The inventory
records the exact resolved Python packages, npm lock hash, image identities and
base-image references for this execution. Retain this manifest and source commit;
rerun the gates if dependency resolution or base images differ later. Do not
silently change frozen science to make a new environment pass.

GitHub Actions plan/runner/protection limitations are not failures of local
application functionality. E3 does not purchase a plan, change repository
visibility or bypass enforcement. Hosted enforcement, public TLS/edge/abuse
controls, operational backup/recovery, load/penetration testing and additional
browser engines are separate unverified items. RC1 approves no internet exposure
or institutional-data operation.

Shutdown verification passed for both the full acceptance stack and independent
HTTP-smoke invocation: no owned containers, networks or images remain. The
before/after shared Docker inventory was unchanged (16 containers, 12 networks,
49 image-list entries). No prune was used. The generated private state is
archived locally, and the synthetic tmpfs database is discarded as documented.

Remaining academic handoff requirements:

- Retain the exact release commit/inventory and provide authorized repository
  access to the examiner/operator.
- Assign a custodian for the approved private legacy model and transfer it
  privately with checksum verification; never place it in Git or a public thesis
  attachment.
- Prepare the approved host, browser dependencies and a full successful rehearsal
  before the session; note that tmpfs shutdown discards synthetic records.
- Keep generated credentials private, retrieve final passwords locally, and
  ensure the presenter can switch among the three roles without sharing sessions.
- Use the supplied synthetic CSVs and approved workflow narrative. Label the
  models' benchmark provenance, limitations and non-causal explanation method
  accurately in the thesis; university-population validation remains a separate
  academic requirement if such a claim is intended.
- Choose which credential-free screenshots/history to include in the thesis and
  confirm the university's submission/access requirements with the supervisor.
- Treat later institutional/public deployment as separate work, including its
  governance, secure topology, recovery and hosted release-enforcement decisions.
