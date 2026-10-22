# D1.2 release gates and dependency compatibility

Date: 2026-10-22 (Africa/Casablanca). Base:
`0fb70a51f5b5bb07830c439edcea6f132676746c`, branch
`codex/phase-d1-academic-write-authorization`. Delivery branch:
`codex/phase-d12-release-gates`.

Read first: [D1 readiness audit](phase-d1-release-readiness-audit.md) and
[D1.1 implementation report](phase-d1-academic-write-authorization.md).
The original checkout has unrelated local changes and was preserved. Work uses
a separate managed worktree. Application source, backend tests, migrations,
scientific requirements, model parameters, registries, manifests and all three
model binaries are unchanged from D1.1. No model training/reproduction command,
RBAC rewrite, application feature change, PR or merge is part of this delivery.
Existing synthetic pipeline fixtures still run as part of the unchanged tests.

## Release-gate checklist

Every item is required before calling a release verified:

- [ ] Use Python **3.11.9**, install `backend/requirements-packaging.txt` before
  `backend/requirements-dev.txt` from the trusted PyPI index; `pip check` passes.
- [ ] Provision the retained legacy artifact through the encrypted Actions
  secret `LEGACY_MODEL_BASE64`. Verify all three approved byte checksums before
  deserialization, then run both existing deployment verifiers/inference probes.
- [ ] Use a new, disposable PostgreSQL 16 server with CREATE DATABASE permission
  and database `release_gate`. Acknowledge with `RELEASE_DISPOSABLE_POSTGRES=1`.
  Never supply an institutional, development, shared or operational database.
- [ ] Set **all seven** URLs below to that same disposable server and set
  `RUN_MODEL_INTEGRATION=1`. Missing/mismatched settings fail before test execution.
- [ ] Check the single Alembic head is `20261014_0012`. Create a random empty
  database, upgrade to head, query its actual revision, run `alembic check`,
  downgrade that empty database to base, upgrade again, and check again. Drop
  only that generated database. Existing historical/data-preservation migration
  tests also run in the full suite; this empty round trip does not promise safe
  downgrade of operational records.
- [ ] Run **all backend tests**, including the eight explicitly required modules
  listed in `scripts/ci/release_backend.py`. Collect no empty/missing mandatory
  suite; every collected test must pass. Any setup/call/collection skip, xfail,
  failure, incomplete run or empty collection fails the release gate.
  Use `APP_ENV=test` and `ML_MODEL_REQUIRED=false` for this test process: existing
  startup-negative fixtures explicitly enable required mode themselves. This
  test setting does not disable artifact provisioning, verification or real-model
  integration. Production Docker smoke retains `ML_MODEL_REQUIRED=true`.
- [ ] Pass Ruff `F,E9` on `backend/app`, `scripts/ci`, the D1.1 PostgreSQL module
  and `backend/tests/auth_context.py`; pass the release-control negative tests.
- [ ] From `frontend`, run `npm ci`, `npm audit --audit-level=low`,
  `npm run typecheck`, and `npm run build` on Node 22 in CI.
- [ ] Build the default backend runtime and standalone frontend Docker images;
  default backend verification must verify all three models. Start fresh tmpfs
  PostgreSQL and application containers on a unique network, publish only random
  loopback HTTP ports, probe live/ready, unauthenticated denial, login, required
  password replacement, authenticated identity, the three-model catalog and
  frontend HTML/security headers. Run both artifact verifiers inside the image.
- [ ] Review saved backend summary, resolved package inventory and Docker smoke
  evidence for this source. Cleanup must check both project and invocation
  labels before removing owned containers, the empty network or owned image tags.
- [ ] Require **Release required** in the target branch's protection/ruleset.
  All three component jobs must succeed; skipped, cancelled or failed jobs fail
  the aggregate. There are no path filters or optional model/integration jobs.
- [ ] Resolve the hosted enforcement blocker below before treating merge
  enforcement as configured. Other public-deployment findings from D1 also remain
  separate prerequisites; passing D1.2 does not approve internet exposure.

Required PostgreSQL settings:

```text
MODEL_TEST_DATABASE_URL
DUAL_STAGE_TEST_DATABASE_URL
STAGED_IMPORT_TEST_DATABASE_URL
USER_MANAGEMENT_TEST_DATABASE_URL
FRESHNESS_TEST_DATABASE_URL
C1_CASEWORK_TEST_DATABASE_URL
D1_AUDIT_TEST_DATABASE_URL
```

The workflow runs on every push, pull request, merge-group event and manual
dispatch, with read-only repository permission, commit-pinned official Actions,
no persisted checkout credentials, explicit timeouts and an always-run aggregate.
It never uses `pull_request_target`. Forks without the private artifact secret
fail provisioning; there is no unverified fallback, training or skip path. Review
fork contributions before running a trusted branch with repository secrets.
Literal fixture credentials in the workflow apply only to its disposable CI
database/test process. Docker HTTP smoke generates new random database,
bootstrap and signing credentials in a private temporary environment file.

## Secure artifact provisioning

The two existing B1 binaries remain tracked and unchanged. The private retained
legacy binary remains ignored. On 2026-10-22, its 11,572 approved bytes were
base64-encoded in memory, encrypted to the repository Actions public key with a
sealed box, and stored as `LEGACY_MODEL_BASE64` (GitHub HTTP 201). Neither the
payload nor the GitHub credential was logged, committed, uploaded as evidence or
included in a command argument. Base64 is a transport encoding; GitHub's secret
store supplies encryption. No artifact URL or external pickle download is used.

To rotate/provision using an approved local file and an authenticated GitHub CLI,
run a private Python session with this pattern (the subprocess consumes stdin):

```python
import base64
import subprocess
from pathlib import Path
payload = Path("/private/approved/model.joblib").read_bytes()
subprocess.run(
    ["gh", "secret", "set", "LEGACY_MODEL_BASE64", "--repo",
     "SabetAbderrahmane/student-dropout-risk-early-warning-system"],
    input=base64.b64encode(payload), check=True,
)
```

Before provisioning, verify the approved hash independently. CI independently
compares bytes against both fixed approved checksums and the unchanged reviewed
manifests before existing verifiers deserialize. Missing/corrupt artifacts fail.
CI removes the ignored legacy file in an always-run step. Images containing it
are built locally on the disposable runner, never pushed or uploaded. Evidence
uploads explicitly include only the safe summary/package inventory/smoke JSON;
raw pytest XML, source directories, environment files and image layers are not
uploaded. Uploaded evidence retention is 14 days; job-log retention follows the
repository's existing policy.

| Artifact directory | Preserved SHA-256 |
| --- | --- |
| dropout-risk-v1 | `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8` |
| enrollment-outcome-v1 | `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602` |
| first-semester-outcome-v1 | `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81` |

## Dependency decisions

The [authoritative advisory inventory](phase-d12-dependency-advisories.json)
records the 17 D1 advisory records retrieved again from GitHub's reviewed API,
plus the newly observed wheel advisory. Version bounds and published release
metadata were checked on 2026-10-22, rather than using scanner upgrade suggestions.

| Coordinate | Minimal change | Basis and compatibility boundary |
| --- | --- | --- |
| Next | 16.3.7 → 16.3.8 | First fixed release for all six D1 Next advisories; preserve React/React DOM 19.3.0, routing and configuration. [Vendor release](https://github.com/vercel/next.js/releases/tag/v16.3.8). |
| source-map-js | 1.2.1 → 1.2.2 | First fixed release for [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q), selected within PostCSS's existing compatible range. No override or broad `npm audit fix`. [Vendor release](https://github.com/7rulnik/source-map-js/releases/tag/v1.2.2). |
| pip | seeded 24.0 → 26.2.0 | First version covering all six D1 pip advisories, including [GHSA-qwm4-qh6w-59xr](https://github.com/advisories/GHSA-qwm4-qh6w-59xr); exact separate tooling pin. |
| setuptools | seeded 65.5.x → 83.0.0 | First version covering all four D1 setuptools advisories, including [GHSA-h35f-9h28-mq5c](https://github.com/advisories/GHSA-h35f-9h28-mq5c). Its macOS normalization precondition does not describe a Linux HTTP exploit. |
| wheel | inherited 0.44.0 → 0.46.2 | Fresh Linux inventory exposed [GHSA-8rrh-rw8j-w5fx](https://github.com/advisories/GHSA-8rrh-rw8j-w5fx); upstream [0.46.2 release](https://github.com/pypa/wheel/releases/tag/0.46.2) fixes malicious-wheel unpack permissions. |

The six Next advisories retain D1's qualified applicability: development MCP
disclosure applies to `next dev`; the others require absent cache/draft mode,
Pages Router SSG/ISR, metadata webpack, root catch-all or remote-image patterns.
Source-map parsing and packaging extraction/index/download advisories require
untrusted inputs/build operations; scanner severity is not evidence of a remotely
exploitable API route. Dependencies are patched despite those narrower bounds.

Only the Next package, its matching env/SWC packages and source-map-js change
versions in the npm lockfile. Next's published Node requirement remains >=20.9;
its React peer range accepts the unchanged 19.3.0. Linux Node 22 container and
native Node 24.14.0 checks cover the existing app. Clean Python installs, `pip
check`, all model verifiers and the zero-skip backend suite are the packaging
compatibility checks. No scientific library pin is loosened or replaced.

Backend web/test dependency ranges and mutable image tags remain as inherited;
the evidence records their resolution/image IDs, not a new complete lock or an
image-digest policy. D1-08 is therefore not claimed fully resolved. Dependency
audits are dated package-coordinate checks, not OS-image certification.
The published packaging metadata accepts Python 3.11.9: pip 26.2.0 and
setuptools 83.0.0 require >=3.10; wheel 0.46.2 requires >=3.9. The full resolved
Linux inventory contains 63 distributions and is recorded with the final audit.

## Exact verification and failures

See [machine-readable verification evidence](phase-d12-verification-evidence.json)
for final results, image IDs, suite counts, source hashes and log digests.
Private raw logs/helpers remain under this worktree's ignored `.venv`.

The checklist above is reusable for future releases. Its final execution record
for this delivery is in the evidence JSON, with passing local checks separated
from the two hosted blockers and the resolved failed attempts below.

The unchanged D1.1 image was built before any Dockerfile edit from the specified
base and given OCI revision `0fb70a51f5b5bb07830c439edcea6f132676746c`.
Its backend tests were mounted read-only from the clean D1.1 worktree, with all
seven URLs and real-model flag enabled against tmpfs PostgreSQL 16. Both baseline
and final tests use Python 3.11.9 and all three real artifacts.
The corrected unchanged-D1.1 container run passed **544 tests, zero skips**, with
298 warnings in **945.85 seconds**. Its separate HTTP/authentication/catalog
smoke and all three in-image artifact verifiers passed. This closes the D1.1
final-source container verification blocker recorded in its implementation
report; the older B2/C1 container evidence remains a separate historical record.

The final D1.2 mandatory gate passed **544 tests, zero skips** in **1285.98
seconds** (XML duration 1285.964 seconds). Its summary records Python 3.11.9,
544 collected, 544 passed, an empty skipped list and exit code 0. The 299 warnings
are the inherited 298 plus one pytest cache-write warning caused by the local
read-only source mount; no warning or test failure was suppressed. All 163 D1.1
authorization and 81 C1 PostgreSQL cases are included in each final full run.

Other final results: **24 release-control tests passed**; both artifact verifiers
passed; fresh/round-trip Alembic and drift checks passed; targeted Ruff lint and
format checks, actionlint 1.7.12 and `git diff --check` passed; frontend clean
install, typecheck and production build passed; npm audit and the 63-distribution
Linux pip-audit returned **zero known vulnerabilities**; production backend and
frontend Docker build/HTTP smoke passed. Model checksums and scientific trees
match the D1.1 base. The smoke checks direct backend HTTP plus frontend HTML and
headers; it is not a browser end-to-end or public-deployment topology test.

Reproducible gate commands (repository root unless stated):

```text
python -m pip install --index-url https://pypi.org/simple -r backend/requirements-packaging.txt
python -m pip install --index-url https://pypi.org/simple -r backend/requirements-dev.txt ruff==0.17.1
python scripts/ci/provision_models.py --source <approved-retained-local-file>
python -m ruff check backend/app scripts/ci --select F,E9
python -m ruff check backend/tests/api/test_d1_authorization_postgres.py backend/tests/auth_context.py --select F,E9
python -m pytest -q scripts/ci/test_release_controls.py
# From backend, after configuring all seven disposable URLs and both required flags:
python ../scripts/ci/release_backend.py
# From frontend:
npm ci
npm audit --audit-level=low
npm run typecheck
npm run build
# Root, after artifact provisioning, on an isolated runner:
python scripts/ci/docker_smoke.py --project <unique-owned-project> --evidence <private-output>/smoke.json
git diff --check
```

For this local Docker host every created object uses the project label
`d1-audit-8ff43a5b`. The unchanged D1.1 smoke also used
`--backend-image d1-audit-8ff43a5b:baseline --backend-only`; D1.2 uses default
builds for both images. CI uses `release-<run-id>-<attempt>` on disposable runners.

Resolved attempts are reported separately from final results:

1. Initial baseline build failed because the new worktree had no ignored legacy
   artifact directory. Provisioned the retained checksum-verified file and rebuilt
   successfully. No source, manifest or model substitution was used.
2. Initial smoke fixture used `release@example.test`; email-validator correctly
   rejected its reserved domain during bootstrap. Changed only the harness to
   `example.edu`. Added immediate detection of exited smoke containers.
3. First actionlint check rejected numeric lookup of the PostgreSQL port in the
   workflow expression. Changed its key to the string `'5432'`; validation passes.
4. First patched Linux package audit found inherited wheel 0.44.0 affected by
   CVE-2026-24049. Added wheel 0.46.2, stopped that owned preliminary D1.2 test
   run, rebuilt, and ran verification again. The interrupted run is not counted
   as a final passing suite.
5. The first complete unchanged-D1.1 run reported **542 passed, 2 failed, zero
   skipped** in 1045.83 seconds. Both failures were the cached startup-error test:
   the test container inherited `ML_MODEL_REQUIRED=true` from the production
   runtime image, while that fixture first expects the test default false.
   Correcting only the test environment made both cases pass immediately.
   Restarted both full suites with explicit test settings; the D1.1 run also
   mounts the original `pyproject.toml` read-only so strict marker configuration
   applies. The release preflight now rejects production-mode inheritance.

## Hosted blocker and remaining scope

Cleanup completed before handoff. Both disposable servers had zero remaining
fixture databases, zero fixture schemas, zero public tables and zero other
client connections. After checking project labels, removed the two completed
test containers, two tmpfs database containers, empty owned network and four
owned image tags. Each smoke invocation separately checked its project/run
labels and removed its own resources. The old stopped container
`9987fc4f8376` had no mounts, and its empty project network `d3da45a644ee` was
removed after positive ownership inspection at the start of this task. Final
label-filtered inspection found **zero project containers, networks, volumes or
images**. No shared container, network, volume or image tag was altered. No
shared service was restarted, no Docker context was changed and no resource or
build cache was pruned. Private raw evidence is retained under ignored `.venv`.

Actions is enabled and allows the pinned actions. The artifact secret was
successfully provisioned. Read-only GitHub REST checks of
`/repos/.../branches/main/protection` and `/repos/.../rulesets` both returned
**403**, explicitly stating that this private repository requires GitHub Pro or
public visibility for those features. This is a confirmed plan restriction,
not evidence of an absent settings attempt. Repository visibility, subscription,
branch policies and shared infrastructure were not changed.

Hosted execution is separately blocked. Pushing executable-source commit
`cf0c36af72921d5561f6ed2bb54dbf2bdad69729` created
[run 39824623182](https://github.com/SabetAbderrahmane/student-dropout-risk-early-warning-system/actions/runs/39824623182)
with `conclusion=startup_failure`, an empty workflow name, `path=BuildFailed`,
zero jobs and zero check runs. Its workflow registration `393183487` reports
`state=deleted`, rather than the tracked `release.yml`. A single rerun request
returned 403, `This workflow run cannot be retried`. The API supplies no reason
or job logs; the local browser is signed out and cannot display this private
run's UI diagnostic. The exact platform/account cause is unconfirmed. Actionlint
1.7.12 validates the tracked workflow. No broad workflow/settings reset, billing
change, visibility change, unrelated commit or PR was used to probe it.

Resolve the hosted startup condition with repository-account diagnostics or
GitHub Support, then rerun this exact executable source and retain all three
successful job results. This delivery's executable evidence is from isolated
local containers and native frontend/tool checks, not a claimed green Actions
run. GitHub's [workflow troubleshooting documentation](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)
describes account/trigger/execution diagnostics; it does not establish the cause
of this particular failure.

The next meaningful executable correction, commit
`edb2ce6468e529b163c43606ae64dded41518ac1`, also produced startup failure before
any jobs in run `39825442693`; the evidence stores the exact revision returned
by GitHub. This repeated condition was not worked around by weakening gates.
The final executable commit `103a283e2fe03211874f364e91eac658eb7c7ff2`
likewise produced zero jobs in
[run 39825944164](https://github.com/SabetAbderrahmane/student-dropout-risk-early-warning-system/actions/runs/39825944164).

After the repository owner resolves that plan restriction, require the stable
**Release required** status on the actual release target and prevent bypasses
according to institutional policy. Until then, manually enforce the checklist;
do not claim server-enforced mandatory merge protection. Passing CI alone does
not prevent an administrator from pushing/merging without that policy.

D1-06's tracked CI/skip-gate defect and D1-07's identified package coordinates are
addressed by this change, with hosted enforcement qualified above. D1-02 login
abuse controls, D1-03 public topology, D1-04 production secret validation, D1-05
aggregate stage readiness, D1-08 full reproducibility, D1-09 complete operational
model handoff, D1-10 recovery runbooks and optional D1-11 export guidance are not
claimed fixed. C1 and D1.1 behavior and scientific contracts remain unchanged.
