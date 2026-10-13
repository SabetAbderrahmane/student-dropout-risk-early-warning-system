import { ApiError } from "./api";
import type {
  PredictionRow,
  GlobalFeatureImportance,
} from "@/types/prediction";
export function predictionError(caught: unknown): string {
  if (caught instanceof ApiError) {
    if (caught.status === 503)
      return `Model runtime unavailable. ${caught.message}`;
    if (caught.status === 403)
      return `Your account does not have permission to perform this action. ${caught.message}`;
    if (caught.status === 404)
      return `No model or prediction record is available. ${caught.message}`;
    return caught.message;
  }
  return caught instanceof Error
    ? caught.message
    : "Unable to complete this request. Please retry.";
}
function download(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportPredictionPage(rows: readonly PredictionRow[]): void {
  const cell = (value: string | number) => {
    const text = String(value);
    const safe = /^[=+@\-\t\r]/.test(text) ? `'${text}` : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const header = [
    "student_number",
    "student_name",
    "prediction_stage",
    "model_target_type",
    "predicted_outcome",
    "class_probabilities",
    "probability",
    "risk_level",
    "model_version",
    "predicted_at",
    "top_explanation_factors",
  ];
  const lines = rows.map((row) =>
    [
      row.student_number,
      row.student_name,
      row.prediction_stage,
      row.model_target_type,
      row.predicted_outcome ?? "",
      row.class_probabilities ? JSON.stringify(row.class_probabilities) : "",
      row.probability,
      row.risk_level,
      row.model_version,
      row.predicted_at,
      JSON.stringify(row.top_explanation_factors),
    ]
      .map(cell)
      .join(","),
  );
  download(
    "\uFEFF" + [header.join(","), ...lines].join("\r\n"),
    "predictions-current-page.csv",
    "text/csv;charset=utf-8",
  );
}
export function exportFeatureImportance(
  items: readonly GlobalFeatureImportance[],
): void {
  download(
    JSON.stringify(items, null, 2),
    "model-feature-importance.json",
    "application/json",
  );
}
