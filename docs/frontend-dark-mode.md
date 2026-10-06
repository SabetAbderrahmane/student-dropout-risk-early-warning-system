# Frontend theme implementation and verification

Implemented on `codex/frontend-dark-mode`, starting at integration commit
`2dfb37becf133a918130647070b94d38a940c5ec`. The nine existing implementation
commits are preserved. Backend files, API contracts, authentication, prediction
and casework behavior are unchanged. No merge, rebase, force push, or PR.

## Architecture

- `frontend/lib/theme.ts` defines Light / Dark / System, validation, the media
  query, and a small static initialization script.
- `frontend/app/layout.tsx` installs the script in the document head before
  body paint and mounts the client theme provider. The bootstrap sets only
  `html[data-theme]`. Hydration suppression is limited to that HTML element;
  the control's initial render is stable on the server and client.
- `frontend/components/theme/theme-provider.tsx` resolves System through
  `prefers-color-scheme`, listens for OS changes, synchronizes other tabs, and
  updates all controls. Explicit Light/Dark overrides OS changes.
- Browser localStorage key: `academic-early-warning-theme`, value `light`,
  `dark`, or `system`. Missing/invalid preferences default to System. Blocked
  storage falls back to a working session-only choice. No backend persistence.
- `frontend/components/theme/theme-control.tsx` is a labeled native select in
  the shared header, login, and landing page. It enables after initialization
  and shows the selected preference, including System.
- `frontend/app/theme.css` contains the central semantic palette, native
  `color-scheme`, focus, placeholders, selection, scrollbars, and compact
  control styling. A media-query palette fallback supports dark OS preference
  when JavaScript is disabled. Screen styles share tokens rather than separate
  light/dark copies. No dependency was added.

## Tokens and color audit

Surface roles: background/auth background, surface, elevated, muted, hover,
selected, sidebar, header. Text roles: primary, secondary, muted, on-accent.
Borders: standard, subtle, strong. Accent roles separate readable foreground
links from filled buttons, hover, active navigation, and focus/halo.

Success, warning, danger, info, neutral, and analysis have theme-specific
foreground/background/border palettes. HIGH/P1/OVERDUE/ACTION_REQUIRED stay red;
MEDIUM/P2/DUE/review stay amber; LOW/COMPLETED/ready stay green; P3/scheduled
and active workflow states use blue. Labels remain alongside colors.
Chart roles cover grid, line, created, neutral, in-progress, completed, risk,
and analysis. Backdrops, shadows, and the existing subtle auth gradients use
tokens too. SVG chart data and geometry were preserved; UI icons already use
`currentColor`.

An audit of CSS, TS, TSX, and SVG source found no screen-specific literal UI
colors remaining. Intentional literal colors are the palettes in `theme.css`
and the unchanged favicon (`app/icon.svg`): navy `#022448` tile and white
shield. It is a self-contained fixed brand mark readable in both themes.
`transparent` and `currentColor` remain intentional CSS values. Native date,
file, select, checkbox, and meter details follow the browser's color scheme.

## Changed files

- New: `frontend/app/theme.css`, `frontend/lib/theme.ts`,
  `frontend/components/theme/theme-provider.tsx`,
  `frontend/components/theme/theme-control.tsx`, this report.
- Bootstrap/control integration: `frontend/app/layout.tsx`,
  `frontend/app/login/page.tsx`, `frontend/app/page.tsx`,
  `frontend/components/layout/app-header.tsx`.
- Palettes: `frontend/app/globals.css`,
  `frontend/app/dashboard/dashboard.css`, `frontend/app/students/students.css`,
  `frontend/app/students/dossier.css`, `frontend/app/warnings/warnings.css`,
  `frontend/app/predictions/predictions.css`, `frontend/app/imports/imports.css`,
  `frontend/app/interventions/casework.css`,
  `frontend/app/follow-ups/follow-ups.css`.
- SVG colors: `frontend/components/dashboard/warning-activity-chart.tsx`,
  `frontend/components/dashboard/intervention-summary.tsx`,
  `frontend/components/warnings/prediction-history-chart.tsx`.

The only responsive adjustments hide the header's long identity text at narrow
widths while retaining the avatar, and wrap full-precision prediction thresholds
inside their existing cards. No values or workflow behavior were changed.

## Browser verification

Chromium with the actual frontend and FastAPI application, an isolated in-memory
test database, real JWT roles, populated student/warning/case/follow-up records,
and the existing model artifact. CSV edits used the official 34-column schema.
No production database was used. Local screenshots and temporary QA scripts
are under ignored `output/playwright/`; fixture setup is outside the repository.

Both Light and Dark were exercised and screenshots inspected on `/`, `/login`,
`/dashboard`, `/students`, `/warnings`, `/predictions`, `/imports`,
`/students/{id}`, `/interventions`, and `/follow-ups`.

Verified student profile and creation dialogs; warning history/review and
intervention creation; model and prediction details; all dossier tabs and
academic editing; case detail/edit/create; follow-up selection, editing,
completion with next-follow-up fields, and scheduling; staged invalid/included/
excluded rows, original and edited values, correction, ready state, audit and
import history dialogs, commit/cancel confirmations, and committed/cancelled
read-only batches. Charts included real model importance, confusion
matrix, dashboard activity/status, explanation bars, and prediction history.

Behavior checks passed: first-time System with light OS; System with dark OS;
live OS changes; explicit overrides; refresh persistence; navigation persistence;
cross-tab synchronization; storage blocked; keyboard focus; no-JavaScript dark
OS fallback. With application JavaScript bundles deliberately blocked and a
saved Dark preference, the head bootstrap still set the dark root attribute
and dark auth surface before React hydration. Normal route checks found no
hydration mismatch or runtime exception.

Visible text contrast was measured against resolved ancestor surfaces on all
routes in both themes. After adjusting the shared muted light token, the scan
found no text below 4.5:1 (3:1 for large text). This scan excludes SVG text,
disabled/transparent text, pseudo-elements, and browser popups; those received
visual review rather than a claim of exhaustive WCAG certification. Focus
rings remain visible. Disabled controls remain intentionally subdued.

At 390px and 1024px all nine application/login routes passed in both themes
with no document-level horizontal overflow, and the theme control fit the
header. A mobile student dialog fit the viewport. Wide data tables retain
their existing internal horizontal scrolling.

## Checks and limits

- `npm run typecheck`: passed.
- `npm run build`: passed.
- No frontend lint or test script is configured. Browser verification supplies
  the behavior/visual checks; no new testing framework was added.
- Native picker/popup appearance varies by browser and OS. Chromium was tested;
  Safari/Firefox and forced-colors modes were not independently exercised.
- The app currently permits the inline bootstrap. A future restrictive CSP
  must allow it via a hash or nonce to preserve stored-preference pre-paint
  initialization. The CSS fallback still follows System if scripts are blocked.
- Backend code and local/remote `main` were not modified.
