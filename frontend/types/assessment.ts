import type { ModelTargetType, PredictionStage } from "./outcome";

export type PredictionFreshness = "CURRENT" | "NOT_SELECTED" | "INPUTS_CHANGED" | "INPUTS_INCOMPLETE" | "MODEL_SUPERSEDED" | "MODEL_UNAVAILABLE" | "STAGE_REASSESSMENT_REQUIRED" | "NO_PREDICTION";
export interface PredictionFreshnessFields {
  prediction_freshness: PredictionFreshness;
  is_operational_current: boolean;
  requires_reassessment: boolean;
  changed_features: string[];
  missing_features: string[];
}
export interface AssessmentFields {
  assessment_as_of: string;
  assessment_status: PredictionFreshness;
  reassessment_required: boolean;
  recommended_stage: PredictionStage;
  recommended_target_type: ModelTargetType;
  recommended_model_version: string | null;
  recommended_model_available: boolean;
  enrollment_ready: boolean;
  first_semester_ready: boolean;
  legacy_ready: boolean;
}
