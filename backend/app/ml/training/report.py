"""Human-readable model-selection report rendering."""

from typing import Any


def render_report(metadata: dict[str, Any], evaluation: dict[str, Any]) -> str:
    lines = [
        "# Dropout Model Training Report",
        "",
        f"- Model: {metadata['model_name']} ({metadata['model_version']})",
        f"- Trained: {metadata['trained_at']}",
        f"- Dataset rows: {metadata['counts']['total']}",
        f"- Development/final test: {metadata['counts']['development']} / {metadata['counts']['final_test']}",
        "",
        "## Model selection",
        "",
        "Selection score = 0.50 recall + 0.30 PR-AUC + 0.20 precision. ",
        "Search refitting uses PR-AUC; all reported development results use the same ",
        "shuffled 5-fold stratified CV with seed 42.",
        "",
        "| Candidate | Recall | Precision | F1 | ROC-AUC | PR-AUC | Selection score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for candidate in evaluation["development_model_selection"]:
        metrics = candidate["cv_metrics"]
        lines.append(
            f"| {candidate['name']} | {metrics['recall']:.4f} | "
            f"{metrics['precision']:.4f} | {metrics['f1']:.4f} | "
            f"{metrics['roc_auc']:.4f} | {metrics['pr_auc']:.4f} | "
            f"{candidate['selection_score']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"Selected **{metadata['model_name']}** because it had the highest locked "
            "recall-weighted selection score, with PR-AUC and precision as guardrails.",
            "",
            "## Threshold calibration",
            "",
            metadata["thresholds"]["method"],
            "",
            f"- LOW: p < {metadata['thresholds']['low_threshold']:.6f}",
            f"- MEDIUM: {metadata['thresholds']['low_threshold']:.6f} <= p < {metadata['thresholds']['high_threshold']:.6f}",
            f"- HIGH: p >= {metadata['thresholds']['high_threshold']:.6f}",
            "",
            "## Untouched final-test evaluation",
            "",
        ]
    )
    final = metadata["final_test_metrics"]
    for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "brier_score"):
        lines.append(f"- {key}: {final[key]:.6f}")
    lines.append(f"- confusion_matrix: {final['confusion_matrix']}")
    lines.extend(["", "## Global feature importance", ""])
    for row in evaluation["global_feature_importance"][:15]:
        lines.append(f"- {row['feature']}: {row['importance']:.6f}")
    lines.extend(["", "## Explainability", "", metadata["explanation_method"], ""])
    return "\n".join(lines)
