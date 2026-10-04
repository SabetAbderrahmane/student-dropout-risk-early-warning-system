import type { User } from "@/types/auth";
import type { WarningRow } from "@/types/warning";
import { ApiError } from "./api";

export function canReviewWarning(user: User, warning: WarningRow): boolean {
  return (
    user.role === "ACADEMIC_ADVISOR" &&
    warning.review_state === "PENDING_REVIEW" &&
    warning.assigned_advisor?.id === user.id
  );
}
export function canCreateWarningIntervention(
  user: User,
  warning: WarningRow,
): boolean {
  return (
    warning.review_state === "CONFIRMED" &&
    !!warning.assigned_advisor &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      warning.assigned_advisor.id,
    ) &&
    (user.role === "ACADEMIC_ADMIN" ||
      (user.role === "ACADEMIC_ADVISOR" &&
        warning.assigned_advisor.id === user.id))
  );
}
export function warningError(caught: unknown): string {
  if (caught instanceof ApiError) {
    if (caught.code === "WARNING_REQUIRES_ASSIGNMENT")
      return "Awaiting assignment. An academic administrator must assign this warning before it can be reviewed.";
    if (caught.status === 403)
      return `${caught.message} Access depends on your role and the warning's assigned advisor.`;
    return caught.message;
  }
  return caught instanceof Error
    ? caught.message
    : "The request could not be completed. Please retry.";
}

/** Export is deliberately restricted to the currently loaded server page. */
export function exportWarningPage(rows: readonly WarningRow[]): void {
  const cell = (value: string | number) => {
    const text = String(value);
    const safe = /^[=+@\-\t\r]/.test(text) ? `'${text}` : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const fields = [
    "student_number",
    "student_name",
    "risk_level",
    "probability",
    "priority",
    "review_state",
    "assigned_advisor",
    "predicted_at",
    "created_at",
  ];
  const lines = rows.map((row) =>
    [
      row.student_number,
      row.student_name,
      row.risk_level,
      row.probability,
      row.priority,
      row.review_state,
      row.assigned_advisor?.full_name ?? "",
      row.predicted_at,
      row.created_at,
    ]
      .map(cell)
      .join(","),
  );
  const blob = new Blob(["\uFEFF", [fields.join(","), ...lines].join("\r\n")], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "warnings-current-page.csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
