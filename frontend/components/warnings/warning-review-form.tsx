import { useState, type FormEvent } from "react";
import type { ReviewDecision, ReviewWarningInput } from "@/types/dashboard";

export function WarningReviewForm({
  onSubmit,
  onBusy,
  reconsider = false,
}: {
  onSubmit: (payload: ReviewWarningInput) => Promise<string | null>;
  onBusy: (busy: boolean) => void;
  reconsider?: boolean;
}) {
  const [decision, setDecision] = useState<ReviewDecision>("CONFIRMED");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!note.trim() || (reconsider && !reason.trim())) {
      setError("A nonblank review note is required for either decision.");
      return;
    }
    setBusy(true);
    onBusy(true);
    setError("");
    try {
      const message = await onSubmit({
        decision,
        note: note.trim(),
        ...(reconsider ? { reason: reason.trim() } : {}),
      });
      if (message) setError(message);
    } finally {
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <section className="warning-review-section">
      <h3>
        {reconsider ? "Reconsider Reviewed Warning" : "Advisor Review Decision"}
      </h3>
      <p className="warning-muted">
        Record your rationale for this individual warning. Support planning is a
        separate next step.
      </p>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <legend className="warning-label">Decision</legend>
          <div className="warning-decisions">
            <label>
              <input
                type="radio"
                name="warning-decision"
                checked={decision === "CONFIRMED"}
                onChange={() => setDecision("CONFIRMED")}
              />
              Confirm Warning
            </label>
            <label>
              <input
                type="radio"
                name="warning-decision"
                checked={decision === "DISMISSED"}
                onChange={() => setDecision("DISMISSED")}
              />
              Dismiss Warning
            </label>
          </div>
          {reconsider && (
            <>
              <label htmlFor="warning-reconsider-reason">
                Reconsideration reason · Required
              </label>
              <textarea
                id="warning-reconsider-reason"
                required
                maxLength={4000}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </>
          )}
          <label htmlFor="warning-review-note">
            Review note <span>Required</span>
          </label>
          <textarea
            id="warning-review-note"
            required
            rows={4}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Explain your review rationale…"
          />
        </fieldset>
        {error && (
          <p className="dash-inline-error" role="alert">
            {error}
          </p>
        )}
        <div className="dash-modal-actions">
          <button
            type="submit"
            className="dash-button dash-button-primary"
            disabled={busy || !note.trim() || (reconsider && !reason.trim())}
          >
            {busy
              ? "Saving review…"
              : decision === "CONFIRMED"
                ? "Confirm Warning"
                : "Dismiss Warning"}
          </button>
        </div>
      </form>
    </section>
  );
}
