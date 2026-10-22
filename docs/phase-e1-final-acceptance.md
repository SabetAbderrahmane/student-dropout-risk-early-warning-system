# E1 final full-stack acceptance

Execution: 2026-10-22; evidence finalized 2026-10-23, Africa/Casablanca. Branch:
`codex/phase-e1-final-acceptance`. Base and freshly fetched remote D1.2 head:
`b8386de921905b6188f71ecf41e1ed8ae7766289`.

**Local university thesis demonstration: CONDITIONAL GO.** The real production
frontend, backend, disposable PostgreSQL and all three approved models complete
the demonstrated academic workflow. Use synthetic records, trusted operators,
loopback access and pre-provisioned artifacts. A newly failing dependency audit
prevents an unconditional release verdict. **Internet deployment: NO-GO.**
No public deployment, PR or merge is part of E1.

## Source and environment

Read before execution: [D1 readiness audit](phase-d1-release-readiness-audit.md),
[D1.1 implementation/verification report](phase-d1-academic-write-authorization.md)
and [D1.2 verification report](phase-d12-release-gates.md).
Ancestor checks confirm integrated frontend `2dfb37b`, dark mode `17a914e`, C1
`9cd8abd`, D1.1 `b45058c` and D1.2 `103a283` are included. The unrelated dirty original checkout
was preserved; the existing managed D1.2 worktree was reused.

Docker Engine 29.5.3 was available. Invocation
`e1-acceptance-24196d32f0` used an ownership-labelled network, tmpfs PostgreSQL 16,
production FastAPI image and production Next.js standalone image. Only random
loopback HTTP ports were published: frontend `65086`, backend `65085`.
PostgreSQL had no host port. Build-time `NEXT_PUBLIC_API_URL` and backend CORS
selected those actual endpoints. Browser tests used those endpoints throughout.
The separate `e1_demo` database contains only generated E1 records; regression
fixtures use `release_gate` and their own disposable databases/schemas.

Credentials and the signing key are randomly generated in ignored
`.venv/e1/session.json` and private environment files, never committed. This is
test tooling, not a production provisioning or persistence configuration. The
database is deliberately ephemeral. Images, container identities, HTTP status
counts, persisted SQL checks, test counts and file checksums are recorded in
[verification evidence](phase-e1-verification-evidence.json).

## Results and limits

| Check | Result |
| --- | --- |
| Complete backend release gate, Python 3.11.9 | **544 passed, zero skips**, 298 warnings, 927.64 seconds |
| Seven required PostgreSQL integration settings and eight mandatory modules | Present and executed; `RUN_MODEL_INTEGRATION=1` |
| Alembic on empty disposable database | Single head `20261014_0012`; upgrade, actual revision, drift check, downgrade to base, re-upgrade and drift check passed |
| Running application schema | Actual `20261014_0012 (head)` |
| All three raw artifact hashes, both deployment verifiers and real inference | Passed in built/running backend; all three model families also invoked through UI |
| D1.2 release-control negative tests | **24 passed**, 5.29 seconds |
| Ruff `F,E9`, backend/application and release/acceptance scripts plus D1.1 targets | Passed |
| Frontend `npm ci`, typecheck and production build | Passed; native Node 24.14.0; actual production container built on Node 22 |
| Real Chromium browser acceptance | **9 passed**, zero skips/failures/flaky tests, 95.829 seconds; exact durations in evidence and [matrix](phase-e1-acceptance-matrix.md) |
| Separate acceptance package `npm ci` and audit | Passed; zero reported vulnerabilities |
| Frontend `npm audit --audit-level=low` | **FAILED**, exit 1: one critical affected package (`next`), three advisory entries |
| Hosted Actions / protected-branch enforcement | Not established by E1; inherited D1.2 hosted startup/plan restrictions remain |
| Public TLS/edge, abuse controls, operational recovery, penetration/load testing | Not executed or approved by this local acceptance phase |

The 298 backend warnings include existing pandas dtype and sklearn probability
warnings; none was silently suppressed. They do not count as skipped tests.
All backend application source, tests, migrations, scientific dependency pins,
parameters, registries and manifests remain byte-for-byte unchanged from D1.2.
No retraining, model reproduction, authentication-contract change or RBAC rewrite
occurred. The separate acceptance package pins Playwright 1.64.1; Chromium is
156.0.8078.4 (Playwright revision 1248).

## Browser acceptance and corrections

The serial executable suite is
[`acceptance/tests/acceptance.spec.ts`](../acceptance/tests/acceptance.spec.ts).
It logs in four independent real browser contexts. All business writes use UI
forms and real backend responses. Authenticated API reads assert persistence;
additional deliberately forbidden API requests assert 403 responses. No
successful response is mocked. Loading coverage delays then continues a real
request; offline coverage aborts one request and then retries against the real
backend. These are explicit fault injections.

The expiry check supplies an already-expired, correctly signed token containing
the synthetic account's existing claims, using only this disposable stack's
private key. The real backend rejects it and the UI returns to sign-in. It does
not forge a successful authorization or wait for wall-clock token expiry.
Deactivating another logged-in synthetic advisor independently verifies session
revocation. Expected network/401/403 failures are distinguished from JavaScript
exceptions. Generic browser resource-failure console messages are excluded;
other console errors and page exceptions must remain empty.

One application defect was verified and corrected: the public homepage still
said predictions, warnings, interventions and dashboards were deferred to later
phases. Its copy now describes the implemented academic workflow. The before
screenshot and final homepage screenshot are retained. This is the only
application source change (`frontend/app/page.tsx`).

Harness development failures are not classified as application defects:

| Attempt | Outcome / correction |
| --- | --- |
| 1, initial three-scenario harness | Role selection timed out; use the accessible combobox role selector. Remaining scenarios unexecuted. |
| 2 | First three scenarios passed. |
| 3, expanded nine-scenario suite | Four passed; warning-review assertion expected 200 instead of the actual contracted 201; four unexecuted. Corrected assertion. |
| 4 | Six passed; asserted detail DTO `stored_status` on a profile DTO exposing `effective_status`; two unexecuted. Corrected assertion. |
| 5 | Six passed; legacy prediction button was sought while the History tab was open; two unexecuted. Return to Predictions first. |
| 6 | All nine passed. |
| 7 | All nine passed with authorized import-screen and portrait tablet/navigation coverage. |
| 8, final | All nine passed with settled-data screenshot waits; 95.829 seconds, zero skips/failures/flaky tests. |

The cleanup ownership negative control initially encountered an absent Docker
image-label key. The helper was corrected to treat absent/null labels as unowned;
the rerun explicitly refused the shared PostgreSQL image before any mutation.
This was a tooling diagnostic, not an application or authorization failure.

Screenshots are full-page PNGs of synthetic records. Desktop uses 1440×1000;
landscape tablet uses 1024×768 and portrait tablet 768×1024. Assertions check
document overflow, real navigation, theme persistence, route headings and settled
loading state; screenshots support manual visual review, not pixel-baseline or
formal accessibility certification. Dashboard offline/loading and registry empty
states are exercised explicitly; this does not claim every possible error state
of every modal was exhaustively tested. Chromium was tested; Firefox, Safari,
phones and assistive-technology testing were not executed.

## Academic demonstration and interpretation

The suite stages a two-row CSV obtained from the actual template contract, using
the repository's public inference regression fixture as synthetic feature data.
One invalid age blocks commit; correcting staged row 3 to age 24 enables commit.
The imported students appear in the registry. A third student is created through
the form and the first student's demographic text is edited.

The system administrator validates and activates both approved outcome models.
The Academic Administrator explicitly runs enrollment inference, sees multiclass
probabilities, Medium risk and recorded non-causal explanation factors, then
assigns the generated warning. The Advisor confirms the warning, starts an
intervention, adds a note and schedules a follow-up. An unassigned advisor cannot
write a note. Transferring the intervention twice also transfers the scheduled
follow-up; its final owner returns to the original advisor. That advisor records
progress and completes both follow-up and intervention.

The administrator runs a semester assessment, edits the semester record, observes
the old assessment marked `INPUTS_CHANGED`, then runs reassessment. The new
operational prediction, earlier enrollment/semester predictions, completed case,
note attribution, follow-up and history timeline all remain persisted. A legacy
binary assessment is separately executed and asserted as binary, with no invented
multiclass probabilities.

The existing CSV contract includes semester fields. Consequently an enrollment
assessment can correctly be historical when semester assessment is recommended:
the header shows **Unavailable / Reassessment required** until a current eligible
assessment exists. This is intentional freshness behavior, not a missing label or
failed prediction. The test verifies that stale predictions do not silently
replace current risk. Models provide benchmark decision support, not institutional
validation or causal explanations.

## Remaining defects and blockers

No unresolved functional blocker was observed in the tested local workflow.
Repository coverage has one explicit exception: the separate
`codex/frontend-usability-onboarding` branch (`2d10cda`) is not an ancestor of
the requested D1.2 base. Its guide provider, guided next-actions and icon refresh
are absent. Thus the requested base contains the integrated academic workflows
and dark mode, but **does not contain every historical frontend branch**. E1
does not silently merge that separate feature work; its inclusion requires a
separate scope decision and integration pass. No core workflow in this matrix
depends on that optional guide. This exception qualifies the source-completeness
claim and the local demonstration verdict.

The genuine newly observed release failure is the dependency audit. The pinned
Next.js 16.3.8 is in the affected ranges of
[image optimization RCE](https://github.com/advisories/GHSA-2464-fhr4-w9xw),
[Server Actions DoS](https://github.com/advisories/GHSA-p3m5-59mp-jv5r) and
[`use cache` typed-array RCE](https://github.com/advisories/GHSA-673q-mjm6-r5xr).
The authoritative advisories, updated October 22, name 16.4.1 as patched; npm's
suggested resolution is 16.4.2, outside this exact pin. An E1 source search found
no application `use server`, `use cache`, `next/image` import or `cacheComponents`
configuration, and the tested frontend runtime is Alpine. These observations are
not a security clearance or an exploitability test. Dependency remediation and
compatibility verification remain a separate release task: E1 permits only
verified integration/usability fixes, so dependencies were not changed incidentally.
The local demonstration must remain confined to loopback, synthetic inputs and
trusted users; do not expose this build to a university network or the internet.

D1.1's authorization fix and D1.2's gates are preserved. D1's remaining public
deployment concerns (abuse controls, chosen secure topology/secrets and operational
recovery) and D1.2's hosted enforcement blocker require separate work. E1 neither
reruns a public deployment audit nor certifies hosted CI success.

## Reproduction

Prerequisites: Docker Linux engine, Python 3.11.9, Node/npm, trusted package
registries and the retained approved private legacy model file. Do not download
an arbitrary pickle or commit the private artifact. The two approved outcome
artifacts are already tracked. From repository root:

```powershell
python scripts/ci/provision_models.py --source C:\private\approved-legacy-model.joblib
python scripts/ci/provision_models.py --verify-only
python scripts/acceptance/stack.py up
Set-Location acceptance
npm ci
npx playwright install chromium
npm test
Set-Location ..
python scripts/acceptance/stack.py regress
```

`up` builds production images, migrates the new database and bootstraps the
synthetic system administrator. It prints only project/HTTP locations. The suite
performs mandatory password changes, creates the other accounts, validates the
models and runs the complete workflow. It must start from an unused demonstration
database. To repeat against the same stack:

```powershell
python scripts/acceptance/stack.py reset-demo
Set-Location acceptance
npm test
Set-Location ..
```

`reset-demo` verifies the database/backend ownership labels and replaces only the
owned `e1_demo` database, never an institutional or shared database. Regression
is intended once per new stack invocation (the named runner is retained for
evidence). For another regression run, close and create a new invocation.

For manual presentation, the authorized local operator can read the generated
private session file without sharing it. Use separate browser profiles for the
three roles and the generated final passwords after the suite. Open the printed
frontend URL, inspect E1-001, and follow the screenshots/history. To perform the
workflow manually from blank data, reset first and follow the suite's CSV and
form values; initial passwords then require replacement. No real student records
or operational credentials are needed. Raw local logs, HTTP evidence and JUnit
reports remain under ignored `.venv/e1*` and `output/playwright/e1`; only reviewed
synthetic screenshots and redacted summaries are committed.

Capture evidence before cleanup. Then:

The independent frontend checks used for this report are reproducible from
`frontend` with `npm ci`, `npm run typecheck`, `npm run build` and
`npm audit --audit-level=low`. The audit currently exits 1 as recorded above;
do not treat that failure as a passed release gate. The backend regression helper
executes the existing D1.2 mandatory gate, including its model/migration preflight
and all seven disposable PostgreSQL integration settings.

After capturing evidence, close the stack:

```powershell
python scripts/acceptance/stack.py down
```

Cleanup positively checks invocation ownership, removes only its containers,
empty network and owned image references, and rejects referenced/shared images.
No Docker prune or shared-resource mutation is used. Rebuild with `up` for a later
demonstration; the verification stack is not left running as an operational service.

For this execution, cleanup exited 0. No containers, networks or images with the
E1 invocation label remain. The before/after shared-resource ID inventory was
unchanged (4 running containers, 12 networks, 49 image-list entries). No shared
Docker resources were removed or modified and no prune was run. Thirty-nine
reviewed synthetic PNGs, including the homepage before correction, accompany this
report; their exact paths and SHA-256 values are in the evidence file.
