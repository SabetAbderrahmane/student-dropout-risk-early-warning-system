# Verified model deployment

The approved model is `dropout-logistic-regression-v1`. Its binary stays ignored
by Git. No trusted public download location currently exists in this repository.
The supported preparation path runs the existing offline training recipe and
requires an exact match before installation. A trusted copy retained by the
operator can also be installed using the reviewed registry manifest.

## Approved artifact and trust boundary

`backend/app/ml/model_registry/dropout-risk-v1/artifact_manifest.json` binds the
artifact SHA-256, model version, canonical JSON hashes of metadata/evaluation/split
records, and dependency versions. The registry in the checked-out, reviewed
commit is authoritative. Never replace its checksum with one from a downloaded
file or accept a manifest shipped by an unknown artifact provider. A checksum
alone does not authenticate a publisher. Joblib uses pickle and can execute code.

The approved checksum is:

```text
0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8
```

It was established after an independent complete training run reproduced the
existing binary byte for byte, with matching evaluation, thresholds, split, and
metadata (excluding the new run timestamp and temporary output location). The
original registry metadata and evaluation remain unchanged. Canonical JSON hashes
are independent of Git newline conversion and JSON formatting.

## Runtime compatibility

Use Python 3.11.9 and these exact inference dependencies:

| Dependency | Version |
| --- | --- |
| joblib | 1.6.0 |
| NumPy | 2.4.6 |
| pandas | 2.3.3 |
| SciPy | 1.17.1 |
| scikit-learn | 1.7.2 |
| XGBoost / Linux xgboost-cpu | 3.2.0 |

Training also uses ucimlrepo 0.0.7. `backend/requirements.txt` pins these packages;
the Dockerfile pins Python 3.11.9. SciPy was absent from the old metadata; its
version is now recorded in the manifest from the independently reproduced run.
The loader checks exact Python and package versions before deserialization and
treats scikit-learn's serialization version warning as an error. This follows
[scikit-learn's persistence guidance](https://scikit-learn.org/stable/model_persistence.html).
Version checks do not guarantee numerical identity across OS/CPU/BLAS builds;
the reproduction checksum and integration tests are the additional gates.

## Fresh clone preparation

Install Python 3.11.9, create and activate a virtual environment, then:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m app.ml.deployment reproduce
python -m app.ml.deployment verify
```

`reproduce` downloads UCI 697 and runs all three original candidate searches,
development-only calibration and final-test evaluation in temporary directories.
It compares the generated records against the authoritative registry, ignoring
only the training timestamp. It installs the binary atomically only after the
trusted checksum, version compatibility, bundle consistency and real inference
probe pass. It neither overwrites the tracked registry nor blesses a new checksum.
This is an explicit preparation step that can take several minutes.

For an operator-retained artifact, skip dataset retrieval and training:

```bash
python -m app.ml.deployment install --source /trusted/storage/model.joblib
python -m app.ml.deployment verify
```

The source path is supplied by the operator. There is no fallback model or
automatic remote download. Both commands verify against this checkout's registry.
Installation preserves any existing valid destination on verification failure.

If reproduction differs on another platform, it fails. Do not edit the approved
checksum to bypass that failure. Either supply the exact approved binary, or
explicitly generate and review a new complete training run with a distinct version:

```bash
python -m app.ml.training.train --model-version dropout-logistic-regression-v2
python -m app.ml.deployment verify
```

The training command refuses to replace an existing registry with the same model
version. A new run writes its binary and all metadata, evaluation, split, report
and integrity records together; review and commit all registry files together
before deployment. A partially written run fails verification. A newly generated
model is not claimed identical to the previously evaluated model. Updating a
model is separate from ordinary deployment; this change preserves the v1 model.

## Docker

From the repository root, after preparation:

```bash
docker compose build backend
docker compose up -d
```

The default `runtime` target copies the artifact to
`/app/app/ml/artifacts/dropout-risk-v1/model.joblib` and verifies it during the
build. Missing binaries and failed verification stop the build. Only the approved
binary is allowed from the artifact directory into the build context. Environment
files, temporary training outputs, and test database data are excluded. The image
runs as the existing non-root `app` user. Startup applies Alembic migrations and
optional administrator bootstrap; it never trains.

The runtime image sets `ML_MODEL_REQUIRED=true`: model failure also stops API
startup, including after an operator mounts a replacement artifact. Outside
Docker, `APP_ENV=production` likewise requires a valid model. Startup failures
log a stable model code. Correct the deployment and restart to clear a cached
failure; ordinary requests do not reload or retrain.

For intentional degraded local development only, select
`BACKEND_BUILD_TARGET=development` in the Compose environment. This target permits
missing ML artifacts; its healthcheck tests process liveness. The default runtime
image's healthcheck tests database plus ML readiness. `ML_MODEL_REQUIRED=true` or
`APP_ENV=production` enables strict startup outside the default runtime target too.

## Health contracts

| Endpoint | Successful result | Failure |
| --- | --- | --- |
| `/api/v1/health/live` | 200, `{"status":"ok"}` | Unreachable if process stopped |
| `/api/v1/health` | Existing 200 database connectivity payload | Existing 503 `DATABASE_UNAVAILABLE` |
| `/api/v1/health/ready` | 200 when database and model are usable | 503 with separate database/model status and stable codes |

Readiness checks an actual loaded model that has already passed the startup
inference probe. When the database is connected, it also validates/synchronizes
the persisted model registry using the existing prediction service. A conflicting
persisted version reports `MODEL_REGISTRY_MISMATCH`, not false readiness.

Example successful readiness response:

```json
{
  "status": "ready",
  "database": {"status": "connected", "code": null},
  "model": {"status": "ready", "code": null}
}
```

With PostgreSQL down, database status is `unavailable`, code
`DATABASE_UNAVAILABLE`. Missing model/registry reports model status `unavailable`,
code `MODEL_ARTIFACT_UNAVAILABLE`. Integrity, registry or dependency failures
report model status `mismatch` with one of these codes:

- `MODEL_CHECKSUM_MISMATCH`: non-empty bytes differ from the trusted SHA-256.
- `MODEL_ARTIFACT_CORRUPTED`: empty artifact or checksum-verified file cannot load.
- `MODEL_REGISTRY_MISMATCH`: changed/malformed records, model version, schema,
  thresholds, explanation contract, hyperparameters, or persisted database registry.
- `MODEL_RUNTIME_INCOMPATIBLE`: installed Python/packages differ from the manifest.

Responses contain no internal paths, traces or secrets. Both database and model
statuses are returned even if both fail. `/health` retains its existing contract.

## Verification

Routine tests use temporary fitted pipelines, require no personal artifact, and
never download UCI:

```bash
cd backend
python -m pytest -q
python -m alembic heads
python -m app.ml.deployment verify
```

Enable the actual trained artifact test after preparation (PowerShell uses
`$env:RUN_MODEL_INTEGRATION='1'` instead of `export`):

```bash
export RUN_MODEL_INTEGRATION=1
python -m pytest -q -m model_integration
```

For the full API workflow, point the test at a dedicated PostgreSQL test server
whose user may create databases. Never use the normal development database:

```bash
export RUN_MODEL_INTEGRATION=1
export MODEL_TEST_DATABASE_URL='postgresql+psycopg://test_user:test_password@localhost:55439/postgres'
python -m pytest -q -s tests/ml/test_deployment_postgres.py
```

The test creates a random database, applies every Alembic migration, starts the
FastAPI lifespan, checks all health endpoints, authenticates an academic admin,
imports an eligible student through the API, executes the real trained model,
and verifies the persisted prediction, warning and history. It drops only the
database it created. This exercises the API in-process; a Docker Compose run is
still necessary to verify container networking, startup commands and healthchecks.

## Troubleshooting

Run `python -m app.ml.deployment verify` first. Missing artifact: prepare or install
it before the default Docker build. Missing manifest/registry: restore the
complete approved checkout. Checksum/corruption failure: replace the binary from
the trusted preparation workflow. Dependency failure: use the pinned environment;
do not suppress serialization warnings. Registry conflict: check that the binary
and all records belong to one approved run, and that a new run has a new version.
Do not reset the development database to hide a conflict.

No Docker daemon means container build/deployment cannot be verified. No UCI
access and no retained trusted artifact means preparation cannot finish. Report
these limitations rather than claiming inference deployment is ready.

## Phase A1 verification record (2026-10-11)

- Full backend suite: **187 passed**, including actual artifact inference,
  disposable PostgreSQL API prediction, and existing PostgreSQL concurrency and
  migration tests. The same suite passed in a fresh checkout with a newly created
  virtual environment installed from `requirements-dev.txt`.
- Fresh checkout started with neither a model binary nor environment secrets.
  `python -m app.ml.deployment reproduce` downloaded UCI and installed the exact
  approved binary; `verify` passed. No original local binary was copied in.
- A separate production-mode Uvicorn process in that fresh checkout passed live
  HTTP liveness, database health, readiness, authentication, CSV import and real
  prediction checks. Probability was **0.9919118545297152**, risk **HIGH**;
  the prediction, warning and history were persisted in a disposable PostgreSQL
  database. All test databases were removed; the development database was unused.
- Alembic has one head: `20261004_0008`. Compose configuration validation,
  `git diff --check`, and focused Python import/undefined-name checks passed.
- The fixture suite emits 210 pandas dtype FutureWarnings while exercising the
  existing explanation code with synthetic reference values. Prediction and
  explanation behavior were preserved.
- PostgreSQL verification used locally installed PostgreSQL 18. Docker build
  was attempted but could not connect to `dockerDesktopLinuxEngine`: the daemon
  was unavailable. The Linux image, Compose networking, PostgreSQL 16 image,
  container healthchecks and non-root execution have **not** been run here.
