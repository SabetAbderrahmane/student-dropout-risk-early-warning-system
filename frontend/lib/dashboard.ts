import type { User } from "@/types/auth";
import type { AttentionStudent, WarningPriority } from "@/types/dashboard";

export function readable(value: string): string {
  return value
    .split("_")
    .map((word) =>
      /^P\d$/.test(word)
        ? word
        : word.charAt(0).toUpperCase() + word.slice(1).toLowerCase(),
    )
    .join(" ");
}
export function percent(value: number): string {
  return new Intl.NumberFormat("en", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}
export function timestamp(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not available"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}
export function calendarDate(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(
        date,
      );
}
export function factorLabel(factor: Record<string, unknown>): string {
  if (typeof factor.label === "string" && factor.label.trim())
    return factor.label;
  for (const key of ["feature", "feature_name", "name"]) {
    if (typeof factor[key] === "string" && factor[key].trim())
      return readable(factor[key]);
  }
  return "Prediction factor";
}
export function isWarningPriority(value: string): value is WarningPriority {
  return ["P1_URGENT", "P2_ELEVATED", "P3_STANDARD"].includes(value);
}
export function canReview(user: User, student: AttentionStudent): boolean {
  return (
    user.role === "ACADEMIC_ADVISOR" &&
    student.review_state === "PENDING_REVIEW" &&
    student.assigned_advisor?.user_id === user.id
  );
}
export function canIntervene(user: User, student: AttentionStudent): boolean {
  return (
    student.review_state === "CONFIRMED" &&
    !!student.assigned_advisor &&
    isWarningPriority(student.priority) &&
    (user.role === "ACADEMIC_ADMIN" ||
      (user.role === "ACADEMIC_ADVISOR" &&
        student.assigned_advisor.user_id === user.id))
  );
}
