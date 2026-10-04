import type { RiskLevel } from "./registry";
import type { ExplanationFactor } from "./warning";
export interface PredictionParams {
  page: number;
  page_size: number;
  search?: string;
  risk_level?: RiskLevel;
  model_version?: string;
  student_id?: string;
  sort:
    | "predicted_at"
    | "probability"
    | "risk_level"
    | "student_number"
    | "model_version";
  order: "asc" | "desc";
}
export interface PredictionRow {
  id: string;
  student_id: string;
  student_number: string;
  student_name: string;
  probability: number;
  risk_level: RiskLevel;
  model_version: string;
  top_explanation_factors: ExplanationFactor[];
  predicted_at: string;
}
export interface PredictionPage {
  items: PredictionRow[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
export interface PredictionDetail extends PredictionRow {
  feature_snapshot: Record<string, number>;
  explanation_method: string;
  created_by: string | null;
}
export interface CurrentModel {
  id: string;
  name: string;
  version: string;
  trained_at: string;
  dataset: { name: string; dataset_id: number };
  feature_schema_version: string;
  low_threshold: number;
  high_threshold: number;
  artifact_available: boolean;
}
export interface GlobalFeatureImportance {
  feature: string;
  label: string;
  importance: number;
}
export interface ModelPerformance {
  evaluation_scope: "FINAL_TEST_SET";
  sample_size: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  pr_auc: number;
  brier_score: number;
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  global_feature_importance: GlobalFeatureImportance[];
}
