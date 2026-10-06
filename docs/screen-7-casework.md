# Screen 7 — Academic Interventions & Casework

Open `/interventions` through the shared navigation. Follow-Ups links to the follow-up section of the same workspace. Student identities link to the established Screen 6 route, `/students/{id}`.

## Data and contracts

- Intervention search, filters, sort and pagination use `GET /api/v1/interventions`. Search covers student name, student number and intervention title, as defined by the repository. Changing search or filters resets to page 1; stale requests are aborted.
- Supported sort values: `urgency`, `status`, `priority`, `updated_at`, `created_at`, `start_date`, `target_date`, `student_number`. Urgency uses the backend's fixed ordering; the order selector is disabled for that sort.
- Status, priority and intervention type use the existing backend enums. Assignee filtering offers all advisors or the authenticated user's actual ID. No advisor directory is fabricated.
- Optional `student_id` and `warning_id` query parameters provide navigation context. Clear filters removes this context.
- Cards request authoritative list totals independently of table filters. Active is the sum of PLANNED, IN_PROGRESS and ACTION_REQUIRED totals. Follow-up attention is the sum of DUE and OVERDUE totals. Failed totals display an unavailable value and a retry action. These separate requests are not an atomic snapshot.
- Follow-up tabs use the paginated `GET /api/v1/follow-ups` endpoint. Effective statuses are returned by the backend. Scheduled/completed/cancelled tabs also expose future and historical contacts.
- The case table omits risk scores and next-follow-up fields because the intervention list does not provide them. The detail endpoint supplies linked follow-ups without inventing a read model or fetching every intervention.

## Actions and authorization

The creation drawer searches and paginates confirmed warnings. Advisors see warnings assigned to them; academic administrators see confirmed warnings across assignments. Selection reloads warning detail before presenting the form. Creation uses its actual student/warning IDs, an explicit priority selection, backend support type, title, description, advisor ID and dates. Administrators can enter an actual advisor ID when needed; the backend validates role and account activity.

Shared Screen 6 case/detail forms provide PATCH editing and status transitions, POST completion/cancellation, append-only notes, and scheduling contacts. Linked follow-ups open the existing detail form for editing, completion and cancellation. Successful mutations refetch the current case page, metrics, follow-up page and selected detail. Cancellation retains historical records.

System administrators have read access. Academic administrators can perform casework actions. Advisors must own the case; follow-up actions additionally require ownership of the follow-up. Screen 7 loads the linked intervention to check case ownership before enabling follow-up writes. FastAPI remains authoritative and enforces permissions and state transitions. Expired sessions redirect to login; other failures remain visible with retry controls.

The prototype contributes only layout ideas. No prototype shell, data store, scheduler, notifications, risk-based priority algorithm, session counters, adherence statistics, outreach, FERPA checkbox or support-liaison integration is installed.

## Validation

- `cd frontend; npm run typecheck`
- `cd frontend; npm run build`
- `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/api/test_casework.py tests/api/test_permissions.py -q` — 16 passed.
- Browser checks against the actual FastAPI routes and an isolated in-memory QA database: JWT login, backend pagination, debounced search resetting pagination, persisted creation with explicitly selected priority, attributed note creation, linked follow-up completion, queue/count refresh, offline error/retry recovery, and rendering at 1440px, 900px and 390px. Mobile document width equaled viewport width. Normal operation produced no application console errors; Next.js emitted CSS preload warnings during navigation. Deliberate offline checks produced the expected failed network requests.

Browser QA data and credentials are confined to a temporary test server and are not part of the application or its production database.
