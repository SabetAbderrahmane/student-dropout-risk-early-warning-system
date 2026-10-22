# E1 acceptance matrix

Final execution: 2026-10-22 18:57:57 UTC (19:57:57 Africa/Casablanca).
Evidence finalized October 23. Actual Chromium → production Next.js → FastAPI →
PostgreSQL; no successful-response mocks. Nine serial scenarios passed in
95.829 seconds: zero skipped, unexpected or flaky tests. IDs below map directly
to `acceptance/tests/acceptance.spec.ts`. All screenshots use synthetic data.
Exact test durations, HTTP status counts, persistent IDs and PNG checksums are in
[verification evidence](phase-e1-verification-evidence.json).

## Roles and business process

| Case | Actor / action | Expected and observed result | Final result | Screenshot |
| --- | --- | --- | --- | --- |
| E1-01a | System Admin initial login | Required password change, then real dashboard; same for three created operators | PASS | [Users](../output/playwright/e1/screenshots/01-user-administration.png) |
| E1-01b | Create academic/admin and two advisor accounts plus disposable advisor | Real account forms complete; catalog shows intended roles | PASS | Users |
| E1-01c | Edit disposable user, deactivate/reactivate, reset password | Confirmed actions complete through UI; account audit persisted | PASS | Users |
| E1-02a | Academic Admin upload two-row official-schema CSV | Row 3 invalid age reported; commit disabled | PASS | [Staged validation](../output/playwright/e1/screenshots/02-staged-validation.png) |
| E1-02b | Correct staged age to 24, commit | Valid rows become committable, receipt displayed, E1-001/E1-002 persisted | PASS | [Receipt](../output/playwright/e1/screenshots/03-committed-import.png) |
| E1-02c | Registry create E1-003, edit E1-001 gender text | Forms complete; dossier renders updated synthetic value | PASS | [Dossier](../output/playwright/e1/screenshots/04-student-dossier.png) |
| E1-03a | System Admin inspect registry | Exactly three approved artifact-available model entries | PASS | [Models](../output/playwright/e1/screenshots/05-approved-model-registry.png) |
| E1-03b | Validate and activate enrollment and semester models | Real inference validation and activation persisted; all three scopes active | PASS | Models |
| E1-04a | Academic Admin run enrollment prediction | 201, Medium risk, three outcome probabilities sum to one, recorded factors present | PASS | [Explanation](../output/playwright/e1/screenshots/06-enrollment-assessment-explanation.png) |
| E1-04b | Assign prediction-generated warning to advisor | Warning exists and assigned advisor matches persisted account | PASS | [Assignment](../output/playwright/e1/screenshots/07-assigned-warning.png) |
| E1-05a | Advisor find assigned warning and confirm review | Warning visible; real review endpoint returns contracted 201 | PASS | [Advisor case](../output/playwright/e1/screenshots/08-advisor-intervention-and-note.png) |
| E1-05b | Create/start advising intervention, record note | Case persisted, IN_PROGRESS controls visible, attributed note saved | PASS | Advisor case |
| E1-05c | Schedule future in-person follow-up | Follow-up persisted with original advisor ownership | PASS | Advisor case |
| E1-06a | Other advisor inspect case and attempt note write | Add Note absent; real unauthorized POST returns 403 | PASS | API assertion |
| E1-06b | Academic Admin transfer intervention away and back | Scheduled follow-up owner follows both transfers, final owner restored | PASS | Persisted API and action audit |
| E1-06c | Advisor complete follow-up with progress outcome | Persisted COMPLETED, recorded progress note | PASS | [Follow-up](../output/playwright/e1/screenshots/09-completed-follow-up.png) |
| E1-06d | Advisor complete intervention with SUPPORT_COMPLETED | Persisted COMPLETED, note author preserved, linked child remains completed | PASS | [Completed case](../output/playwright/e1/screenshots/10-completed-intervention.png) |
| E1-07a | Run initial semester prediction, edit semester record | Earlier result becomes INPUTS_CHANGED; historical label appears | PASS | [Reassessment required](../output/playwright/e1/screenshots/reassessment-required.png) |
| E1-07b | Run semester reassessment | New operational result selected; Low risk; previous results/case/child retained | PASS | [History](../output/playwright/e1/screenshots/11-durable-case-history.png) |
| E1-07c | Inspect case history | Visible event count matches backend timeline; prediction, warning, note, completion events retained | PASS | History |
| E1-07d | Run legacy prediction from UI | BINARY_DROPOUT target, null multiclass probabilities; current semester outcome selection preserved | PASS | [Prediction matrix](../output/playwright/e1/screenshots/portrait-dark-predictions.png) |
| E1-09a | Advisor visit Users and Imports | Permission-denied/restricted headings; no access granted | PASS | Assertions |
| E1-09b | Forbidden writes/read by advisor, academic admin and system admin | All three actual API requests return 403; DENIED students absent | PASS | Persisted integrity evidence |
| E1-09c | Expired token boundary | Real 401 causes sign-in redirect; normal login succeeds afterward | PASS | [Expired session](../output/playwright/e1/screenshots/15-expired-session-sign-in.png) |
| E1-09d | System Admin deactivate another logged-in advisor | Existing advisor session redirects to login | PASS | Assertions and account state |

## Every implemented screen

E1-08 visits each of the ten authenticated routes below at desktop 1440×1000,
then dark landscape tablet 1024×768 and portrait tablet 768×1024, with real data
requests settled and zero busy regions. Each has a visible page heading, no
placeholder `href="#"` links and no document horizontal overflow at either
tablet size. It switches back to light mode and verifies the theme attribute.
It separately clicks all implemented main navigation links and exercises the
portrait navigation drawer open/link/close behavior. Disabled, labelled “Later”
items are intentionally outside the implemented application scope.

| Route | Screen / authorized actor for sweep | Result | Dark portrait screenshot |
| --- | --- | --- | --- |
| `/dashboard` | Academic risk overview / Academic Admin | PASS | [Dashboard](../output/playwright/e1/screenshots/portrait-dark-dashboard.png) |
| `/students` | Registry / Academic Admin | PASS | [Registry](../output/playwright/e1/screenshots/portrait-dark-students.png) |
| `/students/[id]` | Dossier / Academic Admin | PASS | Dynamic student-ID PNG listed in evidence |
| `/imports` | CSV onboarding / Academic Admin | PASS | [Imports](../output/playwright/e1/screenshots/portrait-dark-imports.png) |
| `/predictions` | Predictions and model registry / System Admin | PASS | [Models and assessments](../output/playwright/e1/screenshots/portrait-dark-predictions.png) |
| `/warnings` | Warning workspace / Academic Admin | PASS | [Warnings](../output/playwright/e1/screenshots/portrait-dark-warnings.png) |
| `/interventions` | Intervention workspace / Academic Admin | PASS | [Interventions](../output/playwright/e1/screenshots/portrait-dark-interventions.png) |
| `/follow-ups` | Follow-up workspace / Academic Admin | PASS | [Follow-ups](../output/playwright/e1/screenshots/portrait-dark-follow-ups.png) |
| `/admin/users` | User administration / System Admin | PASS | [Users](../output/playwright/e1/screenshots/portrait-dark-admin-users.png) |
| `/change-password` | Password form / Academic Admin | PASS | [Password](../output/playwright/e1/screenshots/portrait-dark-change-password.png) |
| `/` | Public homepage, final copy and sign-in link | PASS | [Homepage](../output/playwright/e1/screenshots/16-home-tablet-dark.png) |
| `/login` | Public sign-in, mandatory password replacement in E1-01 | PASS | [Sign-in](../output/playwright/e1/screenshots/17-login-tablet-dark.png) |

| Cross-screen condition | Method and expectation | Result | Evidence |
| --- | --- | --- | --- |
| Empty registry | Search impossible synthetic identifier; “No students found” | PASS | [Empty state](../output/playwright/e1/screenshots/12-empty-registry-search.png) |
| Loading dashboard | Delay a real overview request; loading indicator visible; continue request | PASS | [Loading](../output/playwright/e1/screenshots/13-loading-dashboard.png) |
| Offline dashboard | Abort one overview request; alert appears; remove fault and Retry real backend | PASS | [Error state](../output/playwright/e1/screenshots/14-offline-error-state.png) |
| JavaScript runtime / console | Observe all browser pages across scenarios; no page errors or non-resource console errors | PASS | Empty error arrays in evidence |
| Current vs historical prediction | Change inputs; inspect historical label and new operational ID; all 4 predictions retained | PASS | Reassessment, history and persisted profile |
| Cross-record SQL integrity | Orphans, warning/student mismatch, case/student mismatch, child student/owner mismatch all zero | PASS | Evidence `persisted.integrity` |
| Regression isolation | No leftover generated test databases or public tables in release_gate | PASS | Evidence `persisted.integrity` |

## Verification and unexecuted coverage

| Item | Classification | Evidence / limitation |
| --- | --- | --- |
| Full backend suite / mandatory PostgreSQL suites | PASS | 544/544, zero skips; per-module counts in evidence |
| Alembic, all three checksums, real inference probes | PASS | Fresh migration roundtrip/drift checks and live image verifier logs |
| Release gate negative controls | PASS | 24/24 |
| Frontend clean install, typecheck, native and Docker builds | PASS | Log checksums and image IDs in evidence |
| Targeted Python lint | PASS | Ruff F,E9 |
| Frontend dependency audit | **FAILED** | Next.js 16.3.8 affected package; three advisories in main report; no incidental dependency upgrade |
| Hosted Actions / branch enforcement | **UNVERIFIED / inherited blocker** | E1 local runs are not evidence that hosted runner/plan restrictions have been resolved |
| Firefox / Safari / phone layouts | **UNEXECUTED** | Chromium desktop and tablets only |
| Exhaustive modal error permutations, formal accessibility, load/penetration tests | **UNEXECUTED** | No claim beyond listed checks |
| Internet deployment, TLS/edge, real institutional data, recovery exercise | **UNEXECUTED / NO-GO** | Outside this local acceptance scope; existing deployment findings remain |

No test omitted above is counted as passed. Earlier harness failures and
successful reruns are documented in the [final report](phase-e1-final-acceptance.md).
