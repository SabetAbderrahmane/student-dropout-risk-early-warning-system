import type { RiskLevel } from "./registry";
import type { WarningPriority, WarningReview } from "./dashboard";

export type WarningReviewState = "PENDING_REVIEW" | "CONFIRMED" | "DISMISSED";
export type WarningSort =
  | "priority"
  | "created_at"
  | "probability"
  | "risk_level"
  | "review_state"
  | "student_number";
export interface WarningParams {
  page: number;
  page_size: number;
  search?: string;
  risk_level?: RiskLevel;
  review_state?: WarningReviewState;
  priority?: WarningPriority;
  assigned_to?: string;
  sort?: WarningSort;
  order?: "asc" | "desc";
}
export interface ExplanationFactor {
  feature: string;
  label: string;
  value: number;
  contribution: number;
}
export interface WarningRow {
  id: string;
  student_id: string;
  student_number: string;
  student_name: string;
  prediction_id: string;
  probability: number;
  risk_level: RiskLevel;
  priority: WarningPriority;
  review_state: WarningReviewState;
  assigned_advisor: { id: string; full_name: string } | null;
  predicted_at: string;
  created_at: string;
  updated_at: string;
  top_explanation_factors: ExplanationFactor[];
}
export interface WarningPage {
  items: WarningRow[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
export interface WarningDetail extends WarningRow {
  student: { id: string; student_number: string; name: string };
  model_version: string;
  prediction_explanation: ExplanationFactor[];
  review_history: WarningReview[];
}
export interface StudentPrediction {
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
export interface StudentPredictionPage {
  items: StudentPrediction[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
