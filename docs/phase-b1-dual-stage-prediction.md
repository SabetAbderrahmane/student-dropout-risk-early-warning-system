# Phase B1: dual-stage, three-class academic outcome prediction

## Baseline and compatibility plan (recorded before implementation)

Starting commit: `4bf6f89f60cac0b806a27d47ccbf91cb1040b9e7` on
`fix/phase-a2-user-management`. Work branch:
`feat/phase-b1-dual-stage-prediction`. Local main starts at
`c2487d5948d07f4a48bff07798250cda47bf25bb`, remote main at
`385f62f27901fdf5f294a8d19fc995d49de38667`; neither is a delivery target.

Existing inference is a frozen binary first-semester pipeline, version
`dropout-logistic-regression-v1`, schema `uci697-first-semester-v1`, with 30
ordered inputs and target `{Dropout: 1, Enrolled: 0, Graduate: 0}`. Its artifact
SHA-256 is `0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8`.
The tracked registry, training/evaluation records, manifest, original training
modules and serialized bundle class will remain unchanged. A1 verification must
still succeed. No v1 retraining or artifact regeneration is authorized.

Current prediction APIs omit stage selection and use that binary model. Keep
that behavior when a client omits a stage. Explicit `prediction_stage=ENROLLMENT`
or `FIRST_SEMESTER` selects the new multiclass model; never fall back from a
requested stage to binary inference. Historical probabilities still mean
P(Dropout), and historical multiclass outcome/probability fields remain null.
Add stage and target type to model and prediction records, preserve IDs, and
replace global activation uniqueness with uniqueness per (stage, target type).
The v1 active flag is preserved; new registrations begin inactive. Activation
is a distinct System Admin operation after verification and integration checks.

Warnings continue to use dropout probability and each selected model's risk
thresholds. Every prediction remains append-only. Existing warning decisions,
interventions and follow-ups are preserved. Batch deduplication and freshness
invalidation are outside this phase. Dashboard aggregates must explicitly state
their stage/model scope; a binary threshold must never describe mixed-stage
risk counts.

The repository's `revision after teacher questions 1.docx` describes a binary
dropout-risk system, first-semester data, validation-based thresholds, and human
review. It leaves algorithm choice subject to supervisor approval. This B1
extension is the implementation requested here, **not documented supervisor
approval or institutional validation**.

## Input timing and source audit

Source: [UCI dataset 697](https://archive.ics.uci.edu/dataset/697/),
Realinho, Vieira Martins, Machado and Baptista (2021),
[DOI 10.24432/C5MC89](https://doi.org/10.24432/C5MC89), CC BY 4.0. Each row is one
student, and the outcome is measured at the end of the normal course duration.
The official source distinguishes enrollment data from end-of-semester results.

The initial bounded fetch returned 4,424 rows, 36 features, no missing values,
and zero exact duplicate full rows. Observed labels: Dropout 1,421; Enrolled 794;
Graduate 2,209. Canonical source-frame CSV SHA-256:
`4b15c8e0b1fc9ea1e7994caaff47db72c07e0049bf9e47758aa53c2fc7fd6376`.
This hash describes the canonicalized fetched frame, not the original raw CSV
bytes. No additional personal identifiers or new sources are collected.

Enrollment uses the 21 canonical `SourceStage.ENROLLMENT` fields, in their
existing order. First-semester uses those 21 plus the six canonical
`SourceStage.FIRST_SEMESTER` fields, in existing order (27 total). Neither model
uses second-semester results or the target as input.

UCI macroeconomic fields lack observation/release-vintage timestamps. Their
availability cannot be justified at enrollment or definitively at the first
semester cutoff from this extract, so all three are excluded from both new
schemas. A1's historical 30-feature contract is preserved. Deployment must
capture enrollment financial/scholarship indicators as known at enrollment and
first-semester measurements only after that semester; source labeling supports
these stages but does not prove local institution data collection timing.

There are no student identity/group/time columns suitable for independent
temporal validation. Deterministic row stratification is a reproducible UCI
benchmark, not evidence of future-cohort or cross-institution performance.
Identical enrollment projections do not establish duplicate student identities.

## Frozen experimental protocol

New target mapping: `{Dropout: 0, Enrolled: 1, Graduate: 2}`. Public labels:
`DROPOUT`, `ENROLLED`, `GRADUATE`. New stage-specific ordered schema versions and
model versions are independent of v1.

Seed 42, stratified 80/20 development/final-test split on the three-class target,
shared between stages. Within development, stratified 60/20/20 partitions
separate search/fitting, probability calibration, and risk-threshold calibration.
All partition memberships and hashes are frozen. No final-test features, labels,
or metrics inform selection, preprocessing, calibration, or thresholds.

For each stage compare multinomial Logistic Regression, Random Forest, and
XGBoost (`multi:softprob`, three classes). Use bounded randomized searches with
five shuffled stratified folds. Each fold learns numeric median imputation and
scaling and categorical mode imputation/one-hot encoding with unknown-category
handling. Compare unweighted and balanced class/sample weighting where supported;
XGBoost weights must be computed inside the fit on its own fold labels.

Hyperparameter refit and stage winner selection use the same predeclared score:
`0.40 * dropout recall + 0.30 * dropout PR-AUC + 0.20 * macro F1 +
0.10 * dropout precision`, using development CV results. Require dropout recall
at least 0.55 and macro F1 at least 0.45; fail explicitly if no candidate meets
the constraints. Ties favor dropout PR-AUC, then macro F1, then deterministic
family order. Accuracy alone never determines the winner.

After selection freezes, fit each candidate's fixed sigmoid probability
calibration on its disjoint development calibration partition with a frozen
estimator. For each stage winner, use the separate threshold partition to choose
the largest LOW boundary retaining at least 90% dropout recall and the
precision-maximizing HIGH boundary retaining at least 70% dropout recall. Require
ordered valid thresholds and report actual achieved precision/recall; do not
copy v1 thresholds or substitute an undocumented fallback. Calibration quality
includes multiclass log loss/Brier score, dropout Brier score and equal-width
reliability bins/ECE, before and after sigmoid calibration on the threshold
partition. This partition is not used to select a calibration method.

Once all choices are frozen, score all six calibrated candidates on the final
test once for a comparative table. Report accuracy, macro precision/recall/F1,
weighted F1, all per-class metrics, labeled confusion matrices, multiclass OVR
ROC-AUC, log loss, dropout PR-AUC/precision/recall and calibration diagnostics.
Only selected stage winners become deployment artifacts; training does not
activate them.

Explanations use the actual calibrated model's P(Dropout). Single-feature
reference perturbation replaces an observed value by a fitting-partition median
or mode and records the signed probability difference, observed/reference
values, model version and method. It is neither SHAP nor a causal effect;
correlated features and implausible reference combinations limit interpretation.

## Actual training and model selection

The pipeline was executed on the real UCI 697 extract, with six randomized configurations per family and five stratified folds (180 candidate-fold fits across two stages). Shared partitions contain 2,123 fitting/search rows, 708 probability-calibration rows, 708 risk-threshold rows and 885 final-test rows. Training completed for all six candidates; both winners were frozen before any final-test evaluation. The final-test sample has 284 Dropout, 159 Enrolled and 442 Graduate rows. All values below come from generated registry records, rather than illustrative or synthetic results.

Run from `backend`, with the exact pinned Python environment:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='2'
$env:MKL_NUM_THREADS='1'
..\.venv\Scripts\python.exe -m app.ml.outcomes.training --csv ../.venv/b1-data/uci697.csv --jobs 2 --iterations 6
```

The training command refuses existing output version directories. Do not rerun it against these immutable versions. The source cache is ignored; the two compressed deployment artifacts and their complete audited registries are included in this branch.

| Stage | Algorithm | CV score | Accuracy | Macro precision | Macro recall | Macro F1 | Weighted F1 | OVR ROC-AUC | Log loss | Dropout PR-AUC | Dropout recall | Dropout precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ENROLLMENT | Logistic Regression | 0.647545 | 0.642938 | 0.541572 | 0.517802 | 0.501778 | 0.599281 | 0.749616 | 0.830586 | 0.719570 | 0.609155 | 0.670543 |
| ENROLLMENT | Random Forest **winner** | 0.654292 | 0.630508 | 0.542093 | 0.510430 | 0.483237 | 0.582378 | 0.750389 | 0.840824 | 0.711403 | 0.661972 | 0.610390 |
| ENROLLMENT | XGBoost | 0.639118 | 0.625989 | 0.522681 | 0.507748 | 0.490331 | 0.585262 | 0.760645 | 0.835630 | 0.711926 | 0.619718 | 0.624113 |
| FIRST_SEMESTER | Logistic Regression **winner** | 0.764465 | 0.742373 | 0.671239 | 0.621169 | 0.609219 | 0.703917 | 0.851886 | 0.653109 | 0.854348 | 0.795775 | 0.738562 |
| FIRST_SEMESTER | Random Forest | 0.757775 | 0.716384 | 0.640269 | 0.617076 | 0.619765 | 0.697841 | 0.853450 | 0.660923 | 0.830420 | 0.704225 | 0.724638 |
| FIRST_SEMESTER | XGBoost | 0.763766 | 0.733333 | 0.662278 | 0.646006 | 0.649751 | 0.721365 | 0.864875 | 0.650517 | 0.844347 | 0.739437 | 0.742049 |

The enrollment forest's CV score 0.654292 exceeds Logistic Regression's 0.647545 and XGBoost's 0.639118. Its balanced class weighting improves the predeclared dropout-oriented CV objective despite lower overall accuracy. First-semester Logistic Regression scores 0.764465 versus XGBoost 0.763766 and Random Forest 0.757775; its greater CV dropout recall/precision wins the frozen score despite XGBoost's greater macro F1. The margin is small and is not evidence of definitive algorithm superiority. Final-test results did not change these choices.

Logistic Regression searched unweighted/balanced weights; the first-semester winner is unweighted with C=0.05. Enrollment's forest uses balanced weights, 250 trees, depth 16 and minimum leaf size 6. XGBoost searched unweighted/balanced fold-local sample weighting with `multi:softprob`, three classes, histogram trees and one estimator worker. The small bounded search is a reproducible benchmark, not exhaustive optimization.

## Actual risk calibration and artifacts

Sigmoid one-vs-rest calibration uses a frozen estimator and a separate 708-row development partition. Risk boundaries use another 708 rows, including 228 dropout cases. LOW means P(Dropout) < low threshold; MEDIUM means low <= probability < high; HIGH means probability >= high. The recall targets describe the threshold boundaries, whereas dropout precision/recall in the comparative table describe three-class argmax predictions.

| Stage/version | LOW boundary | HIGH boundary | LOW recall / precision | HIGH recall / precision |
| --- | --- | --- | --- | --- |
| enrollment-outcome-v1 | 0.1663330378872195 | 0.3198928692997696 | 0.903509 / 0.430063 | 0.701754 / 0.565371 |
| first-semester-outcome-v1 | 0.18210779379857042 | 0.56377401368663 | 0.903509 / 0.543536 | 0.701754 / 0.824742 |

- `enrollment-outcome-v1`: Random Forest, `uci697-enrollment-outcome-v1`, 21 ordered features; artifact SHA-256 `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602`.

- `first-semester-outcome-v1`: Logistic Regression, `uci697-first-semester-outcome-v1`, 27 ordered features; artifact SHA-256 `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81`.

Both stages maintain unrounded probabilities in stable DROPOUT/ENROLLED/GRADUATE order. Float32 candidate outputs use a 1e-6 normalization tolerance; calibrated deployed outputs are float64. The new verifier checks the artifact bytes and six canonical JSON registry hashes before joblib deserialization, then verifies stage/schema/class encoding, split hashes, calibration/selection/evaluation consistency, estimator settings, reference values, runtime versions and real probe inference. Model paths are trusted local configuration; requests cannot supply pickle paths. Manifests establish integrity against the trusted checkout and are not signed attestations against an attacker who controls the checkout.

Runtime versions: Python 3.11.9, numpy 2.4.6, pandas 2.3.3, scipy 1.17.1, scikit-learn 1.7.2, joblib 1.6.0 and XGBoost 3.2.0. Artifacts require this pinned environment. The Docker runtime verifies legacy and both B1 artifacts during build.

```powershell
python -m app.ml.deployment verify
python -m app.ml.outcomes.deployment verify
python -m app.ml.outcomes.deployment verify --stage ENROLLMENT
python -m app.ml.outcomes.deployment install --stage ENROLLMENT --source <trusted-model.joblib> --root <trusted-ml-root>
```

`ML_OUTCOME_ROOT` configures the new trusted root, whose `model_registry/<version>` and `artifacts/<version>/model.joblib` layout is fixed. Offline installation verifies a staged local file before atomic replacement. The original A1 root/path settings and deployment command remain independent. A missing stage artifact, checksum mismatch or incompatible environment causes an explicit unavailable/error state; it never triggers legacy fallback.

## Ordered stage contracts

### ENROLLMENT

Schema `uci697-enrollment-outcome-v1`:

```text
marital_status_code
application_mode_code
application_order
course_code
daytime_evening_attendance
previous_qualification_code
previous_qualification_grade
nationality_code
mother_qualification_code
father_qualification_code
mother_occupation_code
father_occupation_code
admission_grade
displaced
educational_special_needs
debtor
tuition_fees_up_to_date
gender_code
scholarship_holder
age_at_enrollment
international_student
```

### FIRST_SEMESTER

Schema `uci697-first-semester-outcome-v1`:

```text
marital_status_code
application_mode_code
application_order
course_code
daytime_evening_attendance
previous_qualification_code
previous_qualification_grade
nationality_code
mother_qualification_code
father_qualification_code
mother_occupation_code
father_occupation_code
admission_grade
displaced
educational_special_needs
debtor
tuition_fees_up_to_date
gender_code
scholarship_holder
age_at_enrollment
international_student
first_semester_credited_units
first_semester_enrolled_units
first_semester_evaluations
first_semester_approved_units
first_semester_average_grade
first_semester_without_evaluations
```

## Migration and lifecycle

Revision `20261011_0010`, after `20261011_0009`, adds stage and target type defaults FIRST_SEMESTER/BINARY_DROPOUT to existing models/predictions. Nullable `predicted_outcome` and `class_probabilities` remain null for binary rows. The original student/model/creator IDs, probability, risk, feature snapshot, explanation and timestamp fields are retained. Historical active models receive an additive MIGRATED_ACTIVE audit event; their IDs and active flags stay intact.

Active model uniqueness is scoped to `(prediction_stage, model_target_type)`. A composite foreign key prevents predictions from referencing a model belonging to another stage or target type. PostgreSQL checks exact probability keys, numeric values/range, normalization, P(Dropout) equality, argmax outcome and binary/multiclass field compatibility. The migration freezes its SQL constraint rather than importing future application code. Legacy-only rollback preserves the prior rows; rollback refuses when B1 multiclass models exist rather than dropping academic data.

Startup/catalog synchronization registers new models inactive. System Admin validation requires a real stage-ready student and fresh artifact verification. It executes actual prediction insertion and the existing warning transaction inside a savepoint, rolls them back, and records checksum, actor, student, time and integration results in `model_validations`. Activation re-verifies the exact artifact and requires a matching successful validation. It changes only the selected stage/target scope and appends `model_activation_events`. PostgreSQL advisory locks serialize registration/activation, with a unique index as a second guard. Validation does not add academic predictions or warnings; training and startup do not authorize activation. Current B1 support intentionally accepts only the two frozen registered new versions.

Warnings continue to use the saved risk tier, including MEDIUM/HIGH when the most likely class is ENROLLED. Stage changes append predictions/warnings and preserve confirmed/dismissed reviews, interventions and follow-ups. The dossier shows warning history with each warning's own model and stage, and shows nondismissed warnings across stages.

## API contracts and authorization

All paths below use `/api/v1`. Existing read roles remain System Admin, Academic Admin and Academic Advisor. Only Academic Admin executes single/batch predictions; only System Admin validates/activates models. Normal authentication, forced password-change and existing structured `{error:{code,message,details}}` handling remain enforced.

| Contract | Behavior |
| --- | --- |
| GET `/students/{id}/prediction-readiness` | Without a stage, preserve the original 30-input DTO exactly. Optional `prediction_stage` returns the selected new stage readiness. |
| GET `/students/{id}/prediction-readiness/stages` | New `{legacy, stages}` result: both explicit stages, counts, missing/invalid feature reasons and ACTIVE/INACTIVE/UNAVAILABLE model status/version/error. |
| POST `/students/{id}/predictions` | Omitted stage runs the preserved binary v1. Explicit `prediction_stage=ENROLLMENT` or `FIRST_SEMESTER` runs the corresponding active multiclass model. Missing/invalid data or inactive/unavailable models fail explicitly. |
| POST `/predictions/batch` | Same stage selection and legacy omission semantics. Append predictions for ready students; skip missing/invalid students and report counts. No new deduplication/freshness behavior. |
| GET `/students/{id}/predictions` | Existing history/pagination plus optional stage and target-type filters. |
| GET `/predictions` | Existing filters plus optional `prediction_stage`, `model_target_type`; model version filter remains available. |
| GET `/predictions/{id}` | Detail retains snapshot/explanation; adds stage, target type, nullable multiclass fields and explicit `dropout_probability`. |
| GET `/models` | New catalog of legacy and both new models, activation/validation/artifact state, complete performance and selection/calibration metadata. |
| POST `/models/{version}/validate` | System Admin; body `{student_id}`. Requires complete inputs and fresh verified inference/persistence checks; saves validation only. |
| POST `/models/{version}/activate` | System Admin; requires successful checksum-matching validation and fresh verification; audited stage-scoped activation. |
| GET `/models/current`, `/models/current/performance` | Preserve the legacy binary contract. |

Prediction `probability` and `dropout_probability` both mean P(Dropout). Multiclass records expose descriptive `predicted_outcome` and three `class_probabilities`; binary records expose null for both. No automatic stage selection occurs in the API. The dossier presents explicit selection and initially selects the first ready stage; the modal identifies it before confirmation. Model Analytics separates new models/comparisons from labeled legacy metrics, and enables controls according to role and activation state.

Dashboard `prediction_scope=LEGACY_BINARY_FIRST_SEMESTER` explicitly scopes prediction coverage, risk distribution, threshold widgets and last-prediction time to v1. `support_scope=ALL_PREDICTION_STAGES` identifies warning/intervention/follow-up totals. Operational academic support can therefore include new stage warnings without presenting them as binary model risk statistics. Prediction lists and dossier histories include all stages with labels.

## Model interpretation and remaining limitations

The selected enrollment forest recognizes only 8 of 159 Enrolled cases (5.0% recall), and first-semester Logistic Regression only 23 of 159 (14.5%). The system returns real probabilities for this separate class, but its classification performance is weak. Fixed sigmoid calibration does not guarantee well-calibrated class probabilities everywhere, can change argmax outcomes, and does not imply that ECE improves for every model. Preserve all before/after diagnostics and use human review; do not retune on this final test.

The UCI benchmark provides no institutional validation, external/temporal cohort assessment, local recalibration, fairness validation or supervisor approval for this new thesis scope. Financial/scholarship enrollment timing and macroeconomic exclusion are documented assumptions. A local institution must validate collection timing and outcomes before operational use. Existing stored grades use two decimal places (Numeric(8,2)); the first-semester regression fixture separately records genuine source-row and persisted-input inference values. Model uncertainty, small score margins, population shifts and correlated/reference perturbations limit generalization and explanation.

Probability calibration follows [scikit-learn 1.7 CalibratedClassifierCV/FrozenEstimator](https://scikit-learn.org/1.7/modules/generated/sklearn.calibration.CalibratedClassifierCV.html). Multiclass objective follows [XGBoost parameters](https://xgboost.readthedocs.io/en/stable/parameter.html). No automated intervention decisions, B2 batch optimization or prediction invalidation are introduced.

## Delivery verification (13 October 2026)

The completed branch was verified with the pinned Python environment and a
dedicated PostgreSQL 18 cluster on port 55449. It used randomly named databases
and test schemas, plus separate disposable browser/container databases. The
normal development database was not migrated, reset or used for destructive
tests. The new models remain inactive by default; activation during verification
occurred only in disposable databases.

| Check | Actual result |
| --- | --- |
| Complete backend suite with all PostgreSQL and real-model flags enabled | **263 passed, 0 skipped**, 198.27 seconds |
| PostgreSQL integration subset (B1, A2 users, staged imports, A1 deployment) | **26 passed**, 40.01 seconds |
| Focused B1 ML checks after audit-consistency hardening | **20 passed**, 8.22 seconds |
| Alembic heads | Single head `20261011_0010` |
| Original A1 deployment verifier | Verified `dropout-logistic-regression-v1` |
| B1 deployment verifier | Both stage artifacts verified with the SHA-256 values recorded above |
| Real UCI training reproduction | All six searches rerun in an isolated output root; exact same winner artifacts, thresholds, scientific metadata and evaluations |
| Frontend `npm run typecheck` | Passed |
| Frontend `npm run build` | Passed; all 14 pages generated |
| Browser, production frontend and real API | Validation/activation, missing-semester rejection, enrollment, semester record entry, reassessment, stage history, retained enrollment warning and legacy-only detail passed |
| Responsive/themes | Desktop and 390 px mobile inspected; content width 390 px; light/dark and System following both emulated preferences passed |
| Docker runtime build | `zak-b1-verification` built; build-time verification loaded legacy and both B1 artifacts |
| Docker API against disposable PostgreSQL | Startup migration, bootstrap/password change, RBAC, inactive registration, validation/activation, both stage predictions, legacy inference and three-entry history passed |
| Git compatibility | No diff in v1 artifact contracts, original training code, runtime, deployment verifier or `dropout-risk-v1` registry; local/remote main refs unchanged |

The final backend suite was executed from `backend` with
`RUN_MODEL_INTEGRATION=1` and all four dedicated PostgreSQL URL variables:
`MODEL_TEST_DATABASE_URL`, `DUAL_STAGE_TEST_DATABASE_URL`,
`STAGED_IMPORT_TEST_DATABASE_URL`, and `USER_MANAGEMENT_TEST_DATABASE_URL`.
All tests ran; mock-only results were not substituted for artifact or PostgreSQL
checks. Coverage includes populated migration/legacy rollback, refusal of lossy
rollback, composite model-stage associations, invalid probability JSON, warning
review preservation, activation concurrency and real model regression fixtures.

The reproduction used the same documented seed, six configurations per family,
five folds and source CSV, with `--root ../.venv/b1-reproduction`. It did not
overwrite the deployed versions, change selection/calibration methods, optimize
against final-test metrics or retrain v1. Both reproduced joblib files matched
the deployed SHA-256 values byte for byte. Registry timestamps differ because
this was a separate run; all scientific records match.

Container inference for the same genuine UCI source-row inputs returned:

| Stage | Most likely outcome | P(Dropout) | P(Enrolled) | P(Graduate) | Risk |
| --- | --- | --- | --- | --- | --- |
| ENROLLMENT, without semester records | ENROLLED | 0.2497711730787302 | 0.44325227593179495 | 0.3069765509894749 | MEDIUM |
| FIRST_SEMESTER, after recording measured values | GRADUATE | 0.18011547285576907 | 0.17247123803895922 | 0.6474132891052717 | LOW |

The earlier enrollment warning remained in history after reassessment. Legacy
inference on the completed source-row inputs returned P(Dropout)
`0.3447925421468906`, with nullable multiclass fields and its original version.
The full PostgreSQL workflow additionally preserves a confirmed advisor review
across the stage transition.

The 232 backend warnings are the unchanged legacy perturbation's pandas dtype
deprecation and scikit-learn warnings for float32 candidate probability sums
within the documented 1e-6 tolerance. Browser inspection found no console errors;
Next.js emitted CSS-preload warnings. The production-browser run used
`npm run start`; Next.js advises the standalone server for deployment. The
backend Docker runtime and API were exercised, but a complete frontend/database
Compose stack was not launched. No institutional, temporal, fairness or
supervisor validation is claimed.

The verifier now also recomputes candidate selection scores/eligibility and
checks that the development-selected winner agrees with its hyperparameters,
final-test metrics and probability-calibration records. Tests reject inconsistent
audit records even when their document hashes have been recomputed; immutable
artifact manifests were not changed.

The exact changed-file inventory is in `docs/phase-b1-changed-files.txt`.

## Full candidate evaluation records

### ENROLLMENT: Logistic Regression

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| DROPOUT | 0.670543 | 0.609155 | 0.638376 | 284 |
| ENROLLED | 0.300000 | 0.075472 | 0.120603 | 159 |
| GRADUATE | 0.654174 | 0.868778 | 0.746356 | 442 |

Confusion matrix, actual rows / predicted columns, order DROPOUT, ENROLLED, GRADUATE:

```text
[173, 14, 97]
[41, 12, 106]
[44, 14, 384]
```

Final-test multiclass Brier: 0.483993; dropout Brier: 0.152697; dropout ECE (10 equal-width bins): 0.034403. Full reliability-bin counts, means and observed rates are in `evaluation.json`.

| Threshold partition diagnostic | Before sigmoid | After sigmoid |
| --- | --- | --- |
| Multiclass Brier | 0.456947 | 0.460112 |
| Dropout Brier | 0.151470 | 0.152068 |
| Dropout ECE | 0.029535 | 0.040961 |

Selected hyperparameters: `{"model__C": 0.2, "model__class_weight": null}`.

### ENROLLMENT: Random Forest

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| DROPOUT | 0.610390 | 0.661972 | 0.635135 | 284 |
| ENROLLED | 0.363636 | 0.050314 | 0.088398 | 159 |
| GRADUATE | 0.652252 | 0.819005 | 0.726179 | 442 |

Confusion matrix, actual rows / predicted columns, order DROPOUT, ENROLLED, GRADUATE:

```text
[188, 7, 89]
[47, 8, 104]
[73, 7, 362]
```

Final-test multiclass Brier: 0.489771; dropout Brier: 0.156314; dropout ECE (10 equal-width bins): 0.037054. Full reliability-bin counts, means and observed rates are in `evaluation.json`.

| Threshold partition diagnostic | Before sigmoid | After sigmoid |
| --- | --- | --- |
| Multiclass Brier | 0.522419 | 0.475155 |
| Dropout Brier | 0.156993 | 0.154188 |
| Dropout ECE | 0.055943 | 0.043967 |

Selected hyperparameters: `{"model__class_weight": "balanced", "model__max_depth": 16, "model__min_samples_leaf": 6, "model__n_estimators": 250}`.

### ENROLLMENT: XGBoost

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| DROPOUT | 0.624113 | 0.619718 | 0.621908 | 284 |
| ENROLLED | 0.292683 | 0.075472 | 0.120000 | 159 |
| GRADUATE | 0.651246 | 0.828054 | 0.729084 | 442 |

Confusion matrix, actual rows / predicted columns, order DROPOUT, ENROLLED, GRADUATE:

```text
[176, 14, 94]
[45, 12, 102]
[61, 15, 366]
```

Final-test multiclass Brier: 0.487752; dropout Brier: 0.155975; dropout ECE (10 equal-width bins): 0.029359. Full reliability-bin counts, means and observed rates are in `evaluation.json`.

| Threshold partition diagnostic | Before sigmoid | After sigmoid |
| --- | --- | --- |
| Multiclass Brier | 0.469827 | 0.470683 |
| Dropout Brier | 0.153983 | 0.154547 |
| Dropout ECE | 0.030360 | 0.021277 |

Selected hyperparameters: `{"model__learning_rate": 0.1, "model__max_depth": 4, "model__n_estimators": 120, "model__reg_lambda": 1.0, "model__weight_strategy": null}`.

### FIRST_SEMESTER: Logistic Regression

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| DROPOUT | 0.738562 | 0.795775 | 0.766102 | 284 |
| ENROLLED | 0.511111 | 0.144654 | 0.225490 | 159 |
| GRADUATE | 0.764045 | 0.923077 | 0.836066 | 442 |

Confusion matrix, actual rows / predicted columns, order DROPOUT, ENROLLED, GRADUATE:

```text
[226, 13, 45]
[55, 23, 81]
[25, 9, 408]
```

Final-test multiclass Brier: 0.364593; dropout Brier: 0.109711; dropout ECE (10 equal-width bins): 0.057253. Full reliability-bin counts, means and observed rates are in `evaluation.json`.

| Threshold partition diagnostic | Before sigmoid | After sigmoid |
| --- | --- | --- |
| Multiclass Brier | 0.363943 | 0.370921 |
| Dropout Brier | 0.107668 | 0.110584 |
| Dropout ECE | 0.034863 | 0.049651 |

Selected hyperparameters: `{"model__C": 0.05, "model__class_weight": null}`.

### FIRST_SEMESTER: Random Forest

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| DROPOUT | 0.724638 | 0.704225 | 0.714286 | 284 |
| ENROLLED | 0.431579 | 0.257862 | 0.322835 | 159 |
| GRADUATE | 0.764591 | 0.889140 | 0.822176 | 442 |

Confusion matrix, actual rows / predicted columns, order DROPOUT, ENROLLED, GRADUATE:

```text
[200, 34, 50]
[47, 41, 71]
[29, 20, 393]
```

Final-test multiclass Brier: 0.374245; dropout Brier: 0.120717; dropout ECE (10 equal-width bins): 0.040700. Full reliability-bin counts, means and observed rates are in `evaluation.json`.

| Threshold partition diagnostic | Before sigmoid | After sigmoid |
| --- | --- | --- |
| Multiclass Brier | 0.373973 | 0.361803 |
| Dropout Brier | 0.111532 | 0.104999 |
| Dropout ECE | 0.071330 | 0.045028 |

Selected hyperparameters: `{"model__class_weight": null, "model__max_depth": 16, "model__min_samples_leaf": 1, "model__n_estimators": 250}`.

### FIRST_SEMESTER: XGBoost

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| DROPOUT | 0.742049 | 0.739437 | 0.740741 | 284 |
| ENROLLED | 0.451327 | 0.320755 | 0.375000 | 159 |
| GRADUATE | 0.793456 | 0.877828 | 0.833512 | 442 |

Confusion matrix, actual rows / predicted columns, order DROPOUT, ENROLLED, GRADUATE:

```text
[210, 32, 42]
[49, 51, 59]
[24, 30, 388]
```

Final-test multiclass Brier: 0.368532; dropout Brier: 0.116886; dropout ECE (10 equal-width bins): 0.038385. Full reliability-bin counts, means and observed rates are in `evaluation.json`.

| Threshold partition diagnostic | Before sigmoid | After sigmoid |
| --- | --- | --- |
| Multiclass Brier | 0.354802 | 0.361013 |
| Dropout Brier | 0.105265 | 0.107003 |
| Dropout ECE | 0.020575 | 0.039538 |

Selected hyperparameters: `{"model__learning_rate": 0.1, "model__max_depth": 4, "model__n_estimators": 120, "model__reg_lambda": 1.0, "model__weight_strategy": null}`.
