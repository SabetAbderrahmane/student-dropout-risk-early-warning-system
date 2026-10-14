"use client";
import { useEffect, useState } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import {
  addInterventionNote,
  cancelIntervention,
  completeIntervention,
  createCaseFollowUp,
  fetchInterventionDetail,
  updateIntervention,
  transferIntervention,
} from "@/lib/api";
import { readable, timestamp } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import type {
  InterventionDetail,
  InterventionOutcome,
  FollowUpMethod,
} from "@/types/casework";
import type { WarningPriority } from "@/types/dashboard";
import { DossierForm, type DossierField } from "./dossier-form";
import { DossierBadge, RecordValues } from "./dossier-records";
import { dossierError } from "./use-dossier";
export const FOLLOW_METHODS: FollowUpMethod[] = [
  "IN_PERSON",
  "PHONE",
  "EMAIL",
  "ONLINE_MEETING",
  "OTHER",
];
const OUTCOMES: InterventionOutcome[] = [
  "SUPPORT_COMPLETED",
  "GOALS_PARTIALLY_MET",
  "REFERRED_FOR_ADDITIONAL_SUPPORT",
  "STUDENT_UNRESPONSIVE",
  "OTHER",
];
export function CaseDetail({
  id,
  token,
  user,
  canCase,
  recoveryRevision,
  busy,
  mutate,
  report,
  onClose,
  onFollowUp,
}: {
  id: string;
  token: string;
  user: User;
  canCase: boolean;
  recoveryRevision: number;
  busy: boolean;
  mutate: (work: () => Promise<unknown>) => Promise<string | null>;
  report: (error: unknown) => void;
  onClose: () => void;
  onFollowUp?: (id: string) => void;
}) {
  const [detail, setDetail] = useState<InterventionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [mode, setMode] = useState<
    "note" | "edit" | "schedule" | "complete" | "cancel" | "transfer" | null
  >(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setDetail(null);
    void fetchInterventionDetail(token, id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setDetail(data);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(dossierError(caught));
          report(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, id, revision, recoveryRevision]);
  const owned =
    !!detail &&
    canCase &&
    (user.role === "ACADEMIC_ADMIN" || detail.assigned_advisor.id === user.id);
  const mutable =
    detail?.status !== "COMPLETED" && detail?.status !== "CANCELLED";
  let fields: DossierField[] = [];
  let initial: Record<string, string> = {};
  if (mode === "note")
    fields = [{ key: "note", label: "Case note", type: "textarea" }];
  if (mode === "complete")
    fields = [
      { key: "outcome", label: "Completion outcome", options: OUTCOMES },
      { key: "completion_notes", label: "Completion notes", type: "textarea" },
    ];
  if (mode === "cancel")
    fields = [
      { key: "reason", label: "Cancellation reason", type: "textarea" },
    ];
  if (mode === "schedule" && detail) {
    fields = [
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
      {
        key: "assigned_to",
        label: "Assigned advisor",
        readOnly: true,
      },
    ];
    initial = { assigned_to: detail.assigned_advisor.id };
  }
  if (mode === "edit" && detail) {
    fields = [
      { key: "title", label: "Intervention title", maxLength: 250 },
      { key: "description", label: "Description", type: "textarea" },
      {
        key: "priority",
        label: "Priority",
        options: ["P1_URGENT", "P2_ELEVATED", "P3_STANDARD"],
      },
      {
        key: "target_date",
        label: "Target date",
        type: "date",
        optional: true,
      },
    ];
    initial = {
      title: detail.title,
      description: detail.description,
      priority: detail.priority,
      target_date: detail.target_date ?? "",
      assigned_to: detail.assigned_advisor.id,
    };
  }
  if (mode === "transfer" && detail) {
    fields = [
      { key: "assigned_to", label: "New advisor" },
      { key: "reason", label: "Transfer reason", type: "textarea" },
    ];
    initial = { assigned_to: detail.assigned_advisor.id };
  }
  async function save(values: Record<string, string>) {
    if (!detail || !owned) return "Your account cannot change this case.";
    const result = await mutate(() =>
      mode === "transfer"
        ? transferIntervention(token, id, {
            assigned_to: values.assigned_to,
            reason: values.reason,
            expected_revision: detail.revision,
          })
        : mode === "note"
          ? addInterventionNote(token, id, values.note, detail.revision)
          : mode === "complete"
            ? completeIntervention(
                token,
                id,
                values.outcome as InterventionOutcome,
                values.completion_notes,
                detail.revision,
              )
            : mode === "cancel"
              ? cancelIntervention(token, id, values.reason, detail.revision)
              : mode === "schedule"
                ? createCaseFollowUp(token, id, {
                    scheduled_for: new Date(values.scheduled_for).toISOString(),
                    method: values.method as FollowUpMethod,
                    purpose: values.purpose,
                    assigned_to: detail.assigned_advisor.id,
                    expected_revision: detail.revision,
                  })
                : updateIntervention(token, id, {
                    expected_revision: detail.revision,
                    title: values.title,
                    description: values.description,
                    priority: values.priority as WarningPriority,
                    target_date: values.target_date || null,
                  }),
    );
    if (!result) {
      setError("");
      setMode(null);
      setRevision((r) => r + 1);
    } else setError(result);
    return result;
  }
  async function transition() {
    if (!detail || !owned || !mutable) return;
    const next =
      detail.status === "IN_PROGRESS" ? "ACTION_REQUIRED" : "IN_PROGRESS";
    const result = await mutate(() =>
      updateIntervention(token, id, {
        status: next,
        expected_revision: detail.revision,
      }),
    );
    if (!result) {
      setError("");
      setRevision((r) => r + 1);
    } else setError(result);
  }
  return (
    <ActionModal
      title="Intervention dossier"
      busy={busy}
      onClose={onClose}
      className="dossier-modal"
    >
      {loading && <p role="status">Loading intervention and notes…</p>}
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
          <h3>{detail.title}</h3>
          <div className="dossier-row">
            <DossierBadge value={detail.status} />
            <DossierBadge value={detail.priority} />
          </div>
          <p className="dossier-prose">{detail.description}</p>
          <RecordValues
            record={{
              type: readable(detail.type),
              assigned_advisor: detail.assigned_advisor.full_name,
              start_date: detail.start_date,
              target_date: detail.target_date,
              completion_outcome: detail.completion_outcome,
              completion_notes: detail.completion_notes,
              completed_at: detail.completed_at
                ? timestamp(detail.completed_at)
                : null,
            }}
          />
          {owned && (
            <div className="dossier-actions">
              <button
                className="dash-button"
                disabled={busy}
                onClick={() => setMode("note")}
              >
                Add Note
              </button>
              {mutable && user.role === "ACADEMIC_ADMIN" && (
                <button
                  className="dash-button"
                  disabled={busy}
                  onClick={() => setMode("transfer")}
                >
                  Transfer Intervention
                </button>
              )}
              {mutable && (
                <>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => setMode("edit")}
                  >
                    Edit Intervention
                  </button>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => void transition()}
                  >
                    {detail.status === "PLANNED"
                      ? "Start Intervention"
                      : detail.status === "IN_PROGRESS"
                        ? "Mark Action Required"
                        : "Resume Intervention"}
                  </button>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => setMode("complete")}
                  >
                    Complete Intervention
                  </button>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => setMode("cancel")}
                  >
                    Cancel Intervention
                  </button>
                </>
              )}
              {mutable && (
                <button
                  className="dash-button"
                  disabled={busy}
                  onClick={() => setMode("schedule")}
                >
                  Schedule Follow-Up
                </button>
              )}
            </div>
          )}
          {mode &&
            owned &&
            (mode === "note" ||
              (mode === "schedule" && mutable) ||
              mutable) && (
              <section className="dossier-subform">
                <h3>{readable(mode)}</h3>
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
                  onSubmit={save}
                  onCancel={() => setMode(null)}
                />
              </section>
            )}
          {mode === "transfer" && (
            <p className="dossier-prose">
              Transfers{" "}
              {
                detail.follow_ups.filter(
                  (item) => item.stored_status === "SCHEDULED",
                ).length
              }{" "}
              scheduled follow-ups, including due and overdue contacts.
            </p>
          )}
          {mutable &&
            detail.follow_ups.some(
              (item) => item.stored_status === "SCHEDULED",
            ) && (
              <p className="dossier-prose">
                Complete or cancel all scheduled follow-ups before closing this
                intervention.
              </p>
            )}
          <h3>Advisor notes ({detail.notes.length})</h3>
          {detail.notes.length === 0 ? (
            <p className="dossier-empty">
              No notes recorded for this intervention.
            </p>
          ) : (
            detail.notes.map((note) => (
              <article className="dossier-note" key={note.id}>
                <small>
                  {note.author_name} · {timestamp(note.created_at)}
                </small>
                <p>{note.note}</p>
              </article>
            ))
          )}
          <h3>Linked follow-ups ({detail.follow_ups.length})</h3>
          {detail.follow_ups.length === 0 ? (
            <p className="dossier-empty">No follow-ups recorded.</p>
          ) : (
            detail.follow_ups.map((item) => (
              <article className="dossier-note" key={item.id}>
                <DossierBadge value={item.effective_status} />
                <p>{item.purpose}</p>
                <small>
                  {timestamp(item.scheduled_for)} ·{" "}
                  {item.assigned_advisor.full_name}
                </small>
                {onFollowUp && (
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => onFollowUp(item.id)}
                  >
                    Open Follow-Up
                  </button>
                )}
              </article>
            ))
          )}
        </>
      )}
    </ActionModal>
  );
}
