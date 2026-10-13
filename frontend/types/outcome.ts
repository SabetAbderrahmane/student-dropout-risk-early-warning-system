export type PredictionStage = "ENROLLMENT" | "FIRST_SEMESTER";
export type ModelTargetType = "BINARY_DROPOUT" | "MULTICLASS_OUTCOME";
export type AcademicOutcome = "DROPOUT" | "ENROLLED" | "GRADUATE";
export type StageSelection = "LEGACY" | PredictionStage;
export type ClassProbabilities = Record<AcademicOutcome, number>;
export interface StageReadiness {
  prediction_stage: PredictionStage;
  status: "READY" | "NOT_READY";
  feature_status: "READY" | "NOT_READY";
  required_feature_count: number;
  available_feature_count: number;
  missing_features: string[];
  invalid_features: Record<string, string>;
  model_status: "ACTIVE" | "INACTIVE" | "UNAVAILABLE";
  model_version: string;
  model_error: string | null;
}
export interface MulticlassMetrics {
  accuracy: number;
  macro_precision: number;
  macro_recall: number;
  macro_f1: number;
  weighted_f1: number;
  dropout_pr_auc: number;
  dropout_precision: number;
  dropout_recall: number;
  multiclass_roc_auc_ovr: number | null;
  log_loss: number;
  sample_size: number;
  per_class: Record<
    AcademicOutcome,
    { precision: number; recall: number; f1: number; support: number }
  >;
  confusion_matrix: {
    labels: AcademicOutcome[];
    rows_actual_columns_predicted: number[][];
  };
  calibration: {
    multiclass_brier_score: number;
    dropout_brier_score: number;
    dropout_ece_10_bins: number;
  };
}
export interface CandidateComparison {
  name: string;
  selection_score: number;
  meets_constraints: boolean;
  cv_metrics: Record<string, number>;
  final_test: MulticlassMetrics;
}
export interface ModelCatalogEntry {
  id: string;
  name: string;
  version: string;
  prediction_stage: PredictionStage;
  model_target_type: ModelTargetType;
  feature_schema_version: string;
  feature_count: number;
  class_labels: string[];
  trained_at: string;
  low_threshold: number;
  high_threshold: number;
  is_active: boolean;
  artifact_available: boolean;
  availability_error: string | null;
  artifact_sha256: string | null;
  validation_id: string | null;
  validated_at: string | null;
  evaluation: {
    final_test: MulticlassMetrics | Record<string, unknown>;
    candidate_comparison?: CandidateComparison[];
  };
  selection: { method: string; reason: string; score?: number };
  probability_calibration: { method: string; sample_size: number } | null;
  threshold_calibration: Record<string, unknown>;
  explanation_method: string;
}
export interface ModelCatalog {
  items: ModelCatalogEntry[];
}
export const stageLabel = (stage: StageSelection) =>
  stage === "LEGACY"
    ? "Legacy binary · First semester"
    : stage === "ENROLLMENT"
      ? "Enrollment"
      : "First semester";
