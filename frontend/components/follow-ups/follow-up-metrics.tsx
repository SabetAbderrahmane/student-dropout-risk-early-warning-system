"use client";
import { fetchFollowUps } from "@/lib/api";
import type { FollowUpEffectiveStatus } from "@/types/casework";
import { useFollowUpResource } from "./use-follow-up-resource";

const cards: { status: FollowUpEffectiveStatus; label: string }[] = [
  { status: "OVERDUE", label: "Overdue" },
  { status: "DUE", label: "Due" },
  { status: "SCHEDULED", label: "Scheduled / Upcoming" },
  { status: "COMPLETED", label: "Completed" },
];
export function FollowUpMetrics({
  token,
  revision,
  report,
  onRetry,
}: {
  token: string;
  revision: number;
  report: (caught: unknown) => string;
  onRetry: () => void;
}) {
  const resource = useFollowUpResource(
    token,
    revision,
    async (signal) => {
      const results = await Promise.allSettled(
        cards.map((card) =>
          fetchFollowUps(
            token,
            { page: 1, page_size: 1, status: card.status },
            signal,
          ),
        ),
      );
      return results.map((result) =>
        result.status === "fulfilled"
          ? { total: result.value.total, error: "" }
          : { total: null, error: signal.aborted ? "" : report(result.reason) },
      );
    },
    report,
  );
  const errors = [
    ...new Set(resource.data?.map((item) => item.error).filter(Boolean) ?? []),
  ];
  return (
    <>
      <p className="follow-metric-context">
        Institution-wide follow-up totals · Queue filters apply below
      </p>
      <section
        className="follow-metrics"
        aria-label="Follow-up totals"
        aria-busy={resource.loading}
      >
        {cards.map((card, index) => (
          <article
            className={`follow-metric-${card.status.toLowerCase()}`}
            key={card.status}
          >
            <span>{card.label}</span>
            <strong>
              {resource.data?.[index].total?.toLocaleString() ?? "—"}
            </strong>
            <small>
              {resource.loading
                ? "Refreshing totals…"
                : resource.data?.[index].total === null
                  ? "Count unavailable"
                  : "Persisted follow-up records"}
            </small>
          </article>
        ))}
      </section>
      {(errors.length > 0 || resource.error) && (
        <div className="dash-banner dash-error" role="alert">
          <p>
            Some totals are unavailable. {resource.error || errors.join(" ")}
          </p>
          <button className="dash-button" onClick={onRetry}>
            Retry totals
          </button>
        </div>
      )}
    </>
  );
}
