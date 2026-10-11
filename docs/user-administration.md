# Phase A2: secure user administration

## First-use workflow

Apply `alembic upgrade head` before starting the backend. Prepare and verify the
approved A1 model as described in [model deployment](ml-model-deployment.md).
Temporarily provide all four `BOOTSTRAP_ADMIN_*` variables, with a password of
at least 12 characters, and run `python -m app.db.init_db` (Compose runs this
existing bootstrap command during initialization). Remove the bootstrap password
from the environment after creation. Bootstrap is idempotent and does not change
an existing account's password or permissions.

The new System Admin signs in and replaces the temporary password at
`/change-password`. **Administration → Users** (`/admin/users`) provides account
creation, profile editing, role changes, activation/deactivation, and password
reset. Only System Admins can manage accounts. The three fixed roles are
`SYSTEM_ADMIN`, `ACADEMIC_ADMIN`, and `ACADEMIC_ADVISOR`; an additional System Admin
can be provisioned for continuity. There is no public registration, custom-role
creation, invitation-email service, user deletion, or bulk reassignment.

Create the Academic Admin and Advisor accounts with temporary credentials, then
share them using the institution's secure channel. Every owner must replace
their temporary password before protected application use. The Academic Admin
can manage students and use the existing warning/intervention assignment forms;
those forms now offer a searchable, paginated active-advisor directory. Advisors
retain the existing warning review and casework permissions.

## API contract

All paths below are relative to `/api/v1`. Supply the existing Bearer JWT.

| Method | Path | Access and input |
| --- | --- | --- |
| GET | `/users` | System Admin; `page`, `page_size` (1–100), `search`, fixed `role`, `is_active` |
| POST | `/users` | System Admin; `username`, `email`, `full_name`, `role`, `initial_password`; returns 201 |
| GET | `/users/{id}` | System Admin; account details |
| PATCH | `/users/{id}` | System Admin; one or more of `username`, `email`, `full_name`, `role` |
| POST | `/users/{id}/activate` | System Admin; no body; idempotent |
| POST | `/users/{id}/deactivate` | System Admin; no body; safeguards below |
| POST | `/users/{id}/reset-password` | System Admin; `temporary_password` |
| GET | `/users/advisors` | All three authenticated roles after any required password change; active Academic Advisors only; `page`, `page_size`, `search` |
| POST | `/auth/change-password` | Current active user; `current_password`, `new_password`; allowed during forced password change |

`/auth/login` adds `must_change_password` to its token response. `/auth/me` adds
that flag to its account response and remains available during forced change.
All ordinary protected endpoints return 403 `PASSWORD_CHANGE_REQUIRED` while
the flag is set. `/auth/change-password` returns a replacement access token.

User responses contain ID, username, email, full name, role, active/password-change
flags, and timestamps. They never include a password, hash, or token version.
The advisor directory contains only `id` and `full_name`, plus page metadata.
Creation and reset return account information, never generated credentials or
access tokens. All new input schemas reject unknown fields and null/empty edits.

Usernames are trimmed, lowercase, 3–50 characters, and limited to ASCII letters,
digits, `_ . @ + -`, beginning with a letter or digit. Emails are validated,
trimmed, and lowercase; names are trimmed and 1–200 characters. Passwords retain
the existing 12-character minimum, have a 1024-character maximum, and are hashed
using the existing Argon2 implementation. Self-service change verifies the
current password; both change and reset reject reuse of the current password.

The user list returns server pagination and filtered `total`, plus **global**
`counts.total`, `counts.active`, `counts.academic_admins`, and `counts.advisors`.
Role counts include active and inactive accounts. Search treats wildcard
characters literally. The frontend never derives global metrics from a page.

Errors use the existing `{ "error": { "code", "message", "details"? } }` shape.
Important codes include 409 `USER_IDENTIFIER_CONFLICT`,
`SELF_DEACTIVATION_FORBIDDEN`, `LAST_ACTIVE_SYSTEM_ADMIN`, and
`ADVISOR_HAS_ACTIVE_ASSIGNMENTS`; 400 `CURRENT_PASSWORD_INCORRECT`;
422 `PASSWORD_REUSE`/`VALIDATION_ERROR`; and 401 `AUTHENTICATION_REQUIRED`.

## Sessions, mutations, and audits

JWTs carry the integer `ver` credential version. Every protected request checks
the current database account, active status, role, and credential version.
Password change/reset, login-identifier changes, role changes, and activation or
deactivation increment the version, invalidating older tokens immediately on
their next API request. Full-name-only edits preserve sessions. Reactivating an
account never revives old tokens. Reset also replaces the hash and sets the
password-change flag; the old password no longer authenticates.

Legacy tokens without `ver` are treated as version zero and remain valid only
for unchanged migrated accounts at zero. Existing accounts are not forced to
change passwords merely by migration. Newly bootstrapped/provisioned accounts
and administrative resets require the change. Password change clears the flag
and returns a new JWT while invalidating all previous sessions.

A shared frontend session gate validates each protected route before mounting
its screen. It routes temporary-password users to the dedicated flow, rechecks
identity on focus, and sends expired/revoked/inactive sessions to sign-in.
Network failures offer retry without discarding credentials. User administration
checks the live role and renders a permission-denied view for other roles;
backend authorization is definitive. Existing disabled administration placeholders
remain disabled.

Account creation/update and alias reservations commit in one transaction with
their audit records. A shared database-key namespace reserves normalized
usernames and emails, including username-versus-another-account's-email
collisions. PostgreSQL account mutations take one transaction advisory lock and
refresh locked actor/target rows before checking permissions and invariants.
This favors reliable low-volume administration over concurrent admin writes.
Unique case-insensitive indexes and namespace primary keys independently reject
conflicts. Use these supported services for account writes; direct database edits
are not a provisioning interface.

`user_administration_audit` stores actor and target IDs, action, timestamp, and
safe changed-field metadata. Actions are `USER_CREATED`, `USER_UPDATED`,
`ROLE_CHANGED`, `USER_ACTIVATED`, `USER_DEACTIVATED`, `PASSWORD_RESET`, and
`PASSWORD_CHANGED`. Profile and role changes record before/after values;
credential actions record only the required-change state. The bootstrap creation
records the newly created account as actor and target with `source=bootstrap`.
No password, hash, or access token is recorded in audit metadata. There are no
ordinary audit mutation endpoints. Foreign keys retain historical references;
deactivation never deletes user rows. No-op activation/profile requests create
no misleading mutation audit.

## Administration and advisor safeguards

A System Admin cannot deactivate their own account. An active System Admin
cannot be demoted or deactivated if this would remove the last active System
Admin; inactive administrators do not satisfy this safeguard. Concurrent
demotions are serialized and cannot bypass it.

Demoting or deactivating an Advisor fails with 409 if the advisor owns any:

- Warning whose review state is not `DISMISSED` (pending and confirmed warnings).
- Intervention outside `COMPLETED` or `CANCELLED`.
- Follow-up with stored status `SCHEDULED`, including due or overdue follow-ups.

The response includes numeric `warnings`, `interventions`, and `follow_ups`
counts. Transfer these assignments through existing supported flows, or complete
them according to the existing lifecycle, before retrying. In particular, a
confirmed warning must still be transferred or explicitly unassigned even when
its intervention has finished. This conservative rule avoids silent ownership
loss. No casework state transitions were changed. Assignment eligibility checks
now lock and refresh the advisor row so assignment cannot race administration
and leave active work assigned to a newly inactive or demoted account.

## Migration and legacy conflicts

Migration `20261011_0009_user_administration.py`, revision `20261011_0009`, follows
`20261004_0008`. It adds `must_change_password` (false) and `token_version` (zero),
a nonnegative version check, case-insensitive username/email unique indexes,
`user_login_identifiers` with populated reservations, and the audit table.
The equivalent `lower(ltrim(rtrim(...)))` index expressions work in PostgreSQL
and SQLite and round-trip through PostgreSQL schema reflection.

Before any changes, it locks populated users and checks the combined normalized
username/email namespace. Cross-account collisions cause an explicit error and
transaction rollback; no user is silently rewritten or deleted. The same
identifier used as username and email by one account is valid and reserved once.

For conflict investigation on the **pre-migration** database:

```sql
SELECT identifier, array_agg(DISTINCT id) AS account_ids
FROM (
  SELECT id, lower(trim(username)) AS identifier FROM users
  UNION
  SELECT id, lower(trim(email)) AS identifier FROM users
) AS identifiers
GROUP BY identifier
HAVING count(DISTINCT id) > 1;
```

An operator must explicitly resolve the account identifiers after reviewing
ownership, preserving IDs and existing references, then retry the migration.
Coordinate migration with backend deployment. Downgrade preserves user rows and
removes A2 state/reservations/audits; archive audit data first if a rollback is
required. Do not run the A2 application against a downgraded schema.

## Reproducible verification

Routine tests use isolated SQLite fixtures and a local synthetic model fixture.
PostgreSQL checks require a dedicated server and credentials with CREATE DATABASE
and CREATE SCHEMA privileges; they create/drop only randomized test databases or
schemas. Never point these environment variables at a production server.

From `backend`, with the pinned A1 runtime and verified approved artifact:

```powershell
$env:USER_MANAGEMENT_TEST_DATABASE_URL = '<dedicated PostgreSQL URL>'
$env:STAGED_IMPORT_TEST_DATABASE_URL = $env:USER_MANAGEMENT_TEST_DATABASE_URL
$env:MODEL_TEST_DATABASE_URL = $env:USER_MANAGEMENT_TEST_DATABASE_URL
$env:RUN_MODEL_INTEGRATION = '1'
python -m pytest -q
python -m alembic heads
python -m app.ml.deployment verify
```

From `frontend`, run `npm run typecheck` and `npm run build`.

Account API tests cover all three roles, anonymous denial, normalized duplicates,
invalid fields/escalation, initial/change/reset passwords, old-token rejection,
inactive sign-in, last-admin/self safeguards, global metrics and pagination,
minimal advisor directory, active assignments, and safe audit payloads.
PostgreSQL tests cover same-field and cross-field creation races, independent
database uniqueness, concurrent last-admin demotion, populated migration
backfill/rollback/conflict detection, and bootstrap → owner password changes →
student import → verified model prediction → advisor assignment/review →
deactivation/access denial, including an assignment/deactivation race.

## Verified delivery: 11 October 2026

Implementation branch: `fix/phase-a2-user-management`, based on the pushed A1
commit `1d533d5a37db61caed97f95d9b82a976a6977a68`. No PR or merge is part of this
delivery.

| Check | Result |
| --- | --- |
| Complete backend suite, PostgreSQL flags and actual-model integration enabled | **220 passed**, 216 warnings, 101.45 seconds |
| New account API/RBAC tests | **24 passed**, including both non-admin roles and anonymous denial across every management operation |
| New PostgreSQL account tests | **9 passed**, including creation races, concurrent last-admin protection, migration conflict rollback and the real-model account workflow |
| All PostgreSQL integration checks in the complete suite | **14 passed**: 9 account, 4 staged-import, 1 A1 deployment |
| Alembic heads | Single head: **20261011_0009** |
| Approved A1 model verification | **dropout-logistic-regression-v1** verified |
| Changed Python files | Ruff import/undefined-name checks and formatting passed |
| Frontend | **Typecheck and production build passed**; standalone production server started successfully |
| Browser workflow | **All three roles verified** against an isolated migrated PostgreSQL database |
| Working-tree whitespace | `git diff --check` passed |

Browser verification used supported bootstrap, user-administration UI/API,
owner password-change flows, student CSV review/commit, and dossier prediction.
The real approved model produced a HIGH warning; the Academic Admin assigned
the provisioned advisor using the directory, and that advisor reviewed it.
Reset and deactivation revoked existing sessions, old credentials failed, and
reset credentials required owner replacement. Last-admin and active-assignment
conflicts appeared in the UI; role and profile changes, activation, pagination
over 23 actual test accounts, filtered global totals, empty states, and recovery
after a controlled API failure passed. Neither non-admin role had administration
navigation or could use the administration API.

Light, Dark, and System themes, desktop (1440px), tablet (768px), and mobile
(390px) layouts passed visual/browser checks without document overflow. Keyboard
focus and Escape restoration were checked. A delayed 401 from an old token after
password replacement did not clear the new session. The final standalone
production page reported no browser console errors.

Docker CLI was installed, but fresh container initialization could not run:
`docker info` failed because the Docker Desktop Linux engine pipe
`//./pipe/dockerDesktopLinuxEngine` did not exist. Instead, verification used a
fresh isolated PostgreSQL database, all migrations, the supported bootstrap,
the A1 verified model, and the built standalone frontend. Container startup is
therefore the remaining environmental verification limitation. The backend
suite reported dependency warnings, and Next.js emitted unused CSS-preload
warnings from route prefetching; these did not cause failed tests or browser
application errors. No invitation-email provider or bulk reassignment engine
was introduced.

A1 training, inference, thresholds, model records/checksums, CSV import logic,
warning review semantics, and casework lifecycles remain unchanged. Existing
staged-import/deployment test changes only adapt historical-schema fixtures and
the expected migration head. Warning/casework service edits only serialize
advisor eligibility checks with account mutations.

Local `main` remains at `c2487d5948d07f4a48bff07798250cda47bf25bb`; remote `main`
was read as `385f62f27901fdf5f294a8d19fc995d49de38667` before delivery. Neither
branch is a push target. Test databases and services are isolated from the
application's normal database; browser evidence is stored in ignored
`output/playwright/` files.

## Changed-file inventory (44 files)

- `backend/alembic/versions/20261011_0009_user_administration.py`
- `backend/app/api/v1/auth.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/users.py`
- `backend/app/core/permissions.py`
- `backend/app/core/security.py`
- `backend/app/db/init_db.py`
- `backend/app/models/__init__.py`
- `backend/app/models/user.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/user.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/casework_service.py`
- `backend/app/services/user_service.py`
- `backend/app/services/warning_service.py`
- `backend/tests/api/test_auth.py`
- `backend/tests/api/test_staged_imports_postgres.py`
- `backend/tests/api/test_users_postgres.py`
- `backend/tests/api/test_users.py`
- `backend/tests/ml/test_deployment_postgres.py`
- `docs/user-administration.md`
- `frontend/app/admin/users/page.tsx`
- `frontend/app/admin/users/users.css`
- `frontend/app/change-password/page.tsx`
- `frontend/app/layout.tsx`
- `frontend/app/login/page.tsx`
- `frontend/components/auth/auth-session.tsx`
- `frontend/components/casework/create-case-drawer.tsx`
- `frontend/components/dashboard/action-modal.tsx`
- `frontend/components/dossier/case-detail.tsx`
- `frontend/components/dossier/dossier-form.tsx`
- `frontend/components/dossier/follow-up-detail.tsx`
- `frontend/components/dossier/student-dossier.tsx`
- `frontend/components/follow-ups/follow-up-form.tsx`
- `frontend/components/layout/app-header.tsx`
- `frontend/components/layout/app-sidebar.tsx`
- `frontend/components/users/advisor-select.tsx`
- `frontend/components/users/user-dialog.tsx`
- `frontend/components/users/users-workspace.tsx`
- `frontend/lib/api.ts`
- `frontend/types/auth.ts`
- `frontend/types/user-administration.ts`
- `README.md`
