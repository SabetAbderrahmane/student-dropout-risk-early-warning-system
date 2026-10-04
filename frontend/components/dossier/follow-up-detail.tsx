"use client";
import { useEffect, useState } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import {
  cancelCaseFollowUp,
  completeCaseFollowUp,
  fetchFollowUpDetail,
  updateCaseFollowUp,
} from "@/lib/api";
import type {
  FollowUpDetail as FollowUp,
  FollowUpOutcome,
  FollowUpMethod,
} from "@/types/casework";
import type { User } from "@/types/auth";
import { DossierForm, type DossierField } from "./dossier-form";
import { DossierBadge, RecordValues } from "./dossier-records";
import { dossierError } from "./use-dossier";
import { FOLLOW_METHODS } from "./case-detail";
const outcomes: FollowUpOutcome[] = [
  "COMPLETED",
  "PROGRESS_OBSERVED",
  "NO_RESPONSE",
  "RESCHEDULED",
  "ESCALATION_REQUIRED",
  "INTERVENTION_COMPLETED",
];
function localDatetime(value: string) {
  const d = new Date(value);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
export function FollowUpDetail({
  id,
  token,
  user,
  caseOwned,
  canCase,
  recoveryRevision,
  busy,
  mutate,
  report,
  onClose,
}: {
  id: string;
  token: string;
  user: User;
  caseOwned: boolean;
  canCase: boolean;
  recoveryRevision: number;
  busy: boolean;
  mutate: (work: () => Promise<unknown>) => Promise<string | null>;
  report: (error: unknown) => void;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<FollowUp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [mode, setMode] = useState<"edit" | "complete" | "cancel" | null>(null);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setDetail(null);
    void fetchFollowUpDetail(token, id, c.signal)
      .then((data) => {
        if (!c.signal.aborted) setDetail(data);
      })
      .catch((caught: unknown) => {
        if (!c.signal.aborted) {
          setError(dossierError(caught));
          report(caught);
        }
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [token, id, revision, recoveryRevision]);
  const owned =
    !!detail &&
    canCase &&
    (user.role === "ACADEMIC_ADMIN" ||
      (caseOwned && detail.assigned_advisor.id === user.id));
  const editable = owned && detail?.stored_status === "SCHEDULED";
  const fields: DossierField[] =
    mode === "cancel"
      ? [{ key: "reason", label: "Cancellation reason", type: "textarea" }]
      : mode === "complete"
        ? [
            { key: "outcome", label: "Follow-up outcome", options: outcomes },
            { key: "notes", label: "Follow-up notes", type: "textarea" },
            {
              key: "next_follow_up_at",
              label: "Next follow-up (your local time)",
              type: "datetime-local",
              optional: true,
            },
          ]
        : [
            {
              key: "scheduled_for",
              label: "Scheduled for (your local time)",
              type: "datetime-local",
            },
            { key: "method", label: "Contact method", options: FOLLOW_METHODS },
            {
              key: "purpose",
              label: "Follow-up purpose",
              type: "textarea",
              maxLength: 2000,
            },
            ...(user.role === "ACADEMIC_ADMIN"
              ? [{ key: "assigned_to", label: "Assigned advisor ID" }]
              : []),
          ];
  const initial: Record<string, string> =
    mode === "edit" && detail
      ? {
          scheduled_for: localDatetime(detail.scheduled_for),
          method: detail.method,
          purpose: detail.purpose,
          assigned_to: detail.assigned_advisor.id,
        }
      : {};
  return (
    <ActionModal
      title="Follow-up dossier"
      busy={busy}
      onClose={onClose}
      className="dossier-modal"
    >
      {loading && <p role="status">Loading follow-up…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button
            className="dash-button"
            onClick={() => {
              setError("");
              setRevision((r) => r + 1);
            }}
          >
            Retry
          </button>
        </div>
      )}
      {detail && (
        <>
          <DossierBadge value={detail.effective_status} />
          <p className="dossier-prose">{detail.purpose}</p>
          <RecordValues
            record={{
              scheduled_for: new Date(detail.scheduled_for).toLocaleString(),
              method: detail.method,
              assigned_advisor: detail.assigned_advisor.full_name,
              stored_status: detail.stored_status,
              outcome: detail.outcome,
              notes: detail.notes,
              completed_at: detail.completed_at,
            }}
          />
          {editable && (
            <div className="dossier-actions">
              <button
                className="dash-button"
                disabled={busy}
                onClick={() => setMode("edit")}
              >
                Edit Follow-Up
              </button>
              <button
                className="dash-button"
                disabled={busy}
                onClick={() => setMode("complete")}
              >
                Complete Follow-Up
              </button>
              <button
                className="dash-button"
                disabled={busy}
                onClick={() => setMode("cancel")}
              >
                Cancel Follow-Up
              </button>
            </div>
          )}
          {mode && editable && (
            <DossierForm
              key={mode}
              fields={fields}
              initial={initial}
              submitLabel={
                mode === "cancel"
                  ? "Confirm Cancellation"
                  : mode === "complete"
                    ? "Record Outcome"
                    : "Save"
              }
              onCancel={() => setMode(null)}
              onSubmit={async (values) => {
                const result = await mutate(() =>
                  mode === "cancel"
                    ? cancelCaseFollowUp(token, id, values.reason)
                    : mode === "complete"
                      ? completeCaseFollowUp(token, id, {
                          outcome: values.outcome as FollowUpOutcome,
                          notes: values.notes,
                          next_follow_up_at: values.next_follow_up_at
                            ? new Date(values.next_follow_up_at).toISOString()
                            : null,
                        })
                      : updateCaseFollowUp(token, id, {
                          scheduled_for: new Date(
                            values.scheduled_for,
                          ).toISOString(),
                          method: values.method as FollowUpMethod,
                          purpose: values.purpose,
                          ...(user.role === "ACADEMIC_ADMIN"
                            ? { assigned_to: values.assigned_to }
                            : {}),
                        }),
                );
                if (!result) {
                  setError("");
                  setMode(null);
                  setRevision((r) => r + 1);
                } else setError(result);
                return result;
              }}
            />
          )}
        </>
      )}
    </ActionModal>
  );
}
