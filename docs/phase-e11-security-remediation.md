# E1.1 Next.js security remediation and acceptance reverification

Date: 2026-10-23, Africa/Casablanca. Base:
`6881d78e4240f6bc15f5253e019f5e7949816e90` on
`codex/phase-e1-final-acceptance`. Delivery branch:
`codex/phase-e11-security-remediation`.

**Local university thesis demonstration: GO**, for the tested synthetic,
loopback-only application operated by trusted users. All required E1.1 checks
passed. **Internet deployment: NO-GO** until the existing deployment prerequisites
and hosted enforcement limitations are resolved separately.

This report supersedes E1's failing frontend dependency-audit result. The
[E1 report](phase-e1-final-acceptance.md)
and [acceptance matrix](phase-e1-acceptance-matrix.md) remain historical records.
Machine-readable results, package changes, model checksums, runtime image identity
and persistent synthetic workflow evidence accompany this report in
[verification evidence](phase-e11-verification-evidence.json).

## Dependency decision

The existing manifest and lockfile both resolved Next.js **16.3.8**. Before any
change, `npm audit --audit-level=low --json` reproduced exit 1: one critical
affected package, with these three maintainer advisories:

| Official maintainer advisory | Minimum patched 16.x release |
| --- | --- |
| [GHSA-2464-fhr4-w9xw: image optimization RCE](https://github.com/vercel/next.js/security/advisories/GHSA-2464-fhr4-w9xw) | 16.4.1 |
| [GHSA-p3m5-59mp-jv5r: App Router Server Actions DoS](https://github.com/vercel/next.js/security/advisories/GHSA-p3m5-59mp-jv5r) | 16.4.1 |
| [GHSA-673q-mjm6-r5xr: typed-array cache RCE](https://github.com/vercel/next.js/security/advisories/GHSA-673q-mjm6-r5xr) | 16.4.1 |

Both 16.4.1 and 16.4.2 were checked against the official npm package metadata.
Both require Node >=20.9.0, support the existing React/React DOM 19.3.0 through
their peer ranges, and require optional sharp ^0.35.5. The existing lockfile
already resolves sharp 0.35.5. The image-optimization advisory specifies that
version as the fixed upstream minimum; it was not downgraded or overridden.

**Selected exact pin: Next.js 16.4.2.** 16.4.1 is the security minimum;
[16.4.2 is an available maintenance patch](https://github.com/vercel/next.js/releases/tag/v16.4.2)
on that same minor line, including Turbopack snapshot/module-graph/GC fixes.
The additional patch was evaluated with the existing application's typecheck,
production builds and complete real-browser suite. No later minor/major upgrade
or unrelated dependency refresh was introduced. Version 16.4.1 was evaluated
through metadata/advisories, not separately installed or claimed as tested.

The implementation changes only `frontend/package.json` and its lockfile.
`next`, `@next/env` and eight platform-specific `@next/swc-*` resolutions move
from 16.3.8 to 16.4.2. All other resolved package versions remain unchanged,
including React **19.3.0**, React DOM **19.3.0**, TypeScript **5.9.3**, and sharp
**0.35.5**. No compatibility source changes were necessary.

The bounded update command was:

```powershell
Set-Location frontend
npm install --package-lock-only --ignore-scripts --save-exact next@16.4.2
npm ci
npm run typecheck
npm run build
npm audit --audit-level=low --json
```

No `npm update`, `npm audit fix --force`, security ignore, audit omission or
dependency override was used. The baseline and resulting raw audit reports are
saved as [before](evidence/e11/npm-audit-before.json) and
[after](evidence/e11/npm-audit-after.json). Package integrity fields were updated
by npm and checked by clean installation.

## Verification

Exact outcomes and timings are recorded in the machine-readable evidence. The
required checks are executed against the final dependency coordinates:

| Check | Result / evidence |
| --- | --- |
| Clean frontend installation | **PASS**, `npm ci`; exact lockfile, no peer override |
| TypeScript | **PASS**, `npm run typecheck` |
| Native production build | **PASS**, `npm run build`, Node 24.14.0 |
| Frontend audit | **PASS**, exit 0, **zero vulnerabilities**; full `npm audit --audit-level=low`, including development/optional dependencies |
| Full production Docker build/start | **PASS**, existing backend and standalone frontend Dockerfiles |
| Installed production runtime | **PASS**, Next.js **16.4.2**, React/React DOM **19.3.0**, sharp **0.35.5**, Node **22.23.4**, queried inside running production container |
| Backend mandatory release gate | **544 passed, zero skips**, 768.14 seconds, Python 3.11.9; all seven disposable PostgreSQL settings, eight required modules, `RUN_MODEL_INTEGRATION=1`, exit 0 |
| Migration checks | **PASS**, empty disposable upgrade/current/drift check, downgrade/base/re-upgrade/check; running application at `20261014_0012` |
| Model integrity | **PASS**, all three exact bytes verified before deserialization; both production deployment verifiers and actual browser inference |
| Browser acceptance | **9 passed**, 87.301 seconds, **zero skips/failures/flaky tests**, unchanged E1 suite, one worker and zero retries, real backend/database |
| D1.2 release negative controls | **24 passed**, 3.65 seconds |
| Targeted Python lint | **PASS**, Ruff F,E9 on existing application/release/acceptance targets |

The backend reported 298 existing warnings (including pandas dtype/sklearn
probability warnings), matching E1's warning count. None was suppressed or
counted as a skip. The runner exited 0; no generated fixture databases or public
tables remained in `release_gate`. All required checks completed; there are no
unresolved E1.1 test failures or executable-check blockers. Hosted/public and
additional-browser checks listed below remain unexecuted, not passed.

The Docker invocation uses the existing E1 helper and a fresh ownership-labelled
network, tmpfs PostgreSQL, new random credentials and loopback-only HTTP ports.
No institutional data or pre-existing database is used. Browser and backend
regression databases are separate. Model activation, academic writes and casework
actions occur through real UI forms; authenticated API reads and SQL checks
confirm persistence. The existing loading/offline fault injections and expired
token negative check remain exactly as documented in E1; successful responses
are never mocked.

The regression runner retains D1.2's explicit `APP_ENV=test` and
`ML_MODEL_REQUIRED=false` fixture settings with `RUN_MODEL_INTEGRATION=1` and
`RELEASE_DISPOSABLE_POSTGRES=1`. These permit the existing startup-negative tests;
they do not skip artifact verification or real model integration. The production
backend image retains its required-model default.

The repeated business workflow is CSV staging → invalid-row correction → commit
→ registry/edit → enrollment assessment/explanation → warning assignment → advisor
review → intervention/note → follow-up → ownership transfers → completion →
semester update → stale-result detection → reassessment → durable case history.
Legacy binary inference also runs. Enrollment, current/historical semester
predictions, advisor ownership, recorded notes and completed support records are
cross-checked against the real backend and database.

Persisted SQL checks found three synthetic students, four prediction records, one
reviewed warning, one completed intervention, its attributed note and completed
follow-up. Orphan prediction, warning/student, intervention/student and follow-up
student/owner mismatches were all zero; forbidden writes left no student records.
All four probabilities, risk tiers and freshness selections match E1 exactly for
the identical synthetic inputs. New reviewed screenshots show the
[enrollment explanation](evidence/e11/06-enrollment-assessment-explanation.png),
[completed case](evidence/e11/10-completed-intervention.png),
[durable history](evidence/e11/11-durable-case-history.png) and
[dark tablet dashboard](evidence/e11/tablet-dark-dashboard.png).

There were no frontend build or browser acceptance failures in this run. One
supplementary inspection initially tried an unexported `sharp/package.json`
package subpath; reading the installed manifest directly confirmed 0.35.5. This
was a diagnostic correction and required no application change.

## Preservation and scope

Backend application source, tests, migrations, Python/scientific dependencies,
manifests, parameters and all three artifacts remain unchanged from E1. The
approved SHA-256 values remain:

| Artifact | SHA-256 |
| --- | --- |
| Retained binary dropout model | `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8` |
| Enrollment outcome model | `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602` |
| First-semester outcome model | `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81` |

No model retraining, scientific experiment, new feature, schema alteration,
authentication-contract change, C1/D1.1 behavior change or security bypass is
part of this work. Existing synthetic model-pipeline regression fixtures still
run as ordinary tests; no approved artifact is regenerated. Routing, React
components, styling, themes and API client source remain unchanged.
The optional onboarding branch remains unmerged, as explicitly required.
Repository visibility, GitHub plan and hosted CI enforcement settings are untouched.
Local execution does not establish hosted runner or branch-protection readiness.

Hosted Actions/enforcement, internet deployment, load/penetration testing and
additional browser engines were not verified by this phase. Existing public
deployment prerequisites remain separate from the local synthetic demonstration.

## Reproduction and evidence handling

Use the [E1 reproduction instructions](phase-e1-final-acceptance.md#reproduction)
with the E1.1 branch and its pinned lockfile. After provisioning the trusted
private artifact, run `python scripts/acceptance/stack.py up`, run `npm ci` and
`npm test` from `acceptance`, and run
`python scripts/acceptance/stack.py regress` from repository root. The browser
suite requires a fresh demonstration database; `reset-demo` replaces only the
owned synthetic database if a repeat is needed. Capture runtime package versions
before invoking `down`.

Private generated credentials, environment files, tokens, model binaries and raw
failure artifacts are not committed. The unchanged browser suite uses E1 output
paths; this run's output is copied to ignored `.venv/e11/browser`, then historical
tracked E1 images are restored so their earlier checksums remain valid. Reviewed
new synthetic screenshots and redacted summaries are retained separately for E1.1.
Cleanup validates invocation ownership before removing only this run's containers,
empty network and image references. Shared Docker resources and caches are not
pruned or altered.

The owned E1.1 invocation was `e1-acceptance-31f71547f3` (the unchanged helper
retains its E1 prefix), with frontend `127.0.0.1:54780`, backend `127.0.0.1:54779`
and PostgreSQL 16.13 without a host port. Cleanup exited 0. The final labelled
resource query and before/after shared-resource comparison are recorded in the
evidence file. The private session state is archived locally; no verification
containers remain serving a demonstration after cleanup. Recreate the stack with
`up` to present it later.
