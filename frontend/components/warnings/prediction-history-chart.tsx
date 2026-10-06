import { useEffect, useRef, useState } from "react";
import { ApiError, fetchStudentPredictions } from "@/lib/api";
import { warningError } from "@/lib/warnings";
import { percent, timestamp } from "@/lib/dashboard";
import type { StudentPredictionPage } from "@/types/warning";

export function PredictionHistoryChart({
  token,
  studentId,
  onUnauthorized,
}: {
  token: string;
  studentId: string;
  onUnauthorized: () => void;
}) {
  const [data, setData] = useState<StudentPredictionPage | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const unauthorized = useRef(onUnauthorized);
  unauthorized.current = onUnauthorized;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    fetchStudentPredictions(token, studentId, page, 25, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 401)
          unauthorized.current();
        else setError(warningError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, studentId, page, retry]);
  // Only selected-student history is ordered here, never warning queue rows.
  const chronological = (data?.items ?? []).toSorted(
    (a, b) => Date.parse(a.predicted_at) - Date.parse(b.predicted_at),
  );
  const start = chronological.length
    ? Date.parse(chronological[0].predicted_at)
    : 0;
  const end = chronological.length
    ? Date.parse(chronological[chronological.length - 1].predicted_at)
    : 0;
  const points = chronological.map((item) => ({
    item,
    x:
      32 +
      (end > start
        ? ((Date.parse(item.predicted_at) - start) / (end - start)) * 456
        : 228),
    y: 140 - item.probability * 116,
  }));
  return (
    <section className="warning-prediction-history">
      <h3>Prediction history</h3>
      {loading && (
        <div
          className="warning-skeleton warning-chart-skeleton"
          role="status"
          aria-label="Loading prediction history"
        />
      )}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button
            className="dash-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry prediction history
          </button>
        </div>
      )}
      {data && !loading && data.items.length === 0 && (
        <p className="warning-muted">No prediction history recorded.</p>
      )}
      {data && !loading && data.items.length === 1 && (
        <p>
          <strong>{percent(data.items[0].probability)}</strong> ·{" "}
          {timestamp(data.items[0].predicted_at)}
          <span className="warning-muted">
            {" "}
            — One prediction recorded on this page; no trajectory is shown.
          </span>
        </p>
      )}
      {data && !loading && data.items.length > 1 && end > start && (
        <>
          <svg
            viewBox="0 0 520 168"
            role="img"
            aria-label="Risk probabilities over actual prediction dates for this history page"
          >
            <path
              d="M32 24H488 M32 82H488 M32 140H488"
              stroke="var(--chart-grid)"
              fill="none"
            />
            <text x="0" y="28">
              100%
            </text>
            <text x="6" y="144">
              0%
            </text>
            <polyline
              points={points.map(({ x, y }) => `${x},${y}`).join(" ")}
              fill="none"
              stroke="var(--chart-line)"
              strokeWidth="2.5"
            />
            {points.map(({ item, x, y }) => (
              <circle
                key={item.id}
                cx={x}
                cy={y}
                r="3.5"
                fill="var(--chart-line)"
              >
                <title>
                  {timestamp(item.predicted_at)} · {percent(item.probability)}
                </title>
              </circle>
            ))}
          </svg>
          <div className="warning-history-axis">
            <span>{timestamp(chronological[0].predicted_at)}</span>
            <span>
              {timestamp(chronological[chronological.length - 1].predicted_at)}
            </span>
          </div>
        </>
      )}
      {data && !loading && data.items.length > 1 && (
        <details>
          <summary>View prediction dates and values</summary>
          <ul>
            {chronological.map((item) => (
              <li key={item.id}>
                {timestamp(item.predicted_at)} · {percent(item.probability)} ·{" "}
                {item.model_version}
              </li>
            ))}
          </ul>
        </details>
      )}
      {data && !loading && data.total_pages > 1 && (
        <div className="warning-history-pagination">
          <span>
            History page {data.page} of {data.total_pages} · {data.total}{" "}
            predictions
          </span>
          <button
            className="dash-button"
            disabled={data.page <= 1}
            onClick={() => setPage(data.page - 1)}
          >
            Newer history
          </button>
          <button
            className="dash-button"
            disabled={data.page >= data.total_pages}
            onClick={() => setPage(data.page + 1)}
          >
            Older history
          </button>
        </div>
      )}
    </section>
  );
}
