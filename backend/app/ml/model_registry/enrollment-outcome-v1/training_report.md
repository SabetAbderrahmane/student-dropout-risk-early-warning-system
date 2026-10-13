# enrollment-outcome-v1 actual training report

Trained 2026-10-11T17:03:32.113499+00:00 on UCI 697 (CC BY 4.0); canonical source SHA-256 `4b15c8e0b1fc9ea1e7994caaff47db72c07e0049bf9e47758aa53c2fc7fd6376`.

Stage: ENROLLMENT; schema: uci697-enrollment-outcome-v1; ordered features: 21; target Dropout=0, Enrolled=1, Graduate=2. Winner: Random Forest; CV selection score 0.654292.

Shared seed-42 frozen partitions: fitting 2123, probability calibration 708, threshold calibration 708, final test 885. Search: six configurations per family, five fold-local stratified CV folds. Selection accounts for dropout recall/PR-AUC/precision and macro F1; final test was scored after choices froze. See the phase report for source timing, limitations and deployment/activation rules.

| Stage | Algorithm | CV score | Accuracy | Macro precision | Macro recall | Macro F1 | Weighted F1 | OVR ROC-AUC | Log loss | Dropout PR-AUC | Dropout recall | Dropout precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ENROLLMENT | Logistic Regression | 0.647545 | 0.642938 | 0.541572 | 0.517802 | 0.501778 | 0.599281 | 0.749616 | 0.830586 | 0.719570 | 0.609155 | 0.670543 |
| ENROLLMENT | Random Forest **winner** | 0.654292 | 0.630508 | 0.542093 | 0.510430 | 0.483237 | 0.582378 | 0.750389 | 0.840824 | 0.711403 | 0.661972 | 0.610390 |
| ENROLLMENT | XGBoost | 0.639118 | 0.625989 | 0.522681 | 0.507748 | 0.490331 | 0.585262 | 0.760645 | 0.835630 | 0.711926 | 0.619718 | 0.624113 |

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

## Risk calibration

```json
{
  "calibration_source": "Disjoint development risk-threshold partition; not final test",
  "dropout_count": 228,
  "high_achieved_precision": 0.5653710247349824,
  "high_achieved_recall": 0.7017543859649122,
  "high_target_recall": 0.7,
  "high_threshold": 0.3198928692997696,
  "low_achieved_precision": 0.430062630480167,
  "low_achieved_recall": 0.9035087719298246,
  "low_target_recall": 0.9,
  "low_threshold": 0.1663330378872195,
  "method": "LOW largest threshold retaining >=90% dropout recall; HIGH maximum precision retaining >=70% recall and greater than LOW; no fallback",
  "model_version": "enrollment-outcome-v1",
  "sample_size": 708
}
```

Artifact SHA-256 `bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602`. This report summarizes the existing frozen JSON records; it does not retrain, regenerate or change the artifact/manifest. Registration is inactive until separate successful validation and explicit activation. UCI performance is not institutional validation or supervisor approval.
