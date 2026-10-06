import { readable, timestamp } from "@/lib/dashboard";
import { DossierBadge } from "@/components/dossier/dossier-records";
import { CaseworkPagination } from "@/components/casework/pagination";
import type { FollowUpPage } from "@/types/casework";

export function FollowUpQueue({
  data,
  loading,
  error,
  selectedId,
  busy,
  onSelect,
  onRetry,
  onPage,
  onSize,
}: {
  data: FollowUpPage | null;
  loading: boolean;
  error: string;
  selectedId: string | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onRetry: () => void;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
}) {
  return (
    <section
      className="follow-queue"
      aria-labelledby="follow-queue-heading"
      aria-busy={loading}
    >
      <header className="follow-panel-heading">
        <div>
          <p className="dash-eyebrow">Operational queue</p>
          <h2 id="follow-queue-heading">Follow-up records</h2>
        </div>
        <span>
          {data ? `${data.total.toLocaleString()} matching records` : ""}
        </span>
      </header>
      {error && (
        <div className="follow-load-error" role="alert">
          <p>{error}</p>
          {data && (
            <p>Showing the last successful response. Refresh before acting.</p>
          )}
          <button className="dash-button" onClick={onRetry}>
            Retry queue
          </button>
        </div>
      )}
      {loading && (
        <div className="follow-loading" role="status">
          Loading follow-ups…
        </div>
      )}
      {!loading && !error && data && !data.items.length && (
        <div className="follow-empty">
          <strong>No follow-ups match this view.</strong>
          <p>
            Choose another status or clear the filters to see other records.
          </p>
        </div>
      )}
      <div className="follow-queue-rows">
        {data?.items.map((item) => (
          <button
            key={item.id}
            disabled={busy || loading || !!error}
            className={`follow-queue-row ${item.effective_status === "OVERDUE" ? "is-overdue" : ""} ${item.id === selectedId ? "is-selected" : ""}`}
            aria-pressed={item.id === selectedId}
            aria-controls="selected-follow-up"
            aria-label={`Open follow-up for ${item.student.name}: ${item.purpose}`}
            onClick={() => onSelect(item.id)}
          >
            <div className="follow-row-identity">
              <span className="follow-student-initials" aria-hidden="true">
                {item.student.name
                  .split(" ")
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((word) => word[0])
                  .join("")}
              </span>
              <div>
                <strong>{item.student.name}</strong>
                <small>{item.student.student_number}</small>
              </div>
              <DossierBadge value={item.effective_status} />
            </div>
            <p>{item.purpose}</p>
            <div className="follow-row-meta">
              <time dateTime={item.scheduled_for}>
                {timestamp(item.scheduled_for)}
              </time>
              <span>{readable(item.method)}</span>
              <span>{item.assigned_advisor.full_name}</span>
            </div>
          </button>
        ))}
      </div>
      {data && !loading && (
        <fieldset className="follow-pagination-wrap" disabled={busy || !!error}>
          <CaseworkPagination
            data={data}
            noun="follow-ups"
            onPage={onPage}
            onSize={onSize}
          />
        </fieldset>
      )}
    </section>
  );
}
