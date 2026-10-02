# Academic Risk Overview implementation

Implemented in the existing Next.js frontend on `feat/frontend-dashboard-overview`, based on Phase 8 commit `30d079553214b48c7d8e28d764fa5037db55d07f`. No PR, push, merge, backend changes, migrations, or additional Vite application.

The screen retains the reference's navy application shell, cool surface tokens, Geist typography, compact KPI cards, paired activity/status panels, risk accents, and dense attention table. It uses scoped CSS and inline SVG without adding dependencies. Mobile navigation collapses into a drawer, analytics stack, and the table scrolls within its own container.

## Data and behavior

- `/dashboard` is a client-side authenticated landing screen. Successful login redirects there. Identity comes from `/auth/me`; tokens remain in sessionStorage.
- All dashboard data comes from `/dashboard/overview`. No warnings/predictions/interventions list fetches or per-row profile requests occur on load.
- Four KPI cards map to the requested backend fields. Chart series use actual dates and created / confirmed + dismissed counts. Only presentation percentages are calculated.
- Reviews post CONFIRMED or DISMISSED plus a required nonblank note to `/warnings/{id}/reviews`. The API actually returns WarningDetail, so the client types the consumed review receipt fields correctly. The existing backend also requires assigned-advisor ownership; the UI respects this.
- Interventions post the selected warning's student ID, warning ID, exact priority, and assigned advisor ID to `/interventions`. The action requires confirmation, an assigned advisor, and an eligible role/owner. Dates and text follow the existing validation contract.
- Only Academic Admin sees batch assessment, which posts to `/predictions/batch` and displays the actual synchronous response.
- Successful mutations close the dialog where applicable, show feedback, and reload the aggregate endpoint. Failures remain retryable. Any 401 clears the token and redirects to login, including simultaneous overview failure and auth failure.
- No fabricated records, prototype runtime imports, notification feeds, terms, advisor switching, trend values, export endpoint, compliance claims, or refresh-interval claims are included. Future navigation is visibly disabled.

## Changed files

```text
docs/frontend-dashboard-verification.md
frontend/app/dashboard/dashboard.css
frontend/app/dashboard/page.tsx
frontend/app/icon.svg
frontend/app/layout.tsx
frontend/app/login/page.tsx
frontend/components/dashboard/action-modal.tsx
frontend/components/dashboard/attention-table.tsx
frontend/components/dashboard/dashboard-shell.tsx
frontend/components/dashboard/icon.tsx
frontend/components/dashboard/intervention-summary.tsx
frontend/components/dashboard/kpi-card.tsx
frontend/components/dashboard/overview-view.tsx
frontend/components/dashboard/quick-intervention-modal.tsx
frontend/components/dashboard/review-warning-modal.tsx
frontend/components/dashboard/warning-activity-chart.tsx
frontend/components/layout/app-header.tsx
frontend/components/layout/app-sidebar.tsx
frontend/lib/api.ts
frontend/lib/dashboard.ts
frontend/types/dashboard.ts
```

## Commands and verification

From the repository root:

```powershell
git rev-parse HEAD
git status --short
git switch -c feat/frontend-dashboard-overview
Expand-Archive -LiteralPath D:\academic-early-warning-system.zip -DestinationPath C:\Users\Administrator\Desktop\reference-academic-ui -Force
```

From `frontend`:

```powershell
npm ci
npx --yes prettier@3.6.2 --write app/dashboard components/dashboard components/layout lib/dashboard.ts types/dashboard.ts lib/api.ts app/login/page.tsx app/layout.tsx
npm run typecheck
npm run build
```

Both typecheck and the production build passed. Build output includes `/dashboard`, `/login`, `/students`, `/students/[id]`, and `/imports`. No package manifest or lockfile changes were needed. Formatting's initial command included `app/icon.svg`; Prettier could not infer its parser, so that already valid SVG was excluded on the subsequent pass.

A final overlapping typecheck/build attempt encountered missing generated Next.js type files while the build regenerated them. The final build completed, and the subsequent serial `npm run typecheck` passed. These checks should be run serially because both depend on `.next/types`.

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/api/test_read_models.py tests/api/test_warnings.py tests/api/test_casework.py tests/api/test_predictions.py tests/api/test_auth.py tests/api/test_permissions.py
..\.venv\Scripts\python.exe -m pytest tests/api/test_students.py tests/api/test_imports.py
```

45 workflow/read-model/auth tests and 55 student/import regression tests passed, 100 total. An initial run from the repository root failed 21 tests because the ML artifact paths are relative to `backend`; rerunning from the correct directory passed all tests without backend changes.

Browser verification used `npx --yes --package @playwright/cli playwright-cli` (`open`, `goto`, `snapshot`, `click`, `reload`, `console`, and `run-code`). The Next.js dev server used a temporary `NEXT_PUBLIC_API_URL=http://localhost:8011/api/v1`. A temporary Python QA server reused existing backend fixtures in an isolated in-memory SQLite database. Neither temporary server/configuration nor fixture records are part of production code.

Verified in Chromium:

- Missing-token redirect, successful login redirect, real identity, sign-out and token removal.
- Advisor controls; System Admin has no review/intervention/batch controls; Academic Admin has batch/intervention eligibility and no review control.
- Blank and whitespace review notes blocked. Real confirmation POST returned 201 and refreshed overview.
- Real intervention POST returned 201, retained warning/student/priority/advisor linkage, closed the modal, and refreshed overview.
- Real batch POST returned 200 and every returned result appeared in the success banner.
- Fresh dashboard API requests were limited to `/auth/me` and `/dashboard/overview`.
- Desktop (1440px), tablet (820px), and phone (390px) layouts have no page overflow. Drawer navigation opens/closes; table overflow stays within the table.
- Controlled zero/null endpoint response rendered four zero KPIs, no model, no activity, no attention cases, and absent timestamps without fallback records.
- Controlled 503 response displayed a retryable error; retry recovered to live backend data.
- Controlled auth 401 with simultaneous overview 503 cleared the token and redirected to login.
- Delayed aggregate response rendered the initial loading state; filter changes and mobile Escape navigation worked without page errors.

The first temporary QA fixture omitted required prediction-explanation fields, causing a backend response-validation failure during review. The fixture was corrected and the real mutation passed; no production/backend code was changed to accommodate it. A duplicate section/input ID found during browser QA was fixed so the intervention title has its correct accessible label. Expected HTTP console errors occurred only during deliberately injected failure checks; normal successful flows had no application errors.

Final repository checks use `git diff --check`, a search for prototype mock symbols/fake claims, and `git diff --name-only` to verify frontend-only implementation scope plus this report. The local implementation commit is reported in the final handoff; retrieve it with `git log -1 --format=%H`.
