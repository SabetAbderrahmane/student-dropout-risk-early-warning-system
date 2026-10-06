# Workspace usability and onboarding

The workspace uses a consistent set of rounded SVG icons, navigation grouped into Records & insights and Student support, and clearer text and control sizing. Unimplemented administration placeholders have been removed. The overview's **Where to start** links show real pending reviews, cases requiring action, and due or overdue follow-ups from the existing overview response.

## Using the guide

After signing in for the first time in a browser, choose **Take the guided tour** or **Explore on my own**. The tour visits Overview, Students, Data import, Risk predictions, Warning triage, Interventions, and Follow-ups. Each step explains the workflow, practical tasks, a useful distinction, and the signed-in account's permissions.

Use **Next**, **Back**, or the progress markers to move between workspaces. **Explore this screen** closes the guide so the user can work in that screen. The tour navigates to actual routes; it does not import records, generate predictions, review warnings, or modify cases. **Finish tour**, Escape, the close button, and clicking outside the dialog all dismiss it.

The header's **Help & tour** button and sidebar's **Find your way around** button reopen help. Help offers a walkthrough for the current screen, a specific workspace, or the full tour. On small screens the header help button displays a question-mark icon with an accessible label.

Academic advisors receive six steps and do not see the restricted Data import link. Advice distinguishes institution-wide totals from assigned work, read-only academic data from editable records, warning review ownership, and follow-up completion from intervention completion. System administrators can inspect academic records and receive guidance about which academic roles perform the actions described.

## Implementation

- `frontend/components/dashboard/icon.tsx`: shared 24-unit SVG grid and stroke weight, distinct navigation icons, decorative SVG semantics.
- `frontend/lib/workspace-guide.ts`: shared navigation/guide definitions and role advice.
- `frontend/components/guide/guide-provider.tsx`: persistent root provider and native modal dialog, route navigation, keyboard focus, scrolling cleanup, and welcome/help/tour states.
- `frontend/components/layout/`: help entry points, task groups, role-aware navigation, and mobile navigation keyboard containment.
- `frontend/components/dashboard/next-actions.tsx`: links backed by live overview counts.
- `frontend/app/usability.css`: shared legibility, control sizing, navigation and guide layouts using the existing light/dark semantic colors.

Guide dismissal/completion is stored per user in this browser under `academic-workspace-guide-v1:<user-id>`. Replaying help preserves completion. When persistent storage is blocked, a session fallback prevents repeated prompts during navigation. Onboarding preferences are not synchronized between browsers. No additional dependency, API, database migration, or authorization rule is introduced.

## Validation

- `npm run typecheck` and `npm run build` pass.
- Browser walkthrough covers all seven actual routes, Back/Next/progress navigation, finish/skip persistence across refresh and sign-in, contextual help, and per-user role filtering.
- Native dialogs contain keyboard focus, support Escape, and restore scrolling. Mobile navigation supports reverse Tab and handing off to help without unlocking the page underneath.
- All seven screens avoid page overflow at 390, 768, and 1024 pixels; overview and guide also fit a 320-pixel viewport. Representative populated screens and guide states were visually reviewed in both light and dark themes at desktop and mobile sizes.
- Advisor ownership and system administrator academic permissions are explained. Persistent-storage failure does not block dismissal or replay.
- Browser runs report no page exceptions or hydration mismatches. The built application was also checked across all seven populated tour routes with a temporary production server on port 3101; a browser-only relay of real API responses kept the backend's existing port-3000 CORS configuration unchanged.
- Read-only database verification retained 122 students, 218 predictions, 155 warnings, 52 interventions, 104 follow-ups, 104 notes, and four staged batches.

Local browser evidence is in the ignored `output/playwright/usability-*.png` and QA result files. Design review scores: specificity 4, coherence 4, hierarchy 4, responsiveness 3, interaction 4, motion 3 (deliberately static), accessibility 3, technical finish 4. Dense tables retain their own scrolling on narrow screens.
