import { useState, type FormEvent } from "react";
import type {
  AttentionStudent,
  InterventionInput,
  InterventionType,
} from "@/types/dashboard";
import { isWarningPriority, readable } from "@/lib/dashboard";
import { ActionModal } from "./action-modal";

const types: InterventionType[] = [
  "ACADEMIC_TUTORING",
  "ACADEMIC_ADVISING",
  "STUDY_PERFORMANCE_PLAN",
  "FINANCIAL_SUPPORT_REFERRAL",
  "ADMINISTRATIVE_SUPPORT_REFERRAL",
  "OTHER",
];
function today(): string {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function QuickInterventionModal({
  student,
  onClose,
  onSubmit,
  title: modalTitle = "Quick Intervention",
}: {
  student: Pick<
    AttentionStudent,
    | "student_id"
    | "warning_id"
    | "name"
    | "student_number"
    | "priority"
    | "assigned_advisor"
  >;
  title?: string;
  onClose: () => void;
  onSubmit: (payload: InterventionInput) => Promise<string | null>;
}) {
  const [type, setType] = useState<InterventionType>("ACADEMIC_ADVISING");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState(today);
  const [targetDate, setTargetDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!title.trim() || !description.trim()) {
      setError("Title and description must not be blank.");
      return;
    }
    if (targetDate && targetDate < startDate) {
      setError("Target date cannot precede start date.");
      return;
    }
    if (!student.warning_id || !student.assigned_advisor || !isWarningPriority(student.priority)) {
      setError("A valid warning priority and assigned advisor are required.");
      return;
    }
    setBusy(true);
    setError("");
    const message = await onSubmit({
      student_id: student.student_id,
      warning_id: student.warning_id,
      type,
      title: title.trim(),
      description: description.trim(),
      priority: student.priority,
      assigned_to: student.assigned_advisor.user_id,
      start_date: startDate,
      target_date: targetDate || null,
    });
    if (message) {
      setError(message);
      setBusy(false);
    }
  }
  return (
    <ActionModal title={modalTitle} busy={busy} onClose={onClose}>
      <div className="dash-case-context">
        <strong>{student.name}</strong>
        <span>{student.student_number} · Confirmed warning</span>
      </div>
      <p className="dash-subtle">
        Assigned to <strong>{student.assigned_advisor?.full_name}</strong> ·{" "}
        {student.priority ? readable(student.priority) : "No warning priority"}
      </p>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <label htmlFor="intervention-type">Support type</label>
          <select
            id="intervention-type"
            value={type}
            onChange={(event) =>
              setType(event.target.value as InterventionType)
            }
          >
            {types.map((value) => (
              <option key={value} value={value}>
                {readable(value)}
              </option>
            ))}
          </select>
          <label htmlFor="intervention-title">
            Title <span>Required</span>
          </label>
          <input
            id="intervention-title"
            required
            maxLength={250}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
          <label htmlFor="intervention-description">
            Description <span>Required</span>
          </label>
          <textarea
            id="intervention-description"
            required
            maxLength={4000}
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <div className="dash-date-fields">
            <div>
              <label htmlFor="intervention-start">Start date</label>
              <input
                id="intervention-start"
                type="date"
                required
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="intervention-target">
                Target date <span>Optional</span>
              </label>
              <input
                id="intervention-target"
                type="date"
                min={startDate}
                value={targetDate}
                onChange={(event) => setTargetDate(event.target.value)}
              />
            </div>
          </div>
        </fieldset>
        {error && (
          <p className="dash-inline-error" role="alert">
            {error}
          </p>
        )}
        <div className="dash-modal-actions">
          <button
            type="button"
            className="dash-button"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="dash-button dash-button-primary"
            disabled={busy || !title.trim() || !description.trim()}
          >
            {busy ? "Creating intervention…" : "Create Intervention"}
          </button>
        </div>
      </form>
    </ActionModal>
  );
}
