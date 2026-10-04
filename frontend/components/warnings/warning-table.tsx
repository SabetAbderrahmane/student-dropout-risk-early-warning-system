import Link from "next/link";
import type { User } from "@/types/auth";
import type { WarningPage, WarningRow } from "@/types/warning";
import { percent, readable, timestamp } from "@/lib/dashboard";
import { canReviewWarning } from "@/lib/warnings";
import { Icon } from "@/components/dashboard/icon";

export function WarningBadge({ value }: { value: string }) {
  return (
    <span className={`warning-badge state-${value.toLowerCase()}`}>
      {readable(value)}
    </span>
  );
}
export function WarningTable({
  data,
  user,
  loading,
  error,
  compact,
  onOpen,
  onRetry,
  onPage,
  onPageSize,
  onClear,
}: {
  data: WarningPage | null;
  user: User | null;
  loading: boolean;
  error: string;
  compact: boolean;
  onOpen: (warning: WarningRow) => void;
  onRetry: () => void;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
  onClear: () => void;
}) {
  const first =
    data && data.items.length ? (data.page - 1) * data.page_size + 1 : 0;
  return (
    <section
      className={`warning-queue ${compact ? "is-compact" : ""}`}
      aria-label="Warning queue"
      aria-busy={loading}
    >
      <div className="warning-queue-heading">
        <h2>
          Advisor triage queue{" "}
          {data && (
            <span className="warning-count">{data.total.toLocaleString()}</span>
          )}
        </h2>
        <span className="warning-muted">
          Individual review · Evidence-led support
        </span>
      </div>
      {loading && (
        <div
          className="warning-table-loading"
          role="status"
          aria-label="Loading warning queue"
        >
          {[0, 1, 2, 3, 4].map((value) => (
            <div
              key={value}
              className="warning-skeleton warning-skeleton-row"
            />
          ))}
        </div>
      )}
      {error && (
        <div className="warning-empty" role="alert">
          <Icon name="warning" />
          <strong>Unable to load warnings</strong>
          <p>{error}</p>
          <button className="dash-button" onClick={onRetry}>
            Retry queue
          </button>
        </div>
      )}
      {!loading && !error && data?.items.length === 0 && (
        <div className="warning-empty">
          <Icon name="check" />
          <strong>No warnings found</strong>
          <p>
            No warning records match this queue. Adjust the filters or check
            again later.
          </p>
          <button className="dash-button" onClick={onClear}>
            Clear filters
          </button>
          {data.total > 0 && (
            <button className="dash-button" onClick={() => onPage(1)}>
              Return to first page
            </button>
          )}
        </div>
      )}
      {!loading && !error && !!data?.items.length && (
        <div
          className="warning-table-scroll"
          role="region"
          aria-label="Warning records, scroll for more columns"
          tabIndex={0}
        >
          <table className="warning-table">
            <thead>
              <tr>
                {[
                  "Priority",
                  "Student",
                  "Risk assessment",
                  "Top explanation factors",
                  "Warning created",
                  "Review state",
                  "Assigned advisor",
                  "Actions",
                ].map((label) => (
                  <th key={label} scope="col">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((warning) => (
                <tr key={warning.id}>
                  <td>
                    <WarningBadge value={warning.priority} />
                  </td>
                  <td>
                    <div className="warning-student">
                      <span className="warning-avatar" aria-hidden="true">
                        {warning.student_name
                          .split(/\s+/)
                          .filter(Boolean)
                          .slice(0, 2)
                          .map((word) => word[0])
                          .join("")}
                      </span>
                      <div>
                        <strong>{warning.student_name}</strong>
                        <small className="warning-mono">
                          {warning.student_number}
                        </small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="warning-risk">
                      <strong>{percent(warning.probability)}</strong>
                      <WarningBadge value={warning.risk_level} />
                    </div>
                    <meter
                      min={0}
                      max={1}
                      value={warning.probability}
                      aria-label={`${warning.student_name} risk probability`}
                    />
                  </td>
                  <td>
                    {warning.top_explanation_factors.length ? (
                      <ul className="warning-factor-list">
                        {warning.top_explanation_factors.map(
                          (factor, index) => (
                            <li key={`${factor.feature}-${index}`}>
                              {factor.label || readable(factor.feature)}
                            </li>
                          ),
                        )}
                      </ul>
                    ) : (
                      <span className="warning-muted">
                        No explanation factors available
                      </span>
                    )}
                  </td>
                  <td>
                    <span>{timestamp(warning.created_at)}</span>
                    <small>Predicted {timestamp(warning.predicted_at)}</small>
                  </td>
                  <td>
                    <WarningBadge value={warning.review_state} />
                  </td>
                  <td>
                    {warning.assigned_advisor ? (
                      warning.assigned_advisor.full_name
                    ) : (
                      <span className="warning-muted">
                        Unassigned<small>Awaiting assignment</small>
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="warning-row-actions">
                      <button
                        className={`dash-button ${user && canReviewWarning(user, warning) ? "dash-button-primary" : ""}`}
                        onClick={() => onOpen(warning)}
                        aria-label={`${user && canReviewWarning(user, warning) ? "Review warning" : "View warning"} for ${warning.student_name}`}
                      >
                        {user && canReviewWarning(user, warning)
                          ? "Review warning"
                          : "View warning"}
                      </button>
                      <Link
                        href={`/students/${encodeURIComponent(warning.student_id)}`}
                        aria-label={`Open student profile for ${warning.student_name}`}
                      >
                        Student profile <span aria-hidden="true">↗</span>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && !loading && !error && (
        <footer className="warning-pagination">
          <span>
            {first.toLocaleString()}–
            {(first ? first + data.items.length - 1 : 0).toLocaleString()} of{" "}
            <strong>{data.total.toLocaleString()}</strong> warnings
          </span>
          <div>
            <label>
              Rows per page
              <select
                value={data.page_size}
                onChange={(event) => onPageSize(Number(event.target.value))}
              >
                {[25, 50, 100].map((size) => (
                  <option key={size}>{size}</option>
                ))}
              </select>
            </label>
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            <button
              className="dash-button"
              disabled={data.page <= 1}
              onClick={() => onPage(data.page - 1)}
            >
              Previous
            </button>
            <button
              className="dash-button"
              disabled={data.page >= data.total_pages}
              onClick={() => onPage(data.page + 1)}
            >
              Next
            </button>
          </div>
        </footer>
      )}
    </section>
  );
}
