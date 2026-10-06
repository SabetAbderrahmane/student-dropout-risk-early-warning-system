"use client";
import { useEffect, useState } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import { DossierForm } from "@/components/dossier/dossier-form";
import { createIntervention, fetchWarning, fetchWarnings } from "@/lib/api";
import { readable } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import type {
  InterventionInput,
  InterventionType,
  WarningPriority,
} from "@/types/dashboard";
import type { WarningDetail, WarningPage } from "@/types/warning";
import { CaseworkPagination } from "./pagination";

export const CASE_TYPES: InterventionType[] = [
  "ACADEMIC_TUTORING",
  "ACADEMIC_ADVISING",
  "STUDY_PERFORMANCE_PLAN",
  "FINANCIAL_SUPPORT_REFERRAL",
  "ADMINISTRATIVE_SUPPORT_REFERRAL",
  "OTHER",
];
export const CASE_PRIORITIES: WarningPriority[] = [
  "P1_URGENT",
  "P2_ELEVATED",
  "P3_STANDARD",
];

export function CreateCaseDrawer({
  token,
  user,
  mutate,
  report,
  busy,
  onClose,
}: {
  token: string;
  user: User;
  busy: boolean;
  onClose: () => void;
  mutate: (work: () => Promise<unknown>) => Promise<string | null>;
  report: (error: unknown) => string;
}) {
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<WarningPage | null>(null);
  const [warning, setWarning] = useState<WarningDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [selecting, setSelecting] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(input.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [input]);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    fetchWarnings(
      token,
      {
        page,
        page_size: 10,
        review_state: "CONFIRMED",
        ...(search ? { search } : {}),
        ...(user.role === "ACADEMIC_ADVISOR" ? { assigned_to: user.id } : {}),
      },
      c.signal,
    )
      .then((result) => {
        if (!c.signal.aborted) setData(result);
      })
      .catch((caught) => {
        if (!c.signal.aborted) setError(report(caught));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [token, user.id, user.role, page, search, retry]);
  async function choose(id: string) {
    setSelecting(true);
    setError("");
    try {
      const detail = await fetchWarning(token, id);
      if (
        detail.review_state !== "CONFIRMED" ||
        (user.role === "ACADEMIC_ADVISOR" &&
          detail.assigned_advisor?.id !== user.id)
      ) {
        setError(
          "This warning is no longer eligible. Refresh the warning list.",
        );
        return;
      }
      setWarning(detail);
    } catch (caught) {
      setError(report(caught));
    } finally {
      setSelecting(false);
    }
  }
  return (
    <ActionModal
      title="Create Intervention"
      busy={busy || selecting}
      onClose={onClose}
      className="casework-drawer"
    >
      {error && (
        <p className="dash-inline-error" role="alert">
          {error}{" "}
          <button
            className="dash-button"
            onClick={() => setRetry((r) => r + 1)}
          >
            Retry
          </button>
        </p>
      )}
      {!warning ? (
        <>
          <p className="dash-subtle">
            Start with a confirmed warning
            {user.role === "ACADEMIC_ADVISOR" ? " assigned to you" : ""}.
          </p>
          <label className="casework-search">
            Search confirmed warnings
            <input
              maxLength={200}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Student name or number"
            />
          </label>
          {loading && <p role="status">Loading confirmed warnings…</p>}
          {!loading && data && !data.items.length && (
            <p>No confirmed warnings match this search.</p>
          )}
          <div className="casework-warning-picker">
            {data?.items.map((row) => (
              <button
                key={row.id}
                className="casework-warning-option"
                disabled={selecting}
                onClick={() => void choose(row.id)}
              >
                <strong>{row.student_name}</strong>
                <span>
                  {row.student_number} · {readable(row.priority)}
                </span>
                <small>
                  {row.assigned_advisor?.full_name ?? "Awaiting assignment"}
                </small>
              </button>
            ))}
          </div>
          {data && (
            <CaseworkPagination data={data} noun="warnings" onPage={setPage} />
          )}
        </>
      ) : (
        <>
          <div className="dash-case-context">
            <strong>{warning.student_name}</strong>
            <span>{warning.student_number} · Confirmed warning</span>
          </div>
          <button
            className="dash-button"
            disabled={busy}
            onClick={() => setWarning(null)}
          >
            Choose another warning
          </button>
          <DossierForm
            key={warning.id}
            submitLabel="Create Intervention"
            onCancel={onClose}
            initial={{
              type: "ACADEMIC_ADVISING",
              priority: "P3_STANDARD",
              assigned_to: warning.assigned_advisor?.id ?? "",
              start_date: new Date().toLocaleDateString("en-CA"),
            }}
            fields={[
              { key: "type", label: "Support type", options: CASE_TYPES },
              { key: "title", label: "Title", maxLength: 250 },
              { key: "description", label: "Description", type: "textarea" },
              { key: "priority", label: "Priority", options: CASE_PRIORITIES },
              {
                key: "assigned_to",
                label:
                  user.role === "ACADEMIC_ADMIN"
                    ? "Assigned advisor ID"
                    : `Assigned advisor — ${user.full_name}`,
                readOnly: user.role !== "ACADEMIC_ADMIN",
              },
              { key: "start_date", label: "Start date", type: "date" },
              {
                key: "target_date",
                label: "Target date",
                type: "date",
                optional: true,
              },
            ]}
            onSubmit={async (values) => {
              if (values.target_date && values.target_date < values.start_date)
                return "Target date cannot precede start date.";
              if (
                !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(
                  values.assigned_to,
                )
              )
                return "Enter a valid advisor user ID.";
              const payload: InterventionInput = {
                student_id: warning.student_id,
                warning_id: warning.id,
                type: values.type as InterventionType,
                title: values.title.trim(),
                description: values.description.trim(),
                priority: values.priority as WarningPriority,
                assigned_to: values.assigned_to,
                start_date: values.start_date,
                target_date: values.target_date || null,
              };
              const result = await mutate(() =>
                createIntervention(token, payload),
              );
              if (!result) onClose();
              return result;
            }}
          />
        </>
      )}
    </ActionModal>
  );
}
