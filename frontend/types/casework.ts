import type { InterventionType, WarningPriority } from "./dashboard";
import type { InterventionState } from "./registry";
import type { WarningReviewState } from "./warning";

export type InterventionOutcome =
  | "SUPPORT_COMPLETED"
  | "GOALS_PARTIALLY_MET"
  | "REFERRED_FOR_ADDITIONAL_SUPPORT"
  | "STUDENT_UNRESPONSIVE"
  | "OTHER";
export type FollowUpMethod =
  "IN_PERSON" | "PHONE" | "EMAIL" | "ONLINE_MEETING" | "OTHER";
export type FollowUpOutcome =
  | "COMPLETED"
  | "PROGRESS_OBSERVED"
  | "NO_RESPONSE"
  | "RESCHEDULED"
  | "ESCALATION_REQUIRED"
  | "INTERVENTION_COMPLETED";
export interface InterventionNote {
  id: string;
  intervention_id: string;
  author_id: string;
  author_name: string;
  note: string;
  created_at: string;
}
export interface FollowUpDetail {
  id: string;
  intervention_id: string;
  warning_id: string;
  prediction_id: string;
  student: { id: string; student_number: string; name: string };
  assigned_advisor: { id: string; full_name: string };
  scheduled_for: string;
  method: FollowUpMethod;
  purpose: string;
  stored_status: "SCHEDULED" | "COMPLETED" | "CANCELLED";
  status: "SCHEDULED" | "DUE" | "OVERDUE" | "COMPLETED" | "CANCELLED";
  effective_status: FollowUpDetail["status"];
  outcome: FollowUpOutcome | null;
  notes: string | null;
  completed_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}
export interface InterventionDetail {
  id: string;
  student: FollowUpDetail["student"];
  warning: {
    id: string;
    prediction_id: string;
    review_state: WarningReviewState;
  };
  type: InterventionType;
  title: string;
  description: string;
  priority: WarningPriority;
  status: InterventionState;
  assigned_advisor: { id: string; full_name: string };
  start_date: string;
  target_date: string | null;
  completed_at: string | null;
  completion_outcome: InterventionOutcome | null;
  completion_notes: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  notes: InterventionNote[];
  follow_ups: FollowUpDetail[];
}
export interface InterventionUpdate {
  title?: string;
  description?: string;
  priority?: WarningPriority;
  assigned_to?: string;
  target_date?: string | null;
  status?: "IN_PROGRESS" | "ACTION_REQUIRED";
}
export interface FollowUpInput {
  scheduled_for: string;
  method: FollowUpMethod;
  purpose: string;
  assigned_to: string;
}
export interface FollowUpCompletion {
  outcome: FollowUpOutcome;
  notes: string;
  next_follow_up_at?: string | null;
}
