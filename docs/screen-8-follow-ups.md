# Screen 8 — Follow-Ups & Outcomes

Implemented on `codex/frontend-follow-ups-outcomes`. Screen 7 was preserved first in its own dependency commit, `123d31b`. No backend source or database migration was changed. The ZIP was used only as a visual reference; the pasted request defines the implementation scope.

## Workspace and workflows

`/follow-ups` uses the existing authenticated Next.js shell. Its compact queue and selected-record panel display persisted API records. The sidebar now opens this route. Student links open `/students/{student_id}`; intervention and case-note links open `/interventions?intervention_id={intervention_id}` and its existing case dialog.

Supported URL context: `student_id`, `intervention_id`, and `follow_up_id`. A selected record survives refresh. `intervention_id=...&schedule=1` opens scheduling with real intervention context. Queue filters are session UI state and reset to their defaults on a full reload; the URL context survives.

Scheduling selects a real, paginated/searchable intervention and loads its detail before exposing the form. Cancelled interventions are ineligible. Completed interventions remain eligible because the existing service permits them. The student derives from the intervention. Submission sends a timezone-aware `scheduled_for`, the actual method enum, purpose, and advisor UUID.

Reschedule / Edit PATCHes the selected persisted record's date, method, purpose, and authorized assignee. Completion sends one of the six actual outcome enums and required notes. The optional next date is sent in the same completion request: the backend creates the next follow-up atomically, copying the intervention, student, method, purpose, and assignee. No browser object is appended as a substitute. Even `INTERVENTION_COMPLETED` as a follow-up outcome does not complete the intervention. Cancellation uses the existing dedicated endpoint with a required reason. Completed and cancelled records are historical/read-only.

Every successful write refetches the queue, four totals, selected detail/intervention, and related follow-up history. UI locks prevent overlapping submissions. No automatic selection or fabricated follow-up history is generated.

## Actual API integration

All paths below have the `/api/v1` prefix and use the shared authenticated API utility.

| Method | Route | Use |
| --- | --- | --- |
| GET | `/follow-ups` | Queue, search, filters, pagination, four global totals |
| GET | `/follow-ups/{follow_up_id}` | Selected persisted detail |
| GET | `/interventions` | Paginated intervention picker |
| GET | `/interventions/{intervention_id}` | Scheduling eligibility and dual-ownership context |
| POST | `/interventions/{intervention_id}/follow-ups` | Schedule |
| GET | `/interventions/{intervention_id}/follow-ups` | Paginated related persisted records |
| PATCH | `/follow-ups/{follow_up_id}` | Reschedule/edit/reassign |
| POST | `/follow-ups/{follow_up_id}/complete` | Outcome, notes, optional next date |
| POST | `/follow-ups/{follow_up_id}/cancel` | Cancellation reason |

Global list parameters: `page`, `page_size`, `status`, `assigned_to`, `student_id`, `intervention_id`, `from`, `to`, `search`, `sort`, `order`. Status tabs send the backend effective statuses directly. Assigned to Me sends the authenticated user's UUID. Sort supports scheduled/created/updated time and student number. Page sizes are 10/25/50/100.

Date filters send local date boundaries converted to ISO instants, including the end date through its final millisecond. Upcoming 7 Days sends today's local midnight through the end of the sixth following day with `status=SCHEDULED`. Displayed timestamps use local time. DUE and OVERDUE remain the backend's UTC-day classification; the frontend never derives or persists these states.

Four summary cards request `page_size=1` for OVERDUE, DUE, SCHEDULED, and COMPLETED and display each response's `total`. They are explicitly institution-wide and independent of queue filters. No page-length count is mislabeled as a global total. Failed totals show unavailable markers, with retry.

## Permissions and recovery

Academic admins can schedule and change follow-ups. Academic advisors can schedule only on their own interventions and assign themselves; changes require ownership of both the follow-up and its intervention. System admins can read only. These UI rules mirror the existing service; the backend remains the final authority.

401 clears the JWT and redirects to login. 403/404/409 display the backend error and refresh authoritative state, including removal of stale mutation controls. 422 details attach to the corresponding fields with accessible invalid/error descriptions. A backend-invalid assignee also maps to its field. Request failures never produce a success notice.

Aborted/stale reads cannot overwrite newer queries. Refresh errors retain the last successful response for the same query, clearly label it, and disable stale actions. They never show a previous query's results as a new filter's data. Existing forms retain their draft during read failures and failed writes; retry restores access after the context loads successfully.

## Prototype scope omitted

No prototype mock records, StudentFollowUp type, local persistence, fake KPI/SLA/attendance/milestone data, GPA/cohort/academic-plan details, invented advisors, mock audit actors, communication sending, calendar/export, LMS/SIS integration, FERPA/legal claims, or timer-based state transitions were copied into the production workspace. Method filtering is absent because the global endpoint does not support it. Only the five actual contact methods are offered.

## Verification

Browser verification used the actual FastAPI application and services with an isolated in-memory SQLite QA database, actual JWTs, 30 seeded follow-ups across all five effective states, multiple advisors, academic admin, and system admin. No production database was used. Temporary fixtures and Playwright artifacts are outside the committed feature.

| Requested manual check | Result |
| --- | --- |
| 1. Global list | Passed; real API records and pagination totals |
| 2. Pagination | Passed; page 2 and 25-row size requested server-side |
| 3. Search | Passed; debounced server search resets page 1 |
| 4. Assigned to Me | Passed; authenticated UUID filter |
| 5–8. Scheduled, Due, Overdue, Completed | Passed; every returned item's backend effective status checked |
| 9. Date range / upcoming | Passed; inclusive one-day range and Upcoming 7 Days query/results |
| 10. Create from real intervention | Passed; browser schedule POST and persisted reload |
| 11. Invalid intervention creation | Passed; cancelled-case modal blocks creation, actual POST returns 409; foreign advisor case returns 403 |
| 12–13. Reschedule / method | Passed; date and ONLINE_MEETING persisted via PATCH |
| 14. Assignee change | Passed; admin reassigned to a second real advisor UUID |
| 15. Outcome and notes | Passed; PROGRESS_OBSERVED completion without next date |
| 16. Optional next follow-up | Passed; separate scheduled record persisted; original completed; intervention stayed PLANNED after INTERVENTION_COMPLETED outcome |
| 17. Completed read-only | Passed; controls removed after reload |
| 18. Cancelled display | Passed; dedicated cancel POST, persisted reason, historical state |
| 19. Advisor RBAC | Passed; neither case-only nor follow-up-only ownership permits changes |
| 20. Admin permissions | Passed; scheduling, completion, reassignment; system admin read-only |
| 21. 403 | Passed; real stale-assignment write rejected, error displayed, refreshed controls removed |
| 22. 404 | Passed; nonexistent UUID detail shows error without fake data |
| 23. 409 | Passed; externally completed record rejects stale UI completion, refreshes persisted outcome |
| 24. 422 | Passed; blank purpose returned real backend validation beside purpose field, then corrected submission succeeded |
| 25. Student navigation | Passed; linked real dossier loaded |
| 26. Intervention navigation | Passed; real case dialog opened with linked follow-ups and notes |
| 27. Direct URL refresh | Passed; selected record preserved |
| 28. Empty results | Passed; server total 0 and factual empty state |
| 29. No mock data | Passed; source scan and browser API-backed records; totals independent of empty search |

Additional browser checks passed: server sorting/order; 401 invalid-session redirect; injected 503 queue/detail/write recovery; retained unsaved draft; unavailable count markers; keyboard Enter selection with detail focus; modal Escape with trigger-focus restoration; no horizontal overflow at 1024px or 390px. Screenshots were visually inspected at desktop, tablet, and mobile widths. Browser console errors corresponded to deliberately exercised HTTP failures, with no application runtime exception observed. A few QA script assertions initially used the wrong locator/heading text and were corrected; these were harness errors, not product defects.

Configured checks: `npm run typecheck`, `npm run build`, and `python -m pytest tests/api/test_casework.py tests/api/test_permissions.py -q` (16 passed). There is no configured frontend lint or test script. `git diff --check` verifies whitespace. Final build/typecheck were repeated after the last feature changes.

## Limits and Git scope

There is no advisor-directory endpoint in this integration. Admin assignee entry uses an actual active advisor UUID, validated by the backend; no fabricated directory is shown. Related history is five records per page. Totals are four independent live responses, not a single atomic statistics snapshot. Reads refresh on navigation, filters, manual refresh, and writes; there is no polling timer. Browser checks ran against an isolated service rather than a deployed production environment.

Changed files:

- `frontend/app/follow-ups/page.tsx`, `follow-ups.css`
- `frontend/components/follow-ups/follow-ups-workspace.tsx`, `follow-up-metrics.tsx`, `follow-up-filters.tsx`, `follow-up-queue.tsx`, `follow-up-detail-panel.tsx`, `follow-up-form.tsx`, `schedule-follow-up-modal.tsx`, `use-follow-ups.ts`, `use-follow-up-resource.ts`
- `frontend/lib/follow-ups.ts`, `frontend/lib/api.ts`, `frontend/types/casework.ts`
- `frontend/components/layout/app-sidebar.tsx`
- `frontend/components/casework/casework-workspace.tsx`
- `frontend/AGENTS.md`, `frontend/CLAUDE.md` (generated by this installed Next.js version and retained per its instructions)
- `docs/screen-8-follow-ups.md`

`main` was not checked out, merged into, or modified. Its commit remains `c2487d5948d07f4a48bff07798250cda47bf25bb`. The final Screen 8 commit hash is reported in the completion message.
