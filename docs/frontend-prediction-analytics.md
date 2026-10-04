# Screen 4: Risk Predictions & Model Performance

Implemented `/predictions` in the existing Next.js frontend on
`feat/frontend-dashboard-overview`. Screens 1–3 are preserved. The source ZIP
`D:\screen 4.zip` was inspected in place as a visual reference. No Vite application,
prototype data, threshold simulation, or backend model files were integrated.

## API responsibilities

| Display / action | Authoritative source |
| --- | --- |
| Prediction matrix | `GET /api/v1/predictions`, server search, filters, sorting and pagination |
| Unique students assessed and latest risk distribution | `GET /api/v1/dashboard/overview` |
| Model identity, dataset, schema, training date, artifact availability, thresholds | `GET /api/v1/models/current` |
| All performance metrics, test sample size, confusion matrix, feature importance | `GET /api/v1/models/current/performance` |
| Opened prediction detail, input snapshot and explanation method | `GET /api/v1/predictions/{id}` |
| Opened student's prediction history | Existing `GET /api/v1/students/{id}/predictions` component |
| Explicit Academic Admin batch action | Existing `POST /api/v1/predictions/batch` client and exact completion receipt |

There are five initial requests: authenticated user and the four page APIs.
Prediction detail and history load only after opening a record. There are no
per-row warning or advisor requests. Filter, sort and page-size changes reset
the page to one. Search is debounced by 300 ms. Page sizes are 25, 50 and 100;
displayed pagination metadata comes directly from the response.

Unique assessed students, historical prediction record totals, and final-test
sample size have distinct labels and sources. Final-test metrics are never
computed from the current prediction page. Global feature importance uses the
known backend method: permutation importance on development data, scored by
PR-AUC. Bars scale by the largest absolute returned importance; displayed
values retain their sign and are not assumed to sum to one.

The confusion matrix evaluates binary dropout versus non-dropout. Its cell
positions are TP/FN in the actual-dropout row and FP/TN in the non-dropout row.
Operational Low/Medium/High thresholds are separately displayed as read-only
metadata. Row badges retain the backend risk level regardless of the displayed
current-model thresholds. Model identity and thresholds are never hard-coded.

The detail modal displays the backend explanation method, signed contributions,
raw snapshot values and creator. Empty and single-point histories do not invent
a trajectory. Student profile and warning queue links preserve the existing
casework boundary; prediction rows cannot create interventions.

Batch execution is shown only to `ACADEMIC_ADMIN`, prevents concurrent duplicate
submissions, and displays the actual assessed/skipped/prediction/warning counts,
model version and completion timestamp. Success refetches predictions, dashboard
aggregates, metadata and performance. The page handles loading, empty,
permission, model-unavailable and partial-endpoint failure states. A 401 clears
the session token and redirects to login. CSV exports only the loaded page's
real fields; JSON exports only the loaded global feature importance.

## Files changed

New files:

- `frontend/app/predictions/page.tsx`
- `frontend/app/predictions/predictions.css`
- `frontend/components/predictions/predictions-workspace.tsx`
- `frontend/components/predictions/model-kpi-strip.tsx`
- `frontend/components/predictions/feature-importance-card.tsx`
- `frontend/components/predictions/performance-card.tsx`
- `frontend/components/predictions/model-metadata-card.tsx`
- `frontend/components/predictions/predictions-filters.tsx`
- `frontend/components/predictions/predictions-table.tsx`
- `frontend/components/predictions/prediction-detail-modal.tsx`
- `frontend/components/predictions/model-details-modal.tsx`
- `frontend/components/predictions/batch-prediction-result.tsx`
- `frontend/types/prediction.ts`
- `frontend/lib/predictions.ts`
- `docs/frontend-prediction-analytics.md`

Modified files:

- `frontend/lib/api.ts`: typed prediction/model reads using the existing API client and optional abort signals.
- `frontend/types/registry.ts`: compatibility re-export of the strengthened canonical performance contract.
- `frontend/components/layout/app-sidebar.tsx`: active Next.js link to `/predictions`.

## Verification commands and results

From `frontend`:

```powershell
npx.cmd prettier --write app/predictions components/predictions types/prediction.ts types/registry.ts lib/predictions.ts lib/api.ts components/layout/app-sidebar.tsx
npm.cmd run typecheck
npm.cmd run build
npx.cmd prettier --check app/predictions components/predictions types/prediction.ts types/registry.ts lib/predictions.ts lib/api.ts components/layout/app-sidebar.tsx
npm.cmd run start -- --port 3000
```

Type checking, formatting checks and the final production build passed. The
build includes `/dashboard`, `/students`, `/students/[id]`, `/warnings` and
`/predictions`. The preview server retains the existing Next.js standalone
configuration advisory; no build configuration was changed.

From `backend`:

```powershell
& 'C:\Users\Administrator\Desktop\zak\.venv\Scripts\python.exe' -m pytest tests/api/test_predictions.py tests/api/test_read_models.py tests/api/test_warnings.py tests/api/test_casework.py -q
```

Result: **32 passed in 26.62 seconds**.

Browser commands from the repository root:

```powershell
npx.cmd --yes --package @playwright/cli playwright-cli -s=screen4 open http://localhost:3000/login
npx.cmd --yes --package @playwright/cli playwright-cli -s=screen4 run-code --filename 'C:\Users\Administrator\.codex\visualizations\2026\10\04\01a10807-3636-73f2-9cc4-cfeab7fe8e2e\screen4\predictions-check.js'
npx.cmd --yes --package @playwright/cli playwright-cli -s=screen4 run-code --filename 'C:\Users\Administrator\.codex\visualizations\2026\10\04\01a10807-3636-73f2-9cc4-cfeab7fe8e2e\screen4\predictions-edge-check.js'
npx.cmd --yes --package @playwright/cli playwright-cli -s=screen4 close
git diff --check
```

Both browser scenarios passed against the production build. Fixtures and
screenshots are outside the repository in the path above. Checks covered:

- Five initial authenticated requests and no per-row detail/history requests.
- Distinct sources: 19 unique assessed students, 75 prediction records, final-test N = 1,000.
- Backend risk badge preserved even when deliberately different from current threshold interpretation.
- Server-side risk/model/search/sort queries, page changes, reset to page one and sizes 25/50/100.
- Detail, actual explanation method, signed factors, raw snapshot and selected-student history.
- Empty factors/snapshots/history and single-history-point behavior.
- Read-only model dialog; alternative backend model name, version, thresholds and artifact flag.
- Academic Admin batch receipt/refetch; hidden batch action for System Admin and Academic Advisor.
- 403/503 batch errors, queue permission/error states, missing model, unavailable runtime and partial performance failure.
- Loading skeletons, zero assessed students, empty queue/importance and safe zero distribution.
- Detail/history retry; 401 session clearing and login redirect.
- CSV and JSON downloads inspected for actual loaded fields and values.
- Desktop 1440 px, tablet 1024 px and mobile 390 px screenshots; no document/modal horizontal overflow, Escape and focus restoration.
- Dashboard, registry and warning routes still render successfully.

The successful primary scenario made 77 requests across all interactions and
had no uncaught browser exceptions. Intentionally failed HTTP responses produce
expected browser console network errors. Visual inspection identified and
fixed inherited dashboard table sizing in the confusion matrix.

Live PostgreSQL/inference integration was not exercised by these browser tests;
they used API contract fixtures. Relevant backend behavior was checked by the
existing API test suite. No production mocks, package changes, backend changes,
PR or merge to `main` were introduced.
