# Screen 6 — Student Dossier

Implemented on `codex/frontend-student-dossier`, starting from Screen 5 commit `000c97a421adbfcebcaaed32a9614943670f9d7c`. The full dossier uses the existing `/students/[id]` route and existing registry drawer link. Main was not modified; no backend, migration, dependency or shared navigation changes were made.

## Design and read model

The provided `D:\screen 6.zip` was inspected in place as a design reference. Its identity header, navy/lavender palette, section navigation and vertical case timeline were adapted to the application’s existing layout and modal components. The prototype App, mock students, fake registry and local timeline state were not imported.

`GET /api/v1/students/{student_id}/profile` is the primary dossier source. Its student, admission, semester_one, prediction_readiness, latest_prediction, prediction_history, active_warning, warning_history, interventions, follow_ups and timeline sections all have rendered views. No profile section is assembled from invented records. Loading, unavailable and empty states distinguish missing records from a zero numeric value.

The page provides Overview, Academic record, Predictions, Warnings, Interventions, Follow-ups and History sections. The overview summarizes actual saved data; the full history uses the backend timeline. Prediction explanations display the factors as recorded, with the actual model version and prediction time. There are no weekly scores, fabricated SHAP values, course-level telemetry or causal claims.

Desktop uses paired dossier sections; narrow screens place readiness and warnings before the longer history. Navigation scrolls within its own container. Modals reuse native dialog keyboard behavior, focus restoration and submission guards. No motion or UI dependencies were added.

## Actions and permissions

- Academic Admin: edit core/demographic source fields, admission and semester data; run an individual prediction; assign/unassign warning advisors; create and manage interventions/follow-ups.
- Academic Advisor: read dossier; review only warnings assigned to that advisor; create cases from assigned confirmed warnings; manage only assigned interventions. Follow-up writes also require ownership of the linked case and follow-up.
- System Admin: read-only dossier and case/follow-up details, without write controls.

Warning review remains Advisor-only, as required by the existing API. Confirmed warnings with assigned advisors permit intervention creation. Assignment/reassignment uses an existing active advisor’s UUID because there is no advisor-directory endpoint; the backend validates it. New interventions initially use the warning’s advisor; Academic Admin may reassign through intervention editing.

Intervention actions include editing, allowed status transitions, notes, scheduling, completion with outcome/notes, and cancellation with reason. Follow-ups support editing, completion with outcome/notes and an optional next checkpoint, and cancellation. Local appointment values are converted to ISO timestamps including a timezone offset. Contact method records the method only; no message or email is sent.

Completed/cancelled intervention fields have no edit/status/complete/cancel controls. The backend still permits adding notes to terminal cases and scheduling follow-ups on completed cases; these supported actions remain available to authorized owners. Cancelled cases cannot receive follow-ups. Completed/cancelled follow-ups are read-only.

Successful mutations refetch the profile and affected detail rather than constructing local timeline events. Failed 403/404/409 mutations also reload the relevant detail, so a case changed by another user becomes appropriately read-only inside the open dialog. Rejected mutations are never automatically replayed. A 403 removes write controls; a 401 clears the existing session and redirects to login. Validation messages preserve backend error details.

The previous core/academic editing capability is retained and extended to the existing prediction feature fields. Optional source values are preserved on saves. New missing-record forms start blank, with no synthesized academic defaults.

## Integrated routes

All API paths are beneath the existing `API_BASE_URL`, controlled by `NEXT_PUBLIC_API_URL`, and use the existing sessionStorage JWT.

- `GET /students/{id}/profile` and existing `GET /auth/me`.
- Existing `PATCH /students/{id}`, `PUT /students/{id}/admission`, `PUT /students/{id}/semester-1`.
- `POST /students/{id}/predictions`.
- `PATCH /warnings/{id}/assignment`, existing `POST /warnings/{id}/reviews`.
- Existing `POST /interventions`; `GET/PATCH /interventions/{id}`.
- `POST /interventions/{id}/notes`, `/complete`, `/cancel`, `/follow-ups`.
- `GET/PATCH /follow-ups/{id}`, `POST /follow-ups/{id}/complete`, `/cancel`.

Unsupported prototype fields and features were omitted: contact/residence/emergency information, proxy authorization, balances/aid/holds/grants, individual courses/instructors/exams/attendance, Canvas/LMS features, weekly telemetry, faculty review and fake compliance/model identifiers. No PDF export or messaging control is presented because those contracts do not exist.

## Changed files

- `frontend/app/students/[id]/page.tsx`: existing detail route now renders the dossier.
- `frontend/app/students/dossier.css`: scoped responsive dossier styling.
- `frontend/lib/api.ts`: typed wrappers for existing prediction/assignment/casework APIs.
- `frontend/types/casework.ts`: intervention, note, follow-up and mutation types matching FastAPI schemas.
- `frontend/types/student.ts`: existing source types now include the backend's demographic and optional academic prediction fields.
- `frontend/components/dossier/use-dossier.ts`: authentication, authoritative profile reads, guarded mutations and failure recovery.
- `frontend/components/dossier/student-dossier.tsx`: shared shell, section navigation, role-aware actions and dialogs.
- `frontend/components/dossier/dossier-overview.tsx`: overview composition.
- `frontend/components/dossier/dossier-records.tsx`: source values, readiness, predictions, warning reviews and timeline.
- `frontend/components/dossier/dossier-form.tsx`: accessible source/action forms and duplicate-submit guard.
- `frontend/components/dossier/academic-editor.tsx`: blank/preserved source forms using existing academic contracts.
- `frontend/components/dossier/case-detail.tsx`: lazy intervention detail, notes and lifecycle actions.
- `frontend/components/dossier/follow-up-detail.tsx`: lazy follow-up detail and lifecycle actions.
- `docs/frontend-student-dossier.md`: this report.

## Verification

Executed October 4, 2026:

- `npm.cmd run typecheck` — passed.
- `npm.cmd run build` — passed, including `/students/[id]` and Screens 1–5.
- Targeted `npx.cmd --yes prettier --write ...` and `git diff --check` — formatting/whitespace verification.
- No lint or frontend test scripts are configured in `frontend/package.json`.
- `python -m alembic upgrade head` — passed in isolated PostgreSQL 18 at port 55439, including existing migrations 0007/0008. Normal database/configuration unchanged.
- FastAPI generated OpenAPI schema verified the profile response as `StudentProfile`; read-model/casework/student/prediction/warning schemas and service permissions were inspected.
- `python -m pytest tests/api/test_read_models.py tests/api/test_casework.py tests/api/test_students.py tests/api/test_predictions.py tests/api/test_warnings.py -q` — **64 passed** in 32.81 seconds. These existing API tests use their SQLite fixtures; backend code was unchanged.
- Real Chromium through Playwright CLI against FastAPI/PostgreSQL — passed: registry-to-dossier navigation; full/empty profiles; exact source preservation on core/admission/semester saves; real 422 validation feedback; actual registered-model prediction; warning assignment and assigned-advisor review; intervention creation/start/edit/status transitions/note/completion; follow-up scheduling/edit/completion with a next checkpoint; intervention and follow-up cancellation; terminal views; System Admin read-only and unrelated Advisor ownership restrictions.
- A concurrently cancelled intervention produced a real backend 409; the open dialog reloaded the cancellation reason and removed edit controls. No write was replayed.
- Frontend-only response injection covered profile 401/session clearing and 403/hidden data. A held real profile request verified the loading state. A nonexistent UUID verified the real 404 state.
- Responsive screenshots and overflow checks at 1440, 1024 and 390 pixels; mobile academic editor and Escape/focus restoration — passed.
- Production-build browser checks repeated the three viewports and mobile editor; injected model-unavailable and network errors showed visible feedback, disabled duplicate prediction submission, and successful manual retry. No development overlay is present in the production screenshots.
- Existing dashboard, registry, predictions, warnings and staged-import routes passed browser smoke checks. No uncaught browser exceptions were observed.

Scripts, OpenAPI output, screenshots and disposable fixtures are outside the repository under `C:\Users\Administrator\.codex\visualizations\2026\10\04\01a10807-3636-73f2-9cc4-cfeab7fe8e2e\screen6`. QA student `44d3d04a-3f23-4b58-9359-61d3707ba348` and case `0739316c-25b4-4c09-90dc-3154f826ae05` exist only in the isolated test database. Predictions used the existing registered Logistic Regression artifact, with no substitute model.

No known implementation blockers remain. Existing deployment/database prerequisites still apply. The existing `next start` standalone-output advisory may appear when using that command; deployment can use the standalone server output.
