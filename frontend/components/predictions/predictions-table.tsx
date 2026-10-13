import Link from "next/link";
import type { PredictionPage, PredictionRow } from "@/types/prediction";
import { percent, readable, timestamp } from "@/lib/dashboard";
import { stageLabel } from "@/types/outcome";
export function PredictionRiskBadge({ risk }: { risk: string }) {
  return (
    <span className={`warning-badge state-${risk.toLowerCase()}`}>
      {readable(risk)}
    </span>
  );
}
export function PredictionsTable({
  data,
  loading,
  error,
  compact,
  onOpen,
  onRetry,
  onPage,
  onPageSize,
  onClear,
}: {
  data: PredictionPage | null;
  loading: boolean;
  error: string;
  compact: boolean;
  onOpen: (row: PredictionRow) => void;
  onRetry: () => void;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
  onClear: () => void;
}) {
  const first = data?.items.length ? (data.page - 1) * data.page_size + 1 : 0;
  return (
    <section
      className={`warning-queue prediction-table-card ${compact ? "is-compact" : ""}`}
      aria-label="Prediction matrix"
      aria-busy={loading}
    >
      <div className="warning-queue-heading">
        <h2>
          Prediction Matrix{" "}
          {data && (
            <span className="warning-count">{data.total.toLocaleString()}</span>
          )}
        </h2>
        <span className="prediction-muted">
          Prediction records · Includes historical assessments
        </span>
      </div>
      {loading && (
        <div
          className="warning-table-loading"
          role="status"
          aria-label="Loading prediction matrix"
        >
          {[0, 1, 2, 3].map((value) => (
            <div
              key={value}
              className="warning-skeleton warning-skeleton-row"
            />
          ))}
        </div>
      )}
      {error && (
        <div className="warning-empty" role="alert">
          <strong>Unable to load predictions</strong>
          <p>{error}</p>
          <button className="dash-button" onClick={onRetry}>
            Retry predictions
          </button>
        </div>
      )}
      {!loading && !error && data?.items.length === 0 && (
        <div className="warning-empty">
          <strong>No predictions found</strong>
          <p>
            No prediction records match the current query. Adjust the filters or
            run a batch prediction with an authorized account.
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
          tabIndex={0}
          role="region"
          aria-label="Prediction records, scroll for more columns"
        >
          <table className="prediction-table">
            <thead>
              <tr>
                {[
                  "Student",
                  "Stage / outcome",
                  "Risk probability",
                  "Risk level",
                  "Top explanation factors",
                  "Model version",
                  "Predicted at",
                  "Actions",
                ].map((label) => (
                  <th key={label} scope="col">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    <strong>{row.student_name}</strong>
                    <small>{row.student_number}</small>
                  </td>
                  <td>
                    <strong>
                      {stageLabel(
                        row.model_target_type === "BINARY_DROPOUT"
                          ? "LEGACY"
                          : row.prediction_stage,
                      )}
                    </strong>
                    <small>
                      {row.predicted_outcome
                        ? readable(row.predicted_outcome)
                        : "Binary assessment"}
                    </small>
                  </td>
                  <td>
                    <strong>{percent(row.probability)}</strong>
                    <meter
                      min={0}
                      max={1}
                      value={row.probability}
                      aria-label={`${row.student_name} risk probability`}
                    />
                  </td>
                  <td>
                    <PredictionRiskBadge risk={row.risk_level} />
                  </td>
                  <td>
                    {row.top_explanation_factors.length ? (
                      <ul className="warning-factor-list">
                        {row.top_explanation_factors
                          .slice(0, 3)
                          .map((factor, index) => (
                            <li key={`${factor.feature}-${index}`}>
                              {factor.label || readable(factor.feature)}
                            </li>
                          ))}
                      </ul>
                    ) : (
                      <span className="prediction-muted">
                        No explanation factors available
                      </span>
                    )}
                  </td>
                  <td className="prediction-version">{row.model_version}</td>
                  <td>{timestamp(row.predicted_at)}</td>
                  <td>
                    <div className="warning-row-actions">
                      <button
                        className="dash-button"
                        aria-label={`View prediction for ${row.student_name}`}
                        onClick={() => onOpen(row)}
                      >
                        View prediction
                      </button>
                      <Link
                        href={`/students/${encodeURIComponent(row.student_id)}`}
                        aria-label={`Open student profile for ${row.student_name}`}
                      >
                        Student profile ↗
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
            <strong>{data.total.toLocaleString()}</strong> prediction records
          </span>
          <div>
            <label>
              Rows per page
              <select
                value={data.page_size}
                onChange={(event) => onPageSize(Number(event.target.value))}
              >
                {[25, 50, 100].map((value) => (
                  <option key={value}>{value}</option>
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
