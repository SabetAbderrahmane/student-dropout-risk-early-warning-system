# Dropout Model Training Report

- Model: Logistic Regression (dropout-logistic-regression-v1)
- Trained: 2026-09-30T20:11:46.795527+00:00
- Dataset rows: 4424
- Development/final test: 3539 / 885

## Model selection

Selection score = 0.50 recall + 0.30 PR-AUC + 0.20 precision.
Search refitting uses PR-AUC; all reported development results use the same
shuffled 5-fold stratified CV with seed 42.

| Candidate | Recall | Precision | F1 | ROC-AUC | PR-AUC | Selection score |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.7916 | 0.7413 | 0.7652 | 0.9047 | 0.8590 | 0.8018 |
| Random Forest | 0.7159 | 0.7870 | 0.7493 | 0.8956 | 0.8447 | 0.7688 |
| XGBoost | 0.7643 | 0.7578 | 0.7606 | 0.9029 | 0.8557 | 0.7904 |

Selected **Logistic Regression** because it had the highest locked recall-weighted selection score, with PR-AUC and precision as guardrails.

## Threshold calibration

Development-set 5-fold out-of-fold predictions: low is the largest threshold retaining >=90% dropout recall; high maximizes precision while retaining >=70% dropout recall.

- LOW: p < 0.269495
- MEDIUM: 0.269495 <= p < 0.675301
- HIGH: p >= 0.675301

## Untouched final-test evaluation

- accuracy: 0.859887
- precision: 0.766667
- recall: 0.809859
- f1: 0.787671
- roc_auc: 0.913231
- pr_auc: 0.873827
- brier_score: 0.107212
- confusion_matrix: {'tp': 230, 'fp': 70, 'tn': 531, 'fn': 54}

## Global feature importance

- first_semester_approved_units: 0.618571
- first_semester_enrolled_units: 0.098268
- tuition_fees_up_to_date: 0.094428
- first_semester_credited_units: 0.034690
- course_code: 0.033337
- unemployment_rate: 0.015670
- age_at_enrollment: 0.013356
- mother_qualification_code: 0.013264
- mother_occupation_code: 0.013213
- application_mode_code: 0.012664
- father_occupation_code: 0.012214
- gender_code: 0.006041
- debtor: 0.005673
- father_qualification_code: 0.005393
- scholarship_holder: 0.005084

## Explainability

Model-agnostic single-feature reference perturbation: contribution is the change in dropout probability when one observed feature is replaced by its development-set median (numeric) or mode (categorical).
