export interface DashboardOverview {
  prediction_scope: "LEGACY_BINARY_FIRST_SEMESTER";
  support_scope: "ALL_PREDICTION_STAGES";
  students: {
    total: number;
    prediction_ready: number;
    with_latest_prediction: number;
  };
  risk_distribution: { low: number; medium: number; high: number };
  warnings: {
    active: number;
    pending_review: number;
    confirmed: number;
    dismissed: number;
  };
  interventions: {
    active: number;
    planned: number;
    in_progress: number;
    action_required: number;
    completed: number;
  };
  follow_ups: { due_today: number; overdue: number };
  model: {
    version: string | null;
    name: string | null;
    trained_at: string | null;
    low_threshold: number | null;
    high_threshold: number | null;
  };
  data_freshness: {
    last_import_at: string | null;
    last_prediction_at: string | null;
  };
  warning_activity: Array<{
    date: string;
    created: number;
    confirmed: number;
    dismissed: number;
  }>;
  intervention_activity: Array<{
    date: string;
    created: number;
    completed: number;
  }>;
  attention_students: AttentionStudent[];
}

export interface AttentionStudent {
  student_id: string;
  student_number: string;
  name: string;
  probability: number;
  risk_level: string;
  warning_id: string;
  priority: string;
  review_state: string;
  assigned_advisor: { user_id: string; full_name: string } | null;
  predicted_at: string;
  top_explanation_factors: Array<Record<string, unknown>>;
}

export type ReviewDecision = "CONFIRMED" | "DISMISSED";
export interface ReviewWarningInput {
  decision: ReviewDecision;
  note: string;
}
export interface WarningReview {
  id: string;
  warning_id: string;
  reviewer_id: string;
  reviewer_name: string;
  decision: ReviewDecision;
  note: string;
  reviewed_at: string;
}
export interface WarningReviewReceipt {
  id: string;
  review_state: string;
  review_history: WarningReview[];
}
export type InterventionType =
  | "ACADEMIC_TUTORING"
  | "ACADEMIC_ADVISING"
  | "STUDY_PERFORMANCE_PLAN"
  | "FINANCIAL_SUPPORT_REFERRAL"
  | "ADMINISTRATIVE_SUPPORT_REFERRAL"
  | "OTHER";
export type WarningPriority = "P1_URGENT" | "P2_ELEVATED" | "P3_STANDARD";
export interface InterventionInput {
  student_id: string;
  warning_id: string;
  type: InterventionType;
  title: string;
  description: string;
  priority: WarningPriority;
  assigned_to: string;
  start_date: string;
  target_date?: string | null;
}
/** Only the creation receipt is needed here; casework detail belongs to its own screen. */
export interface InterventionReceipt {
  id: string;
  title: string;
}
export interface BatchPredictionResponse {
  assessed: number;
  skipped_not_ready: number;
  created_predictions: number;
  created_warnings: number;
  model_version: string;
  completed_at: string;
}
