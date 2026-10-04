# Screen 2: Student Registry

The existing Next.js `/students` route now uses the Phase 8 registry read model.
Screen 1's dashboard remains intact on `feat/frontend-dashboard-overview`.
The supplied `screen 2.zip` was inspected as source/design reference only; its
Vite application, mock students, advisor assignment logic, and fabricated counts
were not integrated.

## Data and interactions

- One `GET /api/v1/student-registry` request per query change. No per-row fetches.
- Server-driven search, risk/warning/intervention/readiness filters, sorting,
  and pagination. Search debounces for 300 ms and supports name/student ID only.
- Filter, sort, and page-size changes reset page to 1. Page sizes: 25, 50, 100.
- Counts and page metadata come directly from the response. `updated_at` sorts
  student record updates; it is labeled separately from displayed last activity.
- Superseded registry/profile requests are aborted.
- Profile drawer fetches `/students/{id}/profile` only when opened, with academic
  records, readiness, risk, casework, follow-ups, and history. Full record links
  retain the existing student detail/edit workflow.
- Academic admins can create students through the existing POST endpoint.
  CSV import opens the existing import screen for permitted admin roles.
- Session storage, Bearer headers, shared API error parsing, and configuration
  remain in the existing API/auth modules. A 401 clears the session and redirects.
- Unsupported prototype cohort/term/enrollment filters, email actions, export,
  bulk selection/assignment, and invented KPI numbers are omitted.

## Validation

- `npm run typecheck` and production build.
- Browser checks with temporary intercepted API fixtures, stored outside the
  repository: desktop (1440 px), tablet (1024 px), and mobile (390 px); filter
  mappings; page resets; ascending/descending sorting; page sizes 25/50/100;
  debounced search; density; drawer sections and Escape dismissal; duplicate
  creation error; empty/error/retry states; advisor permissions; 401/session expiry.
- No live database integration was exercised during this change.

The pasted request ends at “Preserve the strong table”; remaining visual choices
follow the ZIP reference and existing backend contracts.
