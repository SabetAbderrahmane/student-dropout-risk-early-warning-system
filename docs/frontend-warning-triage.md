# Screen 3: Early Warnings / Advisor Triage

Implemented `/warnings` inside the existing Next.js frontend on
`feat/frontend-dashboard-overview`. Screen 1 remains intact. The existing
Screen 2 work was preserved in commit `ebe7742` before Screen 3 was added.
The reference `D:\scrreen 3 .zip` was inspected in place; no Vite application,
prototype data, or prototype business logic was integrated.

## Production behavior

| Feature | Source / behavior |
| --- | --- |
| Warning queue | `GET /api/v1/warnings`; backend filtering, sorting and pagination |
| Search | Student name / student ID; 300 ms debounce |
| Filters | Priority, review state, risk level; advisors can filter their own assignments using their authenticated UUID |
| Sorting | Priority, newest/oldest warning, highest/lowest probability, risk level, review state, student ID |
| Page metadata | Backend `page`, `page_size`, `total`, `total_pages`; sizes 25/50/100 |
| Review/confirmed/dismissed KPIs | `GET /api/v1/dashboard/overview`, `warnings` counts |
| High-risk warning KPI | `GET /api/v1/warnings?risk_level=HIGH&page=1&page_size=1`, response `total` |
| Warning detail | `GET /api/v1/warnings/{id}`, fetched only for the opened warning |
| History | `GET /api/v1/students/{student_id}/predictions`, fetched only inside the opened modal; paginated real prediction dates and probabilities |
| Review | `POST /api/v1/warnings/{id}/reviews`, explicit confirm/dismiss decision and mandatory trimmed nonblank note |
| Intervention | Separate explicit modal/submission to `POST /api/v1/interventions`, reusing the existing form and real enum types |
| CSV | Explicitly exports only the current loaded warning page, using real row fields and quoted cells |

The shared sidebar uses Next.js links and marks `/warnings` active. The shared
header uses the authenticated account. Bearer authentication, session storage,
API configuration, error handling, and the shared modal remain in the existing
architecture. Superseded queue, detail, and prediction requests are aborted.

The four KPI cards show institution-wide counts, independently of queue filters.
Unavailable counts show an unavailable marker with retry messaging; zero counts
show zero. Skeletons never show fake values.

Only the exact assigned Academic Advisor sees a review form for a pending warning.
System admins read warnings. Academic admins can create interventions for confirmed
warnings with valid assignee UUIDs; advisors can do so only for their own confirmed
warnings. Backend enforcement remains authoritative. Successful review refetches
detail, queue, and KPI data; it never automatically creates an intervention.

The modal presents backend explanation labels, feature values, and signed
contributions. Bars show relative absolute contribution within that prediction,
with raw numeric values rather than fabricated importance percentages. Prediction
history is separate from the warning's assessment; one point shows its value/date
without a fabricated trajectory. No list row requests prediction history.

Unsupported prototype features were omitted: batch review, quick local state
changes, fake advisor directories/assignment, term/cohort/college filters,
notifications, LMS/attendance triggers, confidence/SHAP/ensemble claims,
compliance claims, and unrelated mock screens. Warning assignment remains
read-only because the backend lacks an advisor-directory contract.

## Changed files

New:

- `frontend/app/warnings/page.tsx`
- `frontend/app/warnings/warnings.css`
- `frontend/components/warnings/warning-workspace.tsx`
- `frontend/components/warnings/warning-kpi-strip.tsx`
- `frontend/components/warnings/warning-filters.tsx`
- `frontend/components/warnings/warning-table.tsx`
- `frontend/components/warnings/warning-detail-modal.tsx`
- `frontend/components/warnings/warning-review-form.tsx`
- `frontend/components/warnings/create-intervention-modal.tsx`
- `frontend/components/warnings/explanation-factors.tsx`
- `frontend/components/warnings/prediction-history-chart.tsx`
- `frontend/types/warning.ts`
- `frontend/lib/warnings.ts`
- `docs/frontend-warning-triage.md`

Extended shared code:

- `frontend/lib/api.ts`: typed warnings/detail/history requests, full review response,
  optional cancellation signal for dashboard overview.
- `frontend/components/layout/app-sidebar.tsx`: live Early Warnings route.
- `frontend/components/dashboard/action-modal.tsx`: optional scoped styling class.
- `frontend/components/dashboard/quick-intervention-modal.tsx`: optional title and
  narrower context type, with the dashboard's defaults preserved.

No backend, dependency, authentication-storage, or existing screen-route changes.

## Commands and results

From `frontend`:

```powershell
npm.cmd run typecheck
npm.cmd run build
npm.cmd run start -- --port 3000
```

TypeScript and production build passed. The route output includes `/dashboard`,
`/students`, `/students/[id]`, and `/warnings`. The existing standalone build
configuration emits an advisory during `npm run start`; the browser checks below
ran successfully against that local preview.

From `backend`:

```powershell
& '..\.venv\Scripts\python.exe' -m pytest tests/api/test_warnings.py tests/api/test_read_models.py tests/api/test_casework.py tests/api/test_predictions.py -q
```

**32 tests passed.** These cover warning contracts/filtering/history, assignment
and review RBAC, intervention ownership and state gates, prediction behavior, and
read-model semantics using the existing isolated test database.

Browser validation used the Playwright CLI against the built frontend:

```powershell
npx.cmd --yes --package @playwright/cli playwright-cli -s=warnings open http://localhost:3000/warnings
npx.cmd --yes --package @playwright/cli playwright-cli -s=warnings run-code --filename <external-artifact-directory>/warnings-check.js
npx.cmd --yes --package @playwright/cli playwright-cli -s=warnings run-code --filename <external-artifact-directory>/warnings-edge-check.js
```

Both browser workflows passed. They checked KPI source distinctions, no eager
detail/history requests, filter mappings, page resets, server sorting, search,
density, CSV contents (50 loaded rows and one header), modal sections, mandatory
notes, assigned-advisor-only review, separate explicit intervention creation,
read-only roles, unassigned warnings, empty/error/retry states, 401 session clearing,
403/409 errors without optimistic state changes, dismissal, zero KPIs, single-point
history, stale request cancellation, and navigation through Screens 1 and 2.

Rendered desktop (1440 px), tablet (1024 px), and mobile (390 px) layouts were
inspected. Page and mobile modal overflow checks passed. Desktop table actions
remain visible while scrolling; mobile uses deliberate table overflow. Native
dialogs support keyboard containment, Escape dismissal, and focus restoration.

Formatting used Prettier on the changed frontend files. `git diff --check` passed,
and source scans found no `any`, prototype data dependencies, local quick-status
mutation, unsupported domain/compliance claims, or queue-side sorting.

Browser checks used temporary API fixtures outside the repository; no fixture data
ships in the application. Live PostgreSQL integration was not exercised. No PR was
created and no merge to `main` was performed.
