import { useState, type FormEvent } from "react";
import type {
  AttentionStudent,
  ReviewDecision,
  ReviewWarningInput,
} from "@/types/dashboard";
import { percent } from "@/lib/dashboard";
import { ActionModal } from "./action-modal";

export function ReviewWarningModal({
  student,
  onClose,
  onSubmit,
}: {
  student: AttentionStudent;
  onClose: () => void;
  onSubmit: (payload: ReviewWarningInput) => Promise<string | null>;
}) {
  const [decision, setDecision] = useState<ReviewDecision>("CONFIRMED");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!note.trim()) {
      setError("Add a nonblank advisor note before submitting the review.");
      return;
    }
    setBusy(true);
    setError("");
    const message = await onSubmit({ decision, note: note.trim() });
    if (message) {
      setError(message);
      setBusy(false);
    }
  }
  return (
    <ActionModal title="Review Case" busy={busy} onClose={onClose}>
      <div className="dash-case-context">
        <strong>{student.name}</strong>
        <span>
          {student.student_number} · {student.probability === null ? "No current probability" : `${percent(student.probability)} current risk probability`}
        </span>
      </div>
      <p className="dash-subtle">
        Record your assessment of this warning. Your note becomes part of its
        review history.
      </p>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <legend>Review decision</legend>
          <div className="dash-decision-options">
            {(["CONFIRMED", "DISMISSED"] as const).map((value) => (
              <label key={value}>
                <input
                  type="radio"
                  name="decision"
                  value={value}
                  checked={decision === value}
                  onChange={() => setDecision(value)}
                />
                {value === "CONFIRMED" ? "Confirm Warning" : "Dismiss Warning"}
              </label>
            ))}
          </div>
          <label htmlFor="review-note">
            Advisor note <span>Required</span>
          </label>
          <textarea
            id="review-note"
            required
            rows={5}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Explain the evidence and reasoning for your decision."
          />
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
            className="dash-button dash-button-primary"
            disabled={busy || !note.trim()}
            type="submit"
          >
            {busy
              ? "Submitting review…"
              : decision === "CONFIRMED"
                ? "Confirm Warning"
                : "Dismiss Warning"}
          </button>
        </div>
      </form>
    </ActionModal>
  );
}
