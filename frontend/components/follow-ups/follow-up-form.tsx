"use client";
import { useId, useRef, useState } from "react";
import type { User } from "@/types/auth";
import type { FollowUpDetail, FollowUpInput } from "@/types/casework";
import {
  cancelCaseFollowUp,
  completeCaseFollowUp,
  createCaseFollowUp,
  updateCaseFollowUp,
} from "@/lib/api";
import { readable } from "@/lib/dashboard";
import {
  FOLLOW_UP_METHODS,
  FOLLOW_UP_OUTCOMES,
  followUpInstant,
  localDateTime,
  followUpFailure,
  type FollowUpFailure,
  type FollowUpMutation,
} from "@/lib/follow-ups";

export type FollowUpFormMode = "schedule" | "edit" | "complete" | "cancel";
export function FollowUpForm({
  mode,
  token,
  user,
  detail,
  interventionId,
  advisorId,
  mutate,
  onDone,
  onCancel,
  disabled = false,
}: {
  mode: FollowUpFormMode;
  token: string;
  user: User;
  detail?: FollowUpDetail;
  interventionId?: string;
  advisorId?: string;
  mutate: FollowUpMutation;
  onDone: () => void;
  onCancel: () => void;
  disabled?: boolean;
}) {
  const prefix = useId();
  const [scheduled, setScheduled] = useState(
    detail ? localDateTime(detail.scheduled_for) : "",
  );
  const [method, setMethod] = useState<FollowUpInput["method"]>(
    detail?.method ?? "IN_PERSON",
  );
  const [purpose, setPurpose] = useState(detail?.purpose ?? "");
  const [assigned, setAssigned] = useState(
    detail?.assigned_advisor.id ??
      (user.role === "ACADEMIC_ADVISOR" ? user.id : (advisorId ?? "")),
  );
  const [outcome, setOutcome] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [another, setAnother] = useState(false);
  const [next, setNext] = useState("");
  const [error, setError] = useState<FollowUpFailure | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const label =
    mode === "schedule"
      ? "Schedule Follow-Up"
      : mode === "edit"
        ? "Save Follow-Up"
        : mode === "complete"
          ? "Complete Follow-Up"
          : "Confirm Cancellation";
  const fieldError = (key: string) =>
    error?.fields[key] ? (
      <span
        id={`${prefix}-${key}-error`}
        className="follow-field-error"
        role="alert"
      >
        {error.fields[key]}
      </span>
    ) : null;
  const invalid = (key: string) => ({
    "aria-invalid": !!error?.fields[key],
    "aria-describedby": error?.fields[key]
      ? `${prefix}-${key}-error`
      : undefined,
  });
  return (
    <form
      className="follow-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (lock.current || disabled) return;
        lock.current = true;
        setBusy(true);
        setError(null);
        try {
          let failure: FollowUpFailure | null;
          if (mode === "schedule" || mode === "edit") {
            const payload: FollowUpInput = {
              scheduled_for: followUpInstant(scheduled),
              method,
              purpose: purpose.trim(),
              assigned_to: assigned.trim(),
            };
            failure = await mutate(() =>
              mode === "schedule"
                ? createCaseFollowUp(token, interventionId!, payload)
                : updateCaseFollowUp(token, detail!.id, payload),
            );
          } else if (mode === "complete") {
            failure = await mutate(() =>
              completeCaseFollowUp(token, detail!.id, {
                outcome: outcome as NonNullable<FollowUpDetail["outcome"]>,
                notes: notes.trim(),
                ...(another
                  ? { next_follow_up_at: followUpInstant(next) }
                  : {}),
              }),
            );
          } else
            failure = await mutate(() =>
              cancelCaseFollowUp(token, detail!.id, notes.trim()),
            );
          if (failure) setError(failure);
          else onDone();
        } catch (caught) {
          setError(followUpFailure(caught));
        } finally {
          lock.current = false;
          setBusy(false);
        }
      }}
    >
      <fieldset disabled={busy || disabled}>
        {(mode === "schedule" || mode === "edit") && (
          <>
            <label htmlFor={`${prefix}-scheduled_for`}>
              Scheduled for <small>Your local time</small>
            </label>
            <input
              id={`${prefix}-scheduled_for`}
              type="datetime-local"
              required
              value={scheduled}
              onChange={(e) => setScheduled(e.target.value)}
              {...invalid("scheduled_for")}
            />
            {fieldError("scheduled_for")}
            <label htmlFor={`${prefix}-method`}>Contact method</label>
            <select
              id={`${prefix}-method`}
              value={method}
              onChange={(e) =>
                setMethod(e.target.value as FollowUpInput["method"])
              }
              {...invalid("method")}
            >
              {FOLLOW_UP_METHODS.map((value) => (
                <option key={value} value={value}>
                  {readable(value)}
                </option>
              ))}
            </select>
            {fieldError("method")}
            <label htmlFor={`${prefix}-purpose`}>Purpose</label>
            <textarea
              id={`${prefix}-purpose`}
              required
              maxLength={2000}
              rows={4}
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              {...invalid("purpose")}
            />
            {fieldError("purpose")}
            <label htmlFor={`${prefix}-assigned_to`}>
              Assigned advisor
              {user.role === "ACADEMIC_ADMIN" ? " ID" : ` — ${user.full_name}`}
            </label>
            <input
              id={`${prefix}-assigned_to`}
              required
              readOnly={user.role !== "ACADEMIC_ADMIN"}
              value={assigned}
              onChange={(e) => setAssigned(e.target.value)}
              {...invalid("assigned_to")}
            />
            {fieldError("assigned_to")}
            {user.role === "ACADEMIC_ADMIN" && (
              <p className="follow-muted">
                Enter an existing active academic advisor's user ID.
              </p>
            )}
          </>
        )}
        {mode === "complete" && (
          <>
            <label htmlFor={`${prefix}-outcome`}>Outcome</label>
            <select
              id={`${prefix}-outcome`}
              required
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              {...invalid("outcome")}
            >
              <option value="">Choose an outcome…</option>
              {FOLLOW_UP_OUTCOMES.map((value) => (
                <option key={value} value={value}>
                  {readable(value)}
                </option>
              ))}
            </select>
            {fieldError("outcome")}
          </>
        )}
        {(mode === "complete" || mode === "cancel") && (
          <>
            <label htmlFor={`${prefix}-notes`}>
              {mode === "cancel" ? "Cancellation reason" : "Completion notes"}
            </label>
            <textarea
              id={`${prefix}-notes`}
              required
              maxLength={4000}
              rows={5}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              {...invalid(mode === "cancel" ? "reason" : "notes")}
            />
            {fieldError(mode === "cancel" ? "reason" : "notes")}
          </>
        )}
        {mode === "complete" && (
          <>
            <label className="follow-checkbox">
              <input
                type="checkbox"
                checked={another}
                onChange={(e) => setAnother(e.target.checked)}
              />
              Schedule another follow-up
            </label>
            {another && (
              <>
                <label htmlFor={`${prefix}-next`}>
                  Next follow-up <small>Your local time</small>
                </label>
                <input
                  id={`${prefix}-next`}
                  type="datetime-local"
                  required
                  value={next}
                  onChange={(e) => setNext(e.target.value)}
                  {...invalid("next_follow_up_at")}
                />
                {fieldError("next_follow_up_at")}
                <p className="follow-muted">
                  The next follow-up will retain this record's intervention,
                  advisor, method, and purpose.
                </p>
              </>
            )}
          </>
        )}
      </fieldset>
      {error && (
        <div className="follow-form-error" role="alert">
          <p>{error.message}</p>
          {Object.entries(error.fields)
            .filter(
              ([key]) =>
                ![
                  "scheduled_for",
                  "method",
                  "purpose",
                  "assigned_to",
                  "outcome",
                  "notes",
                  "reason",
                  "next_follow_up_at",
                ].includes(key),
            )
            .map(([key, value]) => (
              <p key={key}>{value}</p>
            ))}
        </div>
      )}
      <div className="follow-form-actions">
        <button
          className="dash-button"
          type="button"
          disabled={busy}
          onClick={onCancel}
        >
          Back
        </button>
        <button
          className="dash-button dash-button-primary"
          disabled={busy || disabled}
        >
          {busy ? "Saving…" : label}
        </button>
      </div>
    </form>
  );
}
