# Phase D1: security, CI and deployment-readiness audit

Audit date: **2026-10-15**. Repository:
`SabetAbderrahmane/student-dropout-risk-early-warning-system`.
Audited release base: **`68faf1d62cc37acf9074fcff00f61ac0aa420698`**.
Branch: `codex/phase-d1-release-readiness-audit`.

## Executive verdict

**Local thesis demonstration: conditional go with synthetic data and trusted,
sequential operators.** A clean installation completed the core workflow with
all three verified models. No functional blocker to that bounded demonstration
was found. The authorization race below is still a defect; this verdict does
not approve use with untrusted operators or real institutional records. Keep
the demonstration local, use generated credentials and the production frontend
rather than an exposed development server, and prepare the artifacts/accounts
before presenting. The README needs a consolidated three-model handoff.

**Internet-accessible deployment: no-go with the supplied configuration.** The
academic-write revocation race, missing abuse controls and undefined public
deployment/recovery gates require bounded implementation work first. No public
deployment topology has been selected or tested here. This is an audit verdict
against exposing the current development setup unchanged, not a claim that an
already configured production environment exists and is insecure.

This delivery contains **tests and audit documentation only**. Production code,
migrations, requirements, lockfiles, CI configuration and model artifacts are
unchanged. Passing characterization tests reproduce unresolved behavior; they
are not security fixes. No PR, merge, public deployment or training was performed.

The B2 targeted Docker verification gap **remains closed** for the combined
final application source. The prior
[combined container report](b2-c1-final-container-verification.md) at
`9cd8abd63131d5a6d63931045a8796c45475c6ab` remains applicable: its child base
`68faf1d…` changed documentation only. The new Docker interruption described
below does not invalidate that evidence or create a requirement for a full-suite
container rerun to close B2 again.

## Baseline, scope and inventory

The original checkout was clean on `codex/phase-c1-casework-integrity`, exactly
at the expected base. A managed isolated worktree was created at that SHA and
the requested D1 branch was created there. `git merge-base <base> HEAD`
confirmed ancestry. The original checkout and its existing ignored resources
were preserved. Main was not a delivery target.

Read before auditing: repository README, `frontend/AGENTS.md`, the
[B1](phase-b1-dual-stage-prediction.md),
[B2](phase-b2-prediction-freshness.md),
[C1](phase-c1-casework-integrity.md) and combined final-container reports.
Their dated results remain distinct from D1's new checks.

The complete source inventory is in
[phase-d1-route-inventory.json](phase-d1-route-inventory.json): **77 explicit
backend method/path pairs**, **12 application page routes**, and **25 existing
backend test modules** before D1. The frontend build also generates framework
not-found/icon routes. No `.github/workflows` files or other tracked pipeline
configuration were found at this base. Hosted branch protection, external CI
integrations and organization policy were not inspected; their absence is not
inferred from the checkout.

| Surface | Current boundary / implementation |
| --- | --- |
| `/`, `/login`, `/change-password`; protected frontend workspaces | `AuthSession` checks `/auth/me`; ordinary API requests enforce server-side permissions independently of controls. |
| `/dashboard`, `/students`, `/students/{id}`, `/predictions`, `/warnings`, `/interventions`, `/follow-ups` | Institution-wide read access for all three roles is intentional. Assignment constrains casework writes, not student visibility. |
| `/imports` | Academic Admin writes; System Admin reads/import history/export; Advisor denied. |
| `/admin/users` | System Admin only; advisor directory readable by all existing read roles. |
| `/api/v1/auth/login`, health/live/ready; `/docs`, `/redoc`, `/openapi.json` | Public. `/auth/me` and password change require active authentication but allow required-password-change accounts. |
| Student CRUD/admission/semester writes; prediction execution | Academic Admin only at dependency entry. Their unguarded transaction boundary is discussed in D1-01. |
| User administration and model validation/activation | System Admin; service revalidates the actor under the shared administration lock. |
| Warning review/reconsideration, casework writes/transfer/recovery | C1 guarded authorization, assignment, revision, lock-order and lifecycle checks; transfer/recovery restricted to Academic Admin, review to assigned Advisor. |

Deployment assets: `backend/Dockerfile`, `frontend/Dockerfile`, their respective
`.dockerignore` files, `docker-compose.yml`, three `.env.example` files, backend
settings, `app.db.init_db`, Alembic revisions through `20261014_0012`, and the
legacy/B1 model provisioning/verifier commands. No separate startup script is
hidden: backend CMD runs migration → optional bootstrap → Uvicorn. Operating
documentation exists for model deployment and account/casework contracts, but
not a complete production/recovery runbook.

## Findings register

Severity refers to practical impact with the stated preconditions, not a scanner
aggregate. No Critical finding is claimed.

| ID | Type / severity | Finding | Local demonstration | Public deployment |
| --- | --- | --- | --- | --- |
| D1-01 | Confirmed defect / High | In-flight academic writes can commit after account revocation wins. | Avoid concurrent revocation/write activity; fix still needed. | Blocker. |
| D1-02 | Confirmed control gap / Medium | Login has no application throttle and an unknown-identifier hash-work asymmetry. | Limited exposure on a trusted local demo. | Abuse control required before exposure. |
| D1-03 | Configuration gap / High for public target | Development Compose publishes all services and uses the database bootstrap superuser as the app role; no TLS/proxy deployment profile. | Supported development use, with local/firewall restrictions. | Supplied setup must not be exposed unchanged. |
| D1-04 | Configuration gap / Medium, conditional | Production settings accept low-entropy signing keys once length passes. | Generate a strong key; no missing-key default exists. | Strong secret provisioning/validation is a release prerequisite. |
| D1-05 | Confirmed readiness gap / Medium | Ready status covers legacy model/DB, not the two stage artifacts. | Not a blocker when all three verifiers pass. | Incomplete health contract for a three-model release. |
| D1-06 | CI/release gap / High | No tracked pipeline; important integration modules can all skip with exit 0. | Manual checks currently supply evidence. | Add mandatory release gates. |
| D1-07 | Confirmed affected dependencies / Medium in this app | Frontend and packaging-tool versions have authoritative advisories; feature preconditions substantially narrow exposure. | Prefer production frontend; patch in a separate task. | Triage/patch affected coordinates; do not claim every scanner item is remotely exploitable. |
| D1-08 | Reproducibility gap / Medium | Backend is only partly pinned; no complete resolved dependency lock or image digest policy. | Fresh installation succeeded today. | Record and constrain the release environment. |
| D1-09 | Documentation gap / Low | Main installation guidance centers on legacy model; B1 provisioning/activation is scattered. | Handoff improvement needed, not a demonstrated runtime failure. | Include all intended models in the release procedure. |
| D1-10 | Operating-documentation gap / Medium | No documented backup/restore, release rollback and log-retention procedure. | Disposable demonstration can be recreated. | Required before retaining operational data. |
| D1-11 | Optional enhancement / Low | Canonical staged CSV preserves formula-like source text; export UI does not explain spreadsheet risk. | Use it for re-import. | Clarify usage; preserve the lossless contract. |

### D1-01 — academic write authorization stops at request entry

Affected: `core/permissions.py:get_current_user/require_roles`,
`api/v1/students.py:create_student`, `services/student_service.py:create_student`,
and `services/staged_import_service.py:commit` via
`POST /imports/staged/{batch_id}/commit` (all backend paths under `backend/app`).
The student endpoint discards the actor after its dependency. Staged commit
uses actor identity for audit but does not lock/refetch/revalidate that actor.

Reproduction: the committed
[PostgreSQL characterization module](../backend/tests/api/test_d1_authorization_postgres.py)
pauses actual service entry after HTTP authentication, then uses the real
System Admin endpoint to deactivate, demote or reset the Academic Admin before
resuming. All **six cases** (two operations × three revocations) returned write
success and persisted the student after revocation committed. A separate
connection confirmed the credential version had advanced before release of the
timing gate. A fresh request with the old token then returned 401. Timing hooks
control ordering only; authorization, revocation and persistence are real,
using separate request sessions on migrated disposable PostgreSQL.

Preconditions/impact: an already authenticated Academic Admin request must
overlap revocation. This does not let an unauthenticated request or a newly
arriving Advisor request become an administrator. It does let a revoked session
finish sensitive writes after revocation has won, including staged import
commit, despite the stronger C1 semantics elsewhere.

Mitigation: ordinary entry RBAC, credential versions, batch CAS/row locking,
duplicate checks and import audit are present. Account administration, model
validation/activation and C1 writes revalidate actors under locks. The C1 mutex
`610110009`, sorted user locks, presented claims and historical safeguards work
and must be preserved.

Smallest fix: reuse the existing guarded actor-validation pattern in a narrowly
scoped Academic Admin write boundary, in the established lock order, held through
commit/rollback. Start with the two reproduced service families; inventory the
other academic writers before calling the boundary complete. Student update,
direct import and prediction/batch execution show the same entry-only pattern
in source, but were **not separately race-reproduced** here. Do not claim model
administration has this defect: it calls `UserService._administrator`.

Regression needed: convert these characterization cases to assert denial/no
domain or success-audit write when revocation wins; add the opposite ordering
where a guarded write commits before revocation can finish. Cover remaining
academic writers, preserving C1's existing lock-order/concurrency tests.

### D1-02 — login abuse and work asymmetry

Affected: `api/v1/auth.py:login`,
`services/auth_service.py:authenticate`,
`repositories/user_repository.py:get_by_username_or_email`. Twelve consecutive
wrong-password requests for a known account all reached Argon2 and returned 401,
without 429/backoff/Retry-After. The unknown-account branch skipped password
verification entirely. The committed security characterization observes the
real verifier call count while preserving its behavior. No statistical remote
timing attack or service-exhaustion benchmark was performed.

Preconditions/impact: access to the public login endpoint permits repeated
guessing and expensive verification work. The source-confirmed work asymmetry
can supply an enumeration timing signal; its remote accuracy is unmeasured.
Generic failure bodies for absent/inactive/wrong-password accounts, Argon2,
request field bounds, short-lived tokens and backend RBAC already mitigate other
risks. Login's user row lock serializes that account's login transactions; it
does not impose an abuse budget. There is no supplied edge rate limiter.

Smallest fix: bounded account/client abuse controls at a trusted edge or shared
application limiter, explicit 429 handling, and comparable unknown-account hash
work after the abuse budget check. Avoid a permanent attacker-triggered account
lockout. Regression: bounded failed bursts, expiry/recovery of the budget,
unknown/inactive failure parity, and trusted proxy/client-address behavior. MFA
or a wholesale token architecture replacement is not required to fix this finding.

### D1-03 — the development deployment is not a public release profile

Affected: `docker-compose.yml`, backend CMD and deployment documentation.
Compose publishes `5432`, `8000`, `3000` without loopback binding, sets backend
`APP_ENV=development`, supplies its `POSTGRES_USER` directly as the application
database role and has no TLS termination/reverse-proxy service. The official
[PostgreSQL image contract](https://hub.docker.com/_/postgres) gives that bootstrap
user superuser power. No separate application grants/migrator role are provided.
These are source/configuration facts, not evidence of a publicly running instance.

Impact/preconditions: exposing this setup on an internet host without external
firewall/TLS controls exposes unnecessary ports and unencrypted bearer login/API
traffic; an application credential compromise carries superuser database scope.
The README calls this a development environment and instructs replacement of
credentials; password-authenticated PostgreSQL and non-root app containers are
existing controls. The runtime target still requires the legacy model despite
Compose's development APP_ENV.

Smallest fix: define the actual single-instance public topology: TLS edge,
private DB/backend ports, exact origins, host validation at the edge or app,
trusted proxy rules, production environment and secret provisioning; separate
one-off migrations/bootstrap from a least-privilege runtime role. Choose whether
API documentation is public by policy. OpenAPI visibility and unrestricted Host
acceptance were observed, but no Host-derived reset-link poisoning was found;
neither observation alone is labeled an authorization bypass.

Regression: generated configuration/port checks, HTTP→HTTPS behavior and forwarded
headers, allowed/rejected origins/hosts, runtime-role privilege checks, and
startup/migration smoke on that chosen topology. It is unnecessary to impose
that topology on the local thesis demo during this audit.

### D1-04 — secret validation is length-only

Affected: `core/config.py:Settings`, root/backend `.env.example`, README secret
instructions. The characterization constructs production settings with a repeated
character key of sufficient length; validation accepts it. Secret values are
not reproduced here. Missing JWT key fails validation; HS256 is explicitly fixed,
the minimum length is enforced, and README replacement instructions exist.

Risk is conditional on operator misconfiguration, not a demonstrated weak live
deployment key. Length does not establish entropy. The default database URL is
also a development placeholder, rather than production provisioning validation.
Smallest fix: document generation/storage of a random key and required explicit
production DB configuration, reject known example/placeholder values in production,
and document rotation/revocation. Do not claim an entropy heuristic proves key
strength. Regression: missing/known-placeholder production inputs fail safely;
valid generated configuration succeeds without logging its values.

### D1-05 — readiness can be green with unavailable stage models

Affected: `api/v1/health.py:readiness`, `main.py:lifespan`,
`ml/outcomes/runtime.py`, Compose readiness probe. The characterization configures
an absent temporary `ML_OUTCOME_ROOT`; both stage readiness DTOs report
`UNAVAILABLE`, while `/health/ready` still returns 200 `ready` using the verified
legacy fixture. This isolated test never changes deployed artifact files.

Impact: a wrong stage root, missing deployment mount or stage registry failure
can remain invisible to the aggregate health probe for a three-model deployment.
The default runtime build verifies all three artifacts, explicit stage APIs
report stable failures and never silently substitute a model, and default B1
registrations intentionally begin inactive. No missing artifact was found in the
prepared release itself.

Smallest fix: define expected artifact scopes in the deployment health contract
and expose/check their verified availability and registry consistency. Do not
require model activation before startup: activation needs an authenticated live
application and real ready student. Regression: legacy and each stage absent,
corrupt/incompatible registry, inactive-but-valid stage, and unavailable DB.

### D1-06 — no automated release gate, and skipped integration tests look green

Affected: absent tracked workflows, `backend/tests/conftest.py`, PostgreSQL test
fixtures, `backend/pyproject.toml`, frontend package scripts. An actual run of the
C1 module without `C1_CASEWORK_TEST_DATABASE_URL` exited **0 with 81 skipped**.
Other integration fixtures similarly gate on their dedicated URL and/or
`RUN_MODEL_INTEGRATION`. This is visible in pytest output, but a runner checking
only exit status could silently accept no integration coverage. D1's new
PostgreSQL characterization also declares its own environment requirement.

Existing tests are substantial and passed when enabled; the defect is not an
absence of tests. Frontend already has typecheck/build scripts. There is no
frontend lint/test script or enforced repository lint policy, nor a tracked
model/migration/container CI gate.

Smallest fix: add a reviewed workflow after this audit, not a replacement for
an invented existing pipeline. Provide a dedicated PostgreSQL service with
CREATE DATABASE capability, explicitly require every integration variable,
provision/verify all three artifacts, run baseline regression and model flags,
and fail the intended mandatory job if it skips tests. Keep expected unsafe
characterization results separately labeled until converted to regression tests.
Include typecheck/build, relevant Python lint, Alembic single-head/fresh migration,
and isolated container smoke. Never point destructive tests at operational data.

Regression: a missing integration variable or missing trusted artifact fails the
release job; correctly provisioned environment runs the intended tests with zero
skips. Hosted branch protections/external CI status require a separate settings
inspection and are not established by this audit.

### D1-07 — affected dependency coordinates, with qualified applicability

`npm audit --json` reported two high aggregate package entries:
**Next 16.3.7** and transitive **source-map-js 1.2.1** (via PostCSS).
Seven unique advisories were checked against GitHub's authoritative advisory
records. Aggregate severity does not establish an exploitable application route.

| Advisory | Confirmed version range / release fix | Applicability at this source |
| --- | --- | --- |
| [GHSA-3w37-wq28-93x7](https://github.com/advisories/GHSA-3w37-wq28-93x7) | Next ≥16.3.0, <16.3.8 | Requires cache components/use-cache plus Draft Mode; not configured/found. |
| [GHSA-4jqv-mc3x-m676](https://github.com/advisories/GHSA-4jqv-mc3x-m676) | Next ≥16.0.0, <16.3.8 | Pages Router SSG/ISR; this application uses App Router. |
| [GHSA-39w2-rjm5-chcv](https://github.com/vercel/next.js/security/advisories/GHSA-39w2-rjm5-chcv) | Reviewed database: Next ≥16.0.0, <16.3.8 | Relevant to documented `npm run dev`: visiting a malicious site while dev server runs can expose development metadata. Production runtime does not serve the MCP endpoint. Vendor page still has a placeholder patch label; reviewed database supplies the precise range. |
| [GHSA-f87g-xv8r-7p7x](https://github.com/advisories/GHSA-f87g-xv8r-7p7x) | Next ≥16.0.0, <16.3.8 | Requires webpack dynamic metadata-image routes; no such routes found, default build used Turbopack. |
| [GHSA-mcj8-r9mp-w47p](https://github.com/advisories/GHSA-mcj8-r9mp-w47p) | Next ≥16.0.0, <16.3.8 | Requires root catch-all plus SSG/ISR; no root catch-all page found. |
| [GHSA-cjq9-62q9-8jv4](https://github.com/advisories/GHSA-cjq9-62q9-8jv4) | Next ≥16.0.0, <16.3.8 | Image remote-pattern prerequisite absent; upstream explicitly excludes configurations without remotePatterns. |
| [GHSA-68fv-2mgg-jv7q](https://github.com/7rulnik/source-map-js/issues/76) | source-map-js ≥1.0.0, <1.2.2 | Untrusted indexed source-map parsing prerequisite; no API accepting source maps found. Reachability through build/dev/error tooling was not exploit-tested. |

Smallest frontend fix candidate: the advisory patch range points to Next 16.3.8
and source-map-js 1.2.2, subject to upstream release confirmation, lockfile review
and the existing typecheck/build/browser checks. npm's suggestion of Next 16.4.1
is a scanner resolution suggestion, not proof that a broader upgrade is required.
No package or lockfile was changed in D1.

`pip-audit 2.10.1 --path .venv/Lib/site-packages` scanned **62 distributions**,
skipped none, and returned 20 vulnerability records in two packaging tools:
**pip 24.0** and **setuptools 65.5.0**, seeded by Python 3.11.9's venv. Duplicate
feed records reduce to **10 unique advisory IDs**, not 20 distinct defects.
No advisory was returned for the resolved application dependency distributions.
This is a point-in-time scanner result, not an assurance that they are defect-free.

| Packaging advisory | First fixed version / relevant precondition |
| --- | --- |
| [pip GHSA-4xh5-x5gv-qwph](https://github.com/advisories/GHSA-4xh5-x5gv-qwph) | 25.3; vulnerable extraction fallback is mitigated here by Python 3.11.9's PEP 706 support. |
| [pip GHSA-6vgw-5pg2-w6jp](https://github.com/advisories/GHSA-6vgw-5pg2-w6jp) | 26.0; malicious wheel extraction. |
| [pip GHSA-58qw-9mgm-455v](https://github.com/advisories/GHSA-58qw-9mgm-455v) | 26.1; ambiguous concatenated archive handling. |
| [pip GHSA-jp4c-xjxw-mgf9](https://github.com/advisories/GHSA-jp4c-xjxw-mgf9) | 26.1; post-install self-check import behavior with malicious installed modules. |
| [pip GHSA-wf93-45jw-7689](https://github.com/advisories/GHSA-wf93-45jw-7689) | 26.1.2; malicious entry-point paths. |
| [pip GHSA-qwm4-qh6w-59xr](https://github.com/advisories/GHSA-qwm4-qh6w-59xr) | 26.2.0; malicious index URL handling. |
| [setuptools GHSA-r9hx-vwmv-q579](https://github.com/advisories/GHSA-r9hx-vwmv-q579) | 65.5.1; malicious package-index HTML/ReDoS. |
| [setuptools GHSA-cx63-2mw6-8hw5](https://github.com/advisories/GHSA-cx63-2mw6-8hw5) | 70.0.0; unsafe package-index download functions. |
| [setuptools GHSA-5rjg-fvgr-3xxf](https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf) | 78.1.1; PackageIndex download path traversal. |
| [setuptools GHSA-h35f-9h28-mq5c](https://github.com/advisories/GHSA-h35f-9h28-mq5c) | 83.0.0; macOS sdist filename normalization/exclusion issue; not applicable to the Windows/Linux runtimes tested. |

These concern installation/build trust, not a demonstrated unauthenticated API
RCE. Smallest fix: separately update/constrain packaging tooling and trusted-index
installation policy without changing the frozen scientific dependency/model
contracts. Regression: clean install, artifact verifiers and application checks;
do not bypass manifests or retrain artifacts to make an upgrade pass. The new
Linux image did not finish, so its final Python/OS package inventory was not
scanned or certified. Public package coordinates/advisory IDs were queried;
repository code and sensitive configuration were not uploaded to scanners.

### D1-08 — release dependency provenance is incomplete

Affected: `backend/requirements*.txt`, both Dockerfiles and deployment docs.
ML dependencies and Python are intentionally exact to satisfy the manifests;
most web/database/test dependencies use ranges, with no complete resolved backend
lock or hash set. Frontend has a committed npm lockfile and `npm ci`; container
base tags are mutable. The fresh install resolved FastAPI 0.143.2, Starlette
1.8.0, SQLAlchemy 2.1.4, PyJWT 2.15.1 and other versions recorded in the evidence.
They passed the new baseline, so no present install failure is alleged.

Impact: future clean builds may change non-ML dependencies/image contents without
source changes. Smallest fix: reviewed platform-appropriate resolved constraints
and release image digests/provenance, keeping the scientific pins intact.
Regression: clean Linux/Windows installs as supported, zero-skip intended suites,
all three artifact verifiers and a recorded runtime image build. Do not loosen
the exact model-compatibility checks to accommodate unrelated upgrades.

### D1-09 — the primary handoff omits the full three-model lifecycle

Affected: README and `docs/ml-model-deployment.md` emphasize reproducing/verifying
legacy binary. B1's two tracked models, separate verifier/root and explicit
validation/activation are described in `phase-b1-dual-stage-prediction.md`, but
not assembled into the main quick start. A fresh checkout contains both B1
artifacts but no legacy binary. Legacy verification correctly failed until the
supported trusted-artifact installation was performed.

Existing mitigation: exact manifests, build-time verification, a documented
operator-retained installation path and detailed B1 report. Missing UCI access
or a trusted legacy artifact is an explicit provisioning limitation, not a reason
to substitute a mock. D1 used the retained trusted file; it did not exercise the
retraining/reproduction path because this audit forbids retraining.

Smallest fix: one installation sequence for all three artifacts, verifier
commands, a trusted legacy distribution/retrieval policy, inactive stage
registration, ready-student validation, System Admin activation, temporary
bootstrap removal and required password change. Regression: a fresh checkout
can follow that documented sequence and make real enrollment/semester/legacy
predictions without modifying registries or fetching an untrusted pickle.

### D1-10 — recovery and operations lack a complete runbook

Affected: README/operating docs, startup CMD, Compose persistent database volume,
logging configuration. Searches found no `pg_dump`/restore procedure, backup
ownership/storage/retention/restore cadence, application release rollback plan,
log rotation/retention/access procedure or multi-instance migration coordination.
C1 does document downgrade history loss; B1 intentionally refuses lossy rollback
with stage records. Those safeguards must remain.

A new **disposable** pg_dump custom-format → fresh DB pg_restore experiment
succeeded: all **22 public tables** matched by row count and complete-row hash,
including users, model records, predictions and casework audit. It was an
operator-devised experiment, not validation of a nonexistent documented procedure.
It did not test off-host backup security, role/grant restoration, catastrophic
recovery or a production RPO/RTO. The restore DB was removed afterward.

Smallest fix: a tested runbook covering scoped backup/restore, separately secured
configuration and trusted artifacts, data/audit retention, migration/rollback
compatibility and log handling. For more than one app instance, move coordinated
migrations to an explicit job before starting replicas. Regression: disposable
restore preserves domain/audit records and permissions, then starts the supported
application/model set; failed migration and rollback paths preserve data. No
production downgrade or data repair belongs in this audit.

### D1-11 — canonical export needs a usage distinction, not silent rewriting

Affected: `services/staged_import_service.py:export`,
`components/imports/staged-commit-panel.tsx` and import docs. A harmless `=1+1`
name is preserved literally in staged export, as the committed characterization
demonstrates. Existing API documentation explicitly defines this as a lossless
canonical re-import CSV. It is authenticated, bounded and restricted to
Academic/System Admin read access; the browser renders the text rather than
executing it. This is not a defect in that documented data contract.

The visible button says “Export Edited CSV” without a spreadsheet caveat. A user
opening arbitrary canonical source text in spreadsheet software can interpret it
as a formula. Separate prediction/warning spreadsheet exports already quote cells,
double embedded quotes and prefix formula-leading text; they were reviewed rather
than falsely labeled wholly unprotected.

Optional smallest improvement: label/warn that canonical CSV is for re-import;
if a spreadsheet display export is needed, provide an explicitly sanitized copy
without changing stored or canonical values. Regression: canonical byte/value
round-trip remains intact, while the separate display copy neutralizes dangerous
prefixes in actual supported spreadsheet software. No spreadsheet execution was
performed and no claim about every application's whitespace handling is made.

## Authentication, input and exposure controls that already work

- Missing/malformed/expired/unsigned/wrong-scheme and mismatched-version bearer
  credentials returned 401 through actual API dependencies. HS256 is fixed;
  token type/subject/time claims are required and UUID/version validation is
  present. The compatibility allowance for absent `ver` at unchanged version 0
  is documented, not treated as an unsigned-token bypass.
- Current account activity, role, credential version and password-change state
  are consulted by server dependencies. Password change/reset and account/role
  changes revoke old credentials. The fresh HTTP workflow proved forced-password
  change for the initial System Admin and both provisioned academic roles, plus
  rejection of their superseded tokens. Native integration tests cover inactive
  accounts, role changes, last-admin/self-deactivation and assignment safeguards.
- System Admin controls account creation/reset/deactivation. Bootstrap requires
  all fields, validates them, requires a temporary password and is idempotent;
  two fresh bootstrap invocations did not overwrite the first account. There is
  no public registration path. Sensitive account/model/C1 writes revalidate the
  actor in their authorization transaction. Academic entry-only writers are the
  specific exception established in D1-01.
- C1 authorization and domain history, canonical assignment, explicit closure,
  stale-form conflicts, sorted user/domain locks and atomic action audit remain
  intact. The current 81-case module ran in the fresh zero-skip baseline. Read
  projections do not rewrite inconsistent history, warnings or predictions.
- CSV services enforce extension/filename length, UTF-8 with optional BOM, exact
  schema/duplicate header rules, 5 MiB service read limit, 5,000 nonblank rows,
  cell lengths, finite numeric/feature validation and duplicate-student handling.
  Filenames are metadata and are not used as server write destinations. Staged
  edits whitelist canonical fields/versions; commits revalidate duplicates and
  commit the graph atomically. They do not overwrite existing students. The
  multipart parser sees uploads before the service limit; total ingress/spooling
  budgets belong in the selected public edge configuration, not an assumed
  already-deployed safeguard.
- Reviewed SQLAlchemy queries bind user-controlled values; escaped LIKE patterns
  are not string-interpolated SQL. UUID/resource validation and bounded page sizes
  are enforced server-side. No request-controlled executable SQL or subprocess
  path was found. This is source review plus existing validation tests, not a
  blanket proof against every possible injection.
- User-controlled names, notes, CSV values and errors use ordinary React text
  rendering. The reviewed `dangerouslySetInnerHTML` sink is a fixed theme bootstrap
  whose stored preference is restricted to three literal choices. No dynamic
  untrusted HTML sink was found. API validation errors omit submitted inputs,
  including password fields; DB errors use generic responses. Unhandled exceptions
  use FastAPI's non-debug 500 response; there is no custom catch-all structured
  handler, but no traceback/credential response leak was demonstrated.
- JWT storage is sessionStorage and API requests explicitly add Authorization;
  CORS uses exact configured origins and disallows credentials. Cross-origin
  rejection and absence of unsolicited cookie authentication are existing
  controls, not reasons for an authentication rewrite. XSS would threaten bearer
  tokens, but an exploitable XSS path was not found in this audit.
- The only public frontend environment setting found is `NEXT_PUBLIC_API_URL`;
  it is build-time configuration and must match the client-accessible API URL.
  No credential is intended in it. Docker ignores environment files; runtime
  frontend contains standalone output/static assets. Static shells/JS do not
  replace authenticated API data access.
- Targeted private-key/GitHub-token/AWS-key pattern scanning found no matches in
  the audited tracked source; manual settings/example review found development
  placeholders and synthetic test credentials, not an apparent live credential.
  Locations reviewed: root/backend/frontend `.env.example`, settings, bootstrap,
  tests and deployment configuration. No secret values are reproduced. This was
  not exhaustive entropy/history scanning and does not certify all Git history.
- Model requests select fixed registered versions/stages, never arbitrary pickle
  paths. Trusted local CLI/config paths are an operator boundary. Verifiers check
  trusted artifact/registry bytes, exact runtime compatibility and inference
  before using joblib; they deserialize the same verified in-memory bytes.
  Manifests are integrity controls anchored in the trusted checkout, not signed
  attestations against a compromised publisher. All three hashes remain those
  recorded in the prior combined report.
- Both Dockerfiles specify non-root runtime users. Backend runtime installs
  `requirements.txt`, not pytest/dev requirements; tests/env files are ignored.
  Training/provisioning modules and some optional runtime tooling are present,
  but no request-triggered training path was found. Trimming them is optional
  image hardening, not a demonstrated remote execution finding. A new D1 runtime
  image was not completed after Docker stopped.

## Existing CI capability and actual D1 verification

Capability is separated from enforcement. The existing test/build tooling can
run the checks below in a correctly provisioned clean runner; no tracked CI
configuration enforces them today.

| Gate | Current capability | D1 result / remaining constraint |
| --- | --- | --- |
| Backend dependencies | requirements-dev includes runtime; ML versions exact, other ranges | Fresh Python 3.11.9 venv install and `pip check` passed. |
| Existing backend suite | pytest with dedicated PostgreSQL fixtures and opt-in real models | **370 passed, zero skipped**, 238 existing fixture warnings, 443.97 s; native PostgreSQL 18.3. D1 modules excluded because separately exercised. |
| Added D1 tests | 11 boundary/characterization cases plus 6 DB race cases | **17 passed**, zero skipped, 12.02 s; race cases on dedicated Docker PostgreSQL 16 before engine loss. |
| Missing-variable safety | fixtures skip rather than fail | Actual C1-only run: **81 skipped, exit 0**, 0.50 s. |
| PostgreSQL suites | six dedicated URL variables plus real-model flag | All enabled in the fresh 370-test run; migration/concurrency/account/import/freshness/artifact evidence retained. |
| Frontend | locked npm install, `typecheck`, `build` | Fresh `npm ci`, typecheck and production build passed; host Node 24.14.0/npm 11.9.0. Docker specifies Node 22; no new D1 Docker/frontend browser coverage is claimed. |
| Lint | no committed lint runner/policy | Ruff 0.17.1 focused E9/F63/F7/F82 scan passed; new modules also passed F/E9 and were formatted. No full-style clean claim. |
| Models | legacy and B1 verifier CLIs | All three verified in the fresh environment; no retraining, replacement or checksum relaxation. |
| Migrations | Alembic and disposable populated-migration tests | Single head `20261014_0012`; fresh DB migrated, full existing integration suite passed. |
| Container build/smoke | current Dockerfiles; prior combined passing images/workflows | D1 fresh backend build attempted; Docker stopped before export/final verifiers. No new successful image ID/smoke is claimed. Prior combined B2/C1 results still apply. |
| Advisories | npm audit; isolated pip-audit tool environment; authoritative GHSA queries | Findings/ranges/preconditions above; no upgrades performed. No completed-image OS scan. |
| Recovery | pg_dump/pg_restore tools available | Disposable 22-table row/hash comparison passed; no existing runbook or production recovery guarantee. |

Existing full-suite PostgreSQL variables:
`MODEL_TEST_DATABASE_URL`, `DUAL_STAGE_TEST_DATABASE_URL`,
`STAGED_IMPORT_TEST_DATABASE_URL`, `USER_MANAGEMENT_TEST_DATABASE_URL`,
`FRESHNESS_TEST_DATABASE_URL`, `C1_CASEWORK_TEST_DATABASE_URL`; also require
`RUN_MODEL_INTEGRATION=1`. D1 race tests use `D1_AUDIT_TEST_DATABASE_URL`.
All refer to a dedicated CREATE DATABASE server. Do not substitute SQLite or an
institutional database for those PostgreSQL gates.

## Clean installation and recovery experiment

The isolated worktree began without dependencies, environment secrets or the
ignored legacy artifact. Both tracked B1 artifacts were already present and
passed their verifier. The legacy verifier correctly returned
`MODEL_ARTIFACT_UNAVAILABLE`. It was then installed once into the fresh checkout
using the documented operator-retained trusted source path and manifest, and
verified. Neither original artifact bytes nor tracked registries were changed;
the scientific runtime pins remained exact. Dataset/network reproduction was
not run and no mock was substituted for the absent artifact.

The first disposable service was `d1-audit-8ff43a5b`, a tmpfs PostgreSQL 16 Docker
database published only on `127.0.0.1:55469`. It supported the completed six race
cases. During a subsequent fresh backend runtime build the engine became
unavailable; `docker desktop status` reported **stopped**. The dependent full
suite attempt and owned build CLI were canceled; their partial output is not a
passing result. The reason Docker stopped was not established. No daemon/context
restart or shared-resource change was made.

To continue independently, a **new**, separately initialized PostgreSQL 18.3
cluster was created inside this audit worktree's ignored `.venv/d1-pg`, listening
only on port 55479. This is not the original checkout's existing native cluster.
Fresh UUID-named databases were migrated and bootstrapped. A production-mode
Uvicorn process bound to `127.0.0.1:8034` used that new installation.

The live HTTP sequence completed **44 expected-status checks**: readiness;
bootstrap System Admin login/mandatory change/old-token rejection; account
provisioning and required changes for Academic Admin/Advisor; direct API role
denials; real CSV import; real System Admin validation/activation of both stage
models with rolled-back validation probes; real enrollment, semester and legacy
prediction; warning assignment and Advisor confirmation; intervention and
follow-up creation; premature closure rejection; contact completion without
implicit parent closure; explicit parent completion; current semester selection,
retained case visibility, original prediction immutability and empty integrity
diagnostic. This was a live API workflow, not a new browser or full-stack Docker
workflow. Prior browser evidence remains separately applicable.

The first local CSV harness serialized integer-valued fixture floats as decimal
strings and was correctly rejected by the existing CSV integer validator. The
harness was corrected and the successful complete sequence ran on a new empty
database. This was a harness correction, not an application defect/fix.

The successful database was dumped using PostgreSQL 18 tools, restored into a
different generated database and compared read-only across all public tables.
The dump omitted role/grant restoration deliberately for this disposable
same-owner experiment; those operational concerns remain in D1-10.

Representative actual commands (from the audit root unless noted):

```powershell
git switch -c codex/phase-d1-release-readiness-audit
git merge-base 68faf1d62cc37acf9074fcff00f61ac0aa420698 HEAD
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
.venv/Scripts/python.exe -m pip check
# In frontend:
npm ci
npm audit --json
npm run typecheck
npm run build
# In backend, with fresh venv and the configured environment:
python -m app.ml.deployment verify
python -m app.ml.deployment install --source <operator-retained-trusted-model.joblib>
python -m app.ml.outcomes.deployment verify
python -m app.ml.deployment verify
python -m alembic heads
python -m alembic upgrade head
python -m app.db.init_db
python -m app.db.init_db
python -m pytest -q tests/api/test_d1_security_audit.py tests/api/test_d1_authorization_postgres.py
# With C1 URL absent (separate environment):
python -m pytest -q tests/api/test_casework_integrity_audit_postgres.py
# With all six existing URLs and RUN_MODEL_INTEGRATION=1:
python -m pytest -q --ignore=tests/api/test_d1_security_audit.py --ignore=tests/api/test_d1_authorization_postgres.py
# Isolated audit-tools environment:
python -m pip_audit --path .venv/Lib/site-packages --format json
ruff check backend --select E9,F63,F7,F82
docker compose -f .venv/d1-compose.yaml up -d database
docker compose -f .venv/d1-compose.yaml build backend
docker desktop status
```

Local ignored orchestration scripts recorded in evidence:
`.venv/d1-provision-native.py`, `d1-server.py`, `d1-clean-workflow.py`,
`d1-backup-restore.py` and `d1-native-cleanup.py`. The dump/restore subprocesses
used `pg_dump -Fc` and `pg_restore --exit-on-error --no-owner --no-privileges`
with the host/port/user/database of these generated disposable databases.
Passwords were provided through a child environment, not printed command
arguments. These ignored scripts/settings are local evidence, not new supported
deployment tooling. Committed tests supply portable reproductions for findings.

Machine-readable results, resolved versions, normalized advisory ranges, HTTP
checks, recovery hashes and cleanup status are in
[phase-d1-audit-evidence.json](phase-d1-audit-evidence.json). No tokens,
credential values or raw database dumps are committed.

## Cleanup and limitations

Confirmed native cleanup: the Uvicorn process and owned children were stopped;
`SHOW data_directory` matched the exact isolated D1 cluster before removal of
its generated databases; all nondefault databases and other client connections
were zero. Both clean-install attempt databases were dropped. Existing suite
fixtures and the restore fixture dropped their own databases. The new native
server was stopped and ports **8034/55479 had no listeners**. Original/shared
native services were not started, stopped, migrated or reset.

**Docker cleanup is unconfirmed.** The exact scoped command was attempted:

```powershell
docker compose -f .venv/d1-compose.yaml -p d1-audit-8ff43a5b down --volumes
```

It exited 1: `Docker Desktop is unable to start`. Desktop still reported stopped.
The only deliberately started service was
`d1-audit-8ff43a5b-database-1`, with network
`d1-audit-8ff43a5b_default`, tmpfs data and no persistent volume. No D1 backend or
frontend application container was started. A Docker-owned loopback proxy still
listened on **55469**; its shared backend process was not killed. Resource IDs,
actual residual container/network state and final volume inventory cannot be
confirmed while the engine is unavailable. The ignored Compose file remains so
that the same scoped removal can finish when Docker is available. No prune,
image removal or shared-daemon lifecycle action was used.

Automatic approval review rejected the attempted deletion of the stopped owned
native cluster directory and accompanying local dump/password-file cleanup with
“blocked by policy.” No part of that rejected command executed. The stopped
cluster directory (with no nondefault databases), generated local configuration
and small disposable backup remain ignored locally. The backup contains only
synthetic workflow data and test-account hashes, remains private, and is not
claimed removed. This filesystem retention and the unavailable Docker cleanup
are explicit remaining limitations, not a clean-everything claim.

Other limits: no public deployment, full new container run, OS-image vulnerability
scan, exhaustive stress/penetration test, browser re-audit of every text/export
surface, actual spreadsheet formula execution, hosted GitHub policy inspection,
off-host disaster recovery, statistical remote timing attack, or exhaustive Git
history secret scan. No institutional model/privacy/fairness validation is newly
claimed; earlier scientific limitations remain. Native evidence was not relabeled
as container evidence, and characterization successes were not relabeled fixes.

## Prioritized bounded implementation plan

1. **D1.1: close the Academic Admin mutation revocation boundary.** Start with
   student creation and staged commit, convert the six reproductions into
   denial/atomicity regressions, then cover the remaining source-identified
   academic writers before claiming the boundary complete. Reuse the current
   actor validation, mutex/user ordering and immutable presented credentials.
   Preserve C1 domain/audit/assignment semantics. No auth architecture rewrite,
   new product feature or model change is needed. This is the smallest
   recommended next implementation scope.
2. **D1.2: establish the release CI gate and dependency maintenance change.**
   Mandatory PostgreSQL/model variables, trusted artifact provisioning, zero-skip
   intended regression checks, typecheck/build/lint/migration/model verification
   and isolated container smoke; separately review the minimal frontend and
   packaging-tool advisory patches and resolved constraints. Do not upgrade
   frozen ML dependencies or manifests as incidental cleanup.
3. **Before internet exposure:** choose the public deployment topology and abuse
   budget; implement TLS/private ports/least-privilege roles/secret provisioning,
   stage-aware readiness, and the tested backup/restore/rollback/log runbook.
   Public docs/host policy can be handled at the selected edge. Validate that
   actual configuration rather than assuming a future proxy supplies controls.
4. **Local handoff:** consolidate the three-model/bootstrap/activation guide and
   clarify canonical CSV usage. Keep original source text and scientific records
   intact. Complete only the identified disposable Docker cleanup when its
   engine becomes available; do not reopen the closed B2 verification finding.

Audit commit identity and remote confirmation are reported at delivery; the
commit cannot contain its own hash.
