import type {
  AcademicOutcome,
  ClassProbabilities,
  ModelTargetType,
  PredictionStage,
  StageReadiness,
} from "./outcome";
import type { AssessmentFields, PredictionFreshnessFields } from "./assessment";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type WarningState =
  | "PENDING_REVIEW"
  | "CONFIRMED"
  | "DISMISSED"
  | "NONE";
export type InterventionState =
  | "PLANNED"
  | "IN_PROGRESS"
  | "ACTION_REQUIRED"
  | "COMPLETED"
  | "CANCELLED";
export type PredictionReadiness = "READY" | "NOT_READY";
export type RegistrySort =
  | "student_number"
  | "name"
  | "risk_probability"
  | "updated_at";
export interface StudentRegistryParams {
  page: number;
  page_size: 25 | 50 | 100;
  search?: string;
  course_code?: number;
  risk_level?: RiskLevel;
  current_risk?: RiskLevel | "NONE";
  assessment_state?: "CURRENT" | "REASSESSMENT_REQUIRED" | "NOT_ASSESSED";
  prediction_stage?: PredictionStage;
  stage_readiness?: PredictionReadiness;
  warning_state?: WarningState;
  intervention_state?: InterventionState;
  prediction_readiness?: PredictionReadiness;
  sort: RegistrySort;
  order: "asc" | "desc";
}
export interface CaseOwner {
  user_id: string;
  full_name: string;
}
export interface RegistryPrediction extends PredictionFreshnessFields {
  id: string;
  probability: number;
  risk_level: string;
  predicted_at: string;
  prediction_stage: PredictionStage;
  model_target_type: ModelTargetType;
  predicted_outcome: AcademicOutcome | null;
  class_probabilities: ClassProbabilities | null;
}
export interface RegistrySemester {
  average_grade: number;
  enrolled_units: number;
  approved_units: number;
  approval_rate: number | null;
}
export interface RegistryRow extends AssessmentFields {
  student_id: string;
  student_number: string;
  name: string;
  course: { code: number; label: string } | null;
  admission: { method: string; admission_grade: number } | null;
  semester_one: RegistrySemester | null;
  prediction_readiness: PredictionReadiness;
  latest_prediction: RegistryPrediction | null;
  latest_historical_prediction: RegistryPrediction | null;
  operational_prediction: RegistryPrediction | null;
  warning: { id: string; state: string; priority: string } | null;
  case_owner: CaseOwner | null;
  intervention: { id: string; status: string } | null;
  last_activity_at: string | null;
}
export interface RegistryPage {
  items: RegistryRow[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
export interface ProfilePrediction extends RegistryPrediction {
  model_version: string;
  explanation: Array<Record<string, unknown>>;
  feature_snapshot: Record<string, number>;
  explanation_method: string | null;
}
export interface ProfileWarning {
  id: string;
  prediction_id: string;
  risk_level: string;
  priority: string;
  review_state: string;
  assigned_advisor: CaseOwner | null;
  created_at: string;
  prediction_stage: PredictionStage;
  model_target_type: ModelTargetType;
  model_version: string | null;
  reviews: Array<{
    id: string;
    decision: string;
    note: string;
    reviewer: CaseOwner | null;
    reviewed_at: string;
  }>;
}
export interface ProfileIntervention {
  id: string;
  warning_id: string;
  type: string;
  title: string;
  priority: string;
  status: string;
  assigned_advisor: CaseOwner | null;
  start_date: string;
  target_date: string | null;
  created_at: string;
  completed_at: string | null;
  completion_outcome: string | null;
}
export interface ProfileFollowUp {
  id: string;
  intervention_id: string;
  scheduled_for: string;
  method: string;
  purpose: string;
  effective_status: string;
  outcome: string | null;
  assigned_advisor: CaseOwner | null;
  completed_at: string | null;
}
export interface StudentProfile extends AssessmentFields {
  stage_readiness: StageReadiness[];
  student: {
    id: string;
    student_number: string;
    name: string;
    gender: string | null;
    marital_status_code: number | null;
    nationality_code: number | null;
    displaced: number | null;
    educational_special_needs: number | null;
    debtor: number | null;
    tuition_fees_up_to_date: number | null;
    gender_code: number | null;
    scholarship_holder: number | null;
    age_at_enrollment: number | null;
    international_student: number | null;
  };
  admission: {
    admission_method: string;
    admission_grade: number;
    previous_qualification: string;
    previous_qualification_grade: number;
    application_mode_code: number | null;
    application_mode_label: string | null;
    application_order: number | null;
    course_code: number | null;
    course_label: string | null;
    daytime_evening_attendance: number | null;
    previous_qualification_code: number | null;
    previous_qualification_label: string | null;
    mother_qualification_code: number | null;
    father_qualification_code: number | null;
    mother_occupation_code: number | null;
    father_occupation_code: number | null;
    unemployment_rate: number | null;
    inflation_rate: number | null;
    gdp: number | null;
  } | null;
  semester_one:
    | (RegistrySemester & {
        credited_units: number;
        evaluations: number;
        without_evaluations: number | null;
      })
    | null;
  prediction_readiness: {
    status: PredictionReadiness;
    required_feature_count: number;
    available_feature_count: number;
    missing_features: string[];
  };
  latest_prediction: ProfilePrediction | null;
  latest_historical_prediction: ProfilePrediction | null;
  operational_prediction: ProfilePrediction | null;
  prediction_history: ProfilePrediction[];
  active_warning: ProfileWarning | null;
  warning_history: ProfileWarning[];
  open_warnings: ProfileWarning[];
  interventions: ProfileIntervention[];
  follow_ups: ProfileFollowUp[];
  timeline: Array<{
    type: string;
    occurred_at: string;
    title: string;
    summary: string;
    entity_id: string;
  }>;
}
export type { ModelPerformance } from "./prediction";
