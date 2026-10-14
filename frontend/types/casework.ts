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
export type FollowUpStatus = "SCHEDULED" | "COMPLETED" | "CANCELLED";
export type FollowUpEffectiveStatus = FollowUpStatus | "DUE" | "OVERDUE";
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
  revision: number;
  id: string;
  intervention_id: string;
  parent_status: InterventionState;
  parent_assigned_to: string;
  integrity_issues: string[];
  warning_id: string;
  prediction_id: string;
  student: { id: string; student_number: string; name: string };
  assigned_advisor: { id: string; full_name: string };
  scheduled_for: string;
  method: FollowUpMethod;
  purpose: string;
  stored_status: FollowUpStatus;
  status: FollowUpEffectiveStatus;
  effective_status: FollowUpDetail["status"];
  outcome: FollowUpOutcome | null;
  notes: string | null;
  completed_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}
export interface InterventionDetail {
  revision: number;
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
  expected_revision?: number;
  title?: string;
  description?: string;
  priority?: WarningPriority;
  assigned_to?: string;
  target_date?: string | null;
  status?: "IN_PROGRESS" | "ACTION_REQUIRED";
}
export interface FollowUpInput {
  expected_revision?: number;
  scheduled_for: string;
  method: FollowUpMethod;
  purpose: string;
  assigned_to: string;
}
export interface FollowUpCompletion {
  expected_revision?: number;
  outcome: FollowUpOutcome;
  notes: string;
  next_follow_up_at?: string | null;
}

export type InterventionRow = Omit<InterventionDetail, "notes" | "follow_ups">;
export interface CaseworkPage<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
export type InterventionPage = CaseworkPage<InterventionRow>;
export type FollowUpPage = CaseworkPage<FollowUpDetail>;
export interface InterventionParams {
  page: number;
  page_size: number;
  search?: string;
  status?: InterventionState;
  priority?: WarningPriority;
  type?: InterventionType;
  assigned_to?: string;
  student_id?: string;
  warning_id?: string;
  sort?:
    | "urgency"
    | "status"
    | "priority"
    | "updated_at"
    | "created_at"
    | "start_date"
    | "target_date"
    | "student_number";
  order?: "asc" | "desc";
}
export interface FollowUpParams {
  page: number;
  page_size: number;
  status?: FollowUpDetail["effective_status"];
  assigned_to?: string;
  student_id?: string;
  intervention_id?: string;
  search?: string;
  from?: string;
  to?: string;
  sort?: "scheduled_for" | "created_at" | "updated_at" | "student_number";
  order?: "asc" | "desc";
}
