# first-semester-outcome-v1 actual training report

Trained 2026-10-11T17:03:32.945913+00:00 on UCI 697 (CC BY 4.0); canonical source SHA-256 `4b15c8e0b1fc9ea1e7994caaff47db72c07e0049bf9e47758aa53c2fc7fd6376`.

Stage: FIRST_SEMESTER; schema: uci697-first-semester-outcome-v1; ordered features: 27; target Dropout=0, Enrolled=1, Graduate=2. Winner: Logistic Regression; CV selection score 0.764465.

Shared seed-42 frozen partitions: fitting 2123, probability calibration 708, threshold calibration 708, final test 885. Search: six configurations per family, five fold-local stratified CV folds. Selection accounts for dropout recall/PR-AUC/precision and macro F1; final test was scored after choices froze. See the phase report for source timing, limitations and deployment/activation rules.

| Stage | Algorithm | CV score | Accuracy | Macro precision | Macro recall | Macro F1 | Weighted F1 | OVR ROC-AUC | Log loss | Dropout PR-AUC | Dropout recall | Dropout precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIRST_SEMESTER | Logistic Regression **winner** | 0.764465 | 0.742373 | 0.671239 | 0.621169 | 0.609219 | 0.703917 | 0.851886 | 0.653109 | 0.854348 | 0.795775 | 0.738562 |
| FIRST_SEMESTER | Random Forest | 0.757775 | 0.716384 | 0.640269 | 0.617076 | 0.619765 | 0.697841 | 0.853450 | 0.660923 | 0.830420 | 0.704225 | 0.724638 |
| FIRST_SEMESTER | XGBoost | 0.763766 | 0.733333 | 0.662278 | 0.646006 | 0.649751 | 0.721365 | 0.864875 | 0.650517 | 0.844347 | 0.739437 | 0.742049 |

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

## Risk calibration

```json
{
  "calibration_source": "Disjoint development risk-threshold partition; not final test",
  "dropout_count": 228,
  "high_achieved_precision": 0.8247422680412371,
  "high_achieved_recall": 0.7017543859649122,
  "high_target_recall": 0.7,
  "high_threshold": 0.56377401368663,
  "low_achieved_precision": 0.5435356200527705,
  "low_achieved_recall": 0.9035087719298246,
  "low_target_recall": 0.9,
  "low_threshold": 0.18210779379857042,
  "method": "LOW largest threshold retaining >=90% dropout recall; HIGH maximum precision retaining >=70% recall and greater than LOW; no fallback",
  "model_version": "first-semester-outcome-v1",
  "sample_size": 708
}
```

Artifact SHA-256 `2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81`. This report summarizes the existing frozen JSON records; it does not retrain, regenerate or change the artifact/manifest. Registration is inactive until separate successful validation and explicit activation. UCI performance is not institutional validation or supervisor approval.
