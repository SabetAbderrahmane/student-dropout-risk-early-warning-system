import { ApiError } from "./api";
import type { User } from "@/types/auth";
import type {
  FollowUpDetail,
  FollowUpMethod,
  FollowUpOutcome,
  InterventionRow,
} from "@/types/casework";

export const FOLLOW_UP_METHODS: FollowUpMethod[] = [
  "IN_PERSON",
  "PHONE",
  "EMAIL",
  "ONLINE_MEETING",
  "OTHER",
];
export const FOLLOW_UP_OUTCOMES: FollowUpOutcome[] = [
  "COMPLETED",
  "PROGRESS_OBSERVED",
  "NO_RESPONSE",
  "RESCHEDULED",
  "ESCALATION_REQUIRED",
  "INTERVENTION_COMPLETED",
];
export interface FollowUpFailure {
  message: string;
  fields: Record<string, string>;
}
export type FollowUpMutation = (
  work: () => Promise<FollowUpDetail>,
) => Promise<FollowUpFailure | null>;

export function followUpFailure(caught: unknown): FollowUpFailure {
  const fields: Record<string, string> = {};
  if (caught instanceof ApiError) {
    if (Array.isArray(caught.details))
      for (const item of caught.details as unknown[]) {
        if (
          item &&
          typeof item === "object" &&
          "field" in item &&
          "message" in item &&
          typeof item.field === "string" &&
          typeof item.message === "string"
        )
          fields[item.field] = item.message;
      }
    if (caught.status === 422 && caught.code === "INVALID_FOLLOW_UP_ASSIGNEE")
      fields.assigned_to = caught.message;
    const prefix =
      caught.status === 403
        ? "Permission denied. "
        : caught.status === 404
          ? "This record is no longer available. "
          : caught.status === 409
            ? "The record changed or this action is no longer allowed. "
            : "";
    return { message: `${prefix}${caught.message}`, fields };
  }
  return {
    message:
      caught instanceof Error
        ? caught.message
        : "The request could not be completed. Please retry.",
    fields,
  };
}
export function canScheduleFollowUp(
  user: User,
  intervention: InterventionRow,
): boolean {
  return (
    intervention.status !== "CANCELLED" &&
    (user.role === "ACADEMIC_ADMIN" ||
      (user.role === "ACADEMIC_ADVISOR" &&
        intervention.assigned_advisor.id === user.id))
  );
}
export function canChangeFollowUp(
  user: User,
  followUp: FollowUpDetail,
  intervention: InterventionRow,
): boolean {
  return (
    followUp.stored_status === "SCHEDULED" &&
    (user.role === "ACADEMIC_ADMIN" ||
      (user.role === "ACADEMIC_ADVISOR" &&
        followUp.assigned_advisor.id === user.id &&
        intervention.assigned_advisor.id === user.id))
  );
}
/** Accept local form input only; serialize a timezone-aware instant for FastAPI. */
export function followUpInstant(value: string): string {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime()))
    throw new Error("Choose a valid date and time.");
  return date.toISOString();
}
export function localDateTime(value: string): string {
  const date = new Date(value);
  return `${localDate(date)}T${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
export function localDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function dateRangeInstant(
  value: string,
  end = false,
): string | undefined {
  if (!value) return undefined;
  const date = new Date(`${value}T00:00:00`);
  if (end) {
    date.setDate(date.getDate() + 1);
    date.setMilliseconds(-1);
  }
  return date.toISOString();
}
