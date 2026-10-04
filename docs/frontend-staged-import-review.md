# Screen 5: staged CSV import review

Implemented at `/imports`, with resumable selection at `/imports?batch=<id>`, on `feat/frontend-staged-csv-review`. The implementation builds on backend commit `07bee774bb2044cbc28751d5e53d7d2832c6b9d6`. Backend code, migration, dependencies and Screens 1–4 are unchanged. No merge to main or pull request was performed.

## Integration

Screen 5 uses the existing sessionStorage JWT, shared API base (`NEXT_PUBLIC_API_URL`), sidebar, header, error presentation and accessible ActionModal. The AI Studio ZIP was inspected as a visual reference only. Its navy/lavender palette, workflow steps, four summary cards, diagnostic table and execution panel inform the page. Prototype data, invented academic fields, automatic corrections and simulated progress were not imported.

Academic Admin can upload, correct, exclude, restore, commit and cancel. System Admin sees read-only row details, template, export, history and audit. Academic Advisor sees an access restriction and makes no staged-import requests. A 403 removes write controls; a 401 clears the existing session and redirects to login.

API routes integrated (all beneath `/api/v1`):

- `POST /imports/staged/csv`: real multipart `file` upload.
- `GET /imports/staged`: status and server pagination.
- `GET /imports/staged/{id}`: authoritative summary/state/revision/receipt.
- `GET /imports/staged/{id}/rows`: search, valid, included and server pagination.
- `PATCH /imports/staged/{id}/rows/{row_id}`: captured batch/row revisions, exact string corrections and/or inclusion.
- `POST /imports/staged/{id}/commit` and `/cancel`: current batch revision.
- `GET /imports/staged/{id}/export`: backend canonical CSV download.
- `GET /imports/staged/{id}/actions`: paginated audit records.
- `GET /imports/template`, `GET /imports`, `GET /imports/{id}/errors`: existing official template and history contracts.

Screen 5 never calls `POST /imports/csv`. The old immediate-import helper/component remain available unchanged.

## UI and state decisions

The review hook separates authentication, batch list, batch detail and row-page requests. Reads are abortable when selection/filter changes. A synchronous ref lock prevents duplicate mutations. Each successful row mutation adopts its returned batch revision, then reloads batch detail and the current row page; sibling duplicate validation is never updated optimistically. Writes require matching batch and row-page revisions. Search is debounced, while filter changes reset page one. Page counts come from the backend.

The editor uses fields returned by `edited_values`, preserves original values and sends changed values as unnormalized strings. Backend issues remain visible. Stale edits preserve the unsaved draft, refresh authoritative data, block resubmission and require closing/reviewing before a new manual edit. Requests are never automatically replayed. Commit rejection retains backend error details and refreshes rows and summary. Terminal batches offer read/export/audit only, with the actual receipt on success.

Invalid rows and issue counts are distinct. Empty upload, header-only batches, filtered-empty results, loading, missing resources, permission failures and revision mismatch have explicit states. The desktop execution panel is sticky; mobile layout uses a normal-flow panel and horizontal table scrolling. Shared modal keyboard dismissal/focus restoration is preserved.

## Changed files

- `frontend/app/imports/page.tsx`: route integration.
- `frontend/app/imports/imports.css`: scoped responsive Screen 5 styles.
- `frontend/lib/api.ts`: typed staged API functions and error details; compatible optional abort signals for history.
- `frontend/lib/staged-imports.ts`: status helpers and staged error presentation.
- `frontend/types/staged-import.ts`: concrete backend request/response contracts.
- `frontend/components/imports/use-staged-review.ts`: review state and revision-safe mutations.
- `frontend/components/imports/staged-import-workspace.tsx`: shared application shell and orchestration.
- `frontend/components/imports/staged-uploader.tsx`: file selection/drop and real upload.
- `frontend/components/imports/staged-summary.tsx`: counts, metadata and receipt.
- `frontend/components/imports/staged-toolbar.tsx`: supported server filters.
- `frontend/components/imports/staged-rows-table.tsx`: source rows, issues and actions.
- `frontend/components/imports/staged-edit-dialog.tsx`: original/current values and manual correction.
- `frontend/components/imports/staged-pagination.tsx`: server pagination with explicit accessible labels.
- `frontend/components/imports/staged-batches.tsx`: resume/status-filtered batch list.
- `frontend/components/imports/staged-commit-panel.tsx`: permission/state-aware execution controls.
- `frontend/components/imports/staged-audit-dialog.tsx`: lazy paginated action history.
- `frontend/components/imports/import-history-dialog.tsx`: existing import/error history.
- `docs/frontend-staged-import-review.md`: this implementation and verification report.

## Verification

Completed on October 4, 2026:

- `npm.cmd run typecheck`: passed.
- `npm.cmd run build`: passed, including all existing routes.
- Targeted `npx.cmd --yes prettier --write ...`: formatted changed files.
- `git diff --check`: passed before commit.
- No lint or frontend test script is configured in `frontend/package.json`.
- `python -m alembic upgrade head`: passed against an isolated PostgreSQL 18 test cluster at port 55439 with `20261004_0008_staged_csv_import` applied. The normal development database/configuration was not modified.
- Real Chromium via `npx.cmd --yes --package @playwright/cli playwright-cli -s=screen5 run-code --filename <external QA script>`: live FastAPI/PostgreSQL checks passed for malformed/oversized/mixed/valid/header-only upload, supported filters, page two and page sizes, still-invalid/valid corrections, exact string preservation, duplicate creation/resolution and sibling revalidation, exclusion/restoration, stale batch and row revisions, export/audit, commit-time revalidation failure, successful commit, idempotent retry, cancellation and all three roles.
- Live 40-row fixture created no students during staging and persisted exactly 38 included students on commit. Commit receipt: `6e966133-d678-4868-b204-6413837953ed` in the disposable database. No uncaught browser exceptions occurred.
- Additional frontend-only error injection covered commit conflict/busy/stale, 422 correction details, missing row, 403 permission loss and 401 download/session clearing. Successful follow-up GET requests used the actual backend. These checks do not claim to reproduce database locking races.
- Responsive screenshots and overflow checks passed at 1440, 1024 and 390 pixels. Mobile editor keyboard focus restoration passed. Existing dashboard, predictions, students and warnings routes passed browser smoke checks.
- Python CSV inspection verified the actual export: official 34-column order, 39 rows included at export time, excluded existing student absent, and the exact string ` 1.50 ` preserved. A second row was excluded afterward before the 38-row commit.

QA scripts, CSV fixtures, screenshots and disposable PostgreSQL data are stored outside the repository under `C:\Users\Administrator\.codex\visualizations\2026\10\04\01a10807-3636-73f2-9cc4-cfeab7fe8e2e\screen5` (database under adjacent `staged-import-check`). Test users and records were confined to this isolated database.

No known implementation blockers remain. The existing `next start` advisory about `output: standalone` was observed during QA; the server ran successfully. Deployment can use the existing standalone server output. Apply the staged migration to the intended development/deployment database before using this screen there.
