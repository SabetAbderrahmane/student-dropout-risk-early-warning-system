"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  fetchFollowUpDetail,
  fetchInterventionDetail,
  fetchInterventionFollowUps,
} from "@/lib/api";
import { canChangeFollowUp, type FollowUpMutation } from "@/lib/follow-ups";
import { readable, timestamp } from "@/lib/dashboard";
import { DossierBadge } from "@/components/dossier/dossier-records";
import { CaseworkPagination } from "@/components/casework/pagination";
import type { User } from "@/types/auth";
import { useFollowUpResource } from "./use-follow-up-resource";
import { IntegrityRecovery } from "./integrity-recovery";
import { FollowUpForm, type FollowUpFormMode } from "./follow-up-form";

export function FollowUpDetailPanel({
  id,
  token,
  user,
  revision,
  busy,
  mutate,
  report,
  onRetry,
  onSelect,
  onClose,
}: {
  id: string;
  token: string;
  user: User;
  revision: number;
  busy: boolean;
  mutate: FollowUpMutation;
  report: (caught: unknown) => string;
  onRetry: () => void;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<FollowUpFormMode | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 1250px)").matches)
      heading.current?.scrollIntoView({ block: "start" });
  }, [id]);
  const resource = useFollowUpResource(
    `${token}:${id}`,
    revision,
    async (signal) => {
      const followUp = await fetchFollowUpDetail(token, id, signal);
      const intervention = await fetchInterventionDetail(
        token,
        followUp.intervention_id,
        signal,
      );
      return { followUp, intervention };
    },
    report,
  );
  const record = resource.data?.followUp;
  const intervention = resource.data?.intervention;
  const related = useFollowUpResource(
    record ? `${token}:${record.intervention_id}:${historyPage}` : "",
    revision,
    (signal) =>
      fetchInterventionFollowUps(
        token,
        record!.intervention_id,
        historyPage,
        5,
        signal,
      ),
    report,
  );
  const permitted =
    !!record && !!intervention && canChangeFollowUp(user, record, intervention);
  const writable = permitted && !resource.loading && !resource.error;
  return (
    <aside
      id="selected-follow-up"
      className="follow-detail"
      aria-labelledby="follow-detail-heading"
      aria-busy={resource.loading}
    >
      <header className="follow-panel-heading">
        <div>
          <p className="dash-eyebrow">Selected record</p>
          <h2 ref={heading} tabIndex={-1} id="follow-detail-heading">
            Follow-up details
          </h2>
        </div>
        <button className="dash-button" disabled={busy} onClick={onClose}>
          Close details
        </button>
      </header>
      {resource.loading && (
        <p className="follow-loading" role="status">
          Loading follow-up and intervention context…
        </p>
      )}
      {resource.error && (
        <div className="follow-load-error" role="alert">
          <p>{resource.error}</p>
          {record && (
            <p>
              Showing the last successful response. Actions are unavailable
              until this record refreshes.
            </p>
          )}
          <button className="dash-button" onClick={onRetry}>
            Retry details
          </button>
        </div>
      )}
      {record && intervention && (
        <div className="follow-detail-body">
          <div className="follow-detail-identity">
            <Link href={`/students/${encodeURIComponent(record.student.id)}`}>
              <h3>{record.student.name}</h3>
              <span>
                {record.student.student_number} · View Student Dossier ↗
              </span>
            </Link>
            <DossierBadge value={record.effective_status} />
          </div>
          <p className="follow-purpose">{record.purpose}</p>
          <div className="follow-intervention-link">
            <small>Related intervention</small>
            <Link
              href={`/interventions?intervention_id=${encodeURIComponent(record.intervention_id)}`}
            >
              {intervention.title} ↗
            </Link>
            <span>
              {readable(intervention.type)} · {readable(intervention.status)}
            </span>
          </div>
          <dl className="follow-detail-values">
            <div>
              <dt>Scheduled for</dt>
              <dd>{timestamp(record.scheduled_for)}</dd>
            </div>
            <div>
              <dt>Method</dt>
              <dd>{readable(record.method)}</dd>
            </div>
            <div>
              <dt>Assigned advisor</dt>
              <dd>{record.assigned_advisor.full_name}</dd>
            </div>
            <div>
              <dt>Completion state</dt>
              <dd>{readable(record.stored_status)}</dd>
            </div>
          </dl>
          <IntegrityRecovery
            record={record}
            token={token}
            user={user}
            busy={busy}
            mutate={async (work) => (await mutate(work))?.message ?? null}
            onDone={onRetry}
          />
          {record.outcome && (
            <section className="follow-recorded-outcome">
              <h3>Recorded outcome</h3>
              <strong>{readable(record.outcome)}</strong>
              <p>{record.notes}</p>
              <small>Completed {timestamp(record.completed_at)}</small>
            </section>
          )}
          {record.stored_status === "CANCELLED" && (
            <section className="follow-recorded-outcome">
              <h3>Cancellation reason</h3>
              <p>{record.notes || "No reason returned."}</p>
            </section>
          )}
          {record.stored_status === "SCHEDULED" &&
            !writable &&
            !resource.loading &&
            !resource.error && (
              <p className="follow-readonly">
                Read-only access. Changes require an academic administrator or
                the advisor assigned to both this follow-up and its
                intervention.
              </p>
            )}
          {record.stored_status !== "SCHEDULED" && (
            <p className="follow-readonly">
              This {record.stored_status.toLowerCase()} follow-up is a
              historical record.
            </p>
          )}
          {writable && !mode && (
            <div className="follow-detail-actions">
              <button
                className="dash-button dash-button-primary"
                disabled={busy}
                onClick={() => setMode("complete")}
              >
                Complete Follow-Up
              </button>
              <button
                className="dash-button"
                disabled={busy}
                onClick={() => setMode("edit")}
              >
                Reschedule / Edit
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
          {permitted && mode && (
            <section className="follow-action-section">
              <h3>
                {mode === "edit"
                  ? "Reschedule / Edit Follow-Up"
                  : mode === "complete"
                    ? "Complete Follow-Up"
                    : "Cancel Follow-Up"}
              </h3>
              <FollowUpForm
                key={`${id}:${mode}`}
                mode={mode}
                detail={record}
                token={token}
                user={user}
                disabled={!writable}
                mutate={mutate}
                onDone={() => setMode(null)}
                onCancel={() => setMode(null)}
              />
            </section>
          )}
          <Link
            className="follow-note-link"
            href={`/interventions?intervention_id=${encodeURIComponent(record.intervention_id)}`}
          >
            Open case notes in Interventions ↗
          </Link>
          <details className="follow-audit">
            <summary>Record information</summary>
            <dl className="follow-detail-values">
              <div>
                <dt>Created</dt>
                <dd>{timestamp(record.created_at)}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{timestamp(record.updated_at)}</dd>
              </div>
              <div>
                <dt>Created by user ID</dt>
                <dd>{record.created_by}</dd>
              </div>
              <div>
                <dt>Follow-up ID</dt>
                <dd>{record.id}</dd>
              </div>
            </dl>
          </details>
          <section className="follow-related" aria-label="Related follow-ups">
            <h3>Follow-ups for this intervention</h3>
            {related.loading && (
              <p role="status">Loading related follow-ups…</p>
            )}
            {related.error && (
              <div role="alert">
                <p>{related.error}</p>
                <button className="dash-button" onClick={onRetry}>
                  Retry related follow-ups
                </button>
              </div>
            )}
            {!related.loading &&
              !related.error &&
              related.data &&
              !related.data.items.length && (
                <p>No follow-ups recorded for this intervention.</p>
              )}
            {related.data?.items.map((item) => (
              <button
                className="follow-related-row"
                key={item.id}
                disabled={
                  busy || related.loading || !!related.error || item.id === id
                }
                onClick={() => onSelect(item.id)}
              >
                <span>{item.purpose}</span>
                <small>
                  {timestamp(item.scheduled_for)}
                  {item.id === id ? " · Selected record" : ""}
                </small>
                <DossierBadge value={item.effective_status} />
              </button>
            ))}
            {related.data && !related.loading && (
              <fieldset
                className="follow-pagination-wrap"
                disabled={busy || !!related.error}
              >
                <CaseworkPagination
                  data={related.data}
                  noun="related follow-ups"
                  onPage={setHistoryPage}
                />
              </fieldset>
            )}
          </section>
        </div>
      )}
    </aside>
  );
}
