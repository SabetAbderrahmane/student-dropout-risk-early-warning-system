import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError, fetchPrediction } from "@/lib/api";
import { predictionError } from "@/lib/predictions";
import { readable, percent, timestamp } from "@/lib/dashboard";
import type { PredictionRow, PredictionDetail } from "@/types/prediction";
import { ActionModal } from "@/components/dashboard/action-modal";
import { ExplanationFactors } from "@/components/warnings/explanation-factors";
import { PredictionHistoryChart } from "@/components/warnings/prediction-history-chart";
import { PredictionRiskBadge } from "./predictions-table";
import { OutcomeSummary } from "./outcome-summary";
export function PredictionDetailModal({
  row,
  token,
  onClose,
  onUnauthorized,
}: {
  row: PredictionRow;
  token: string;
  onClose: () => void;
  onUnauthorized: () => void;
}) {
  const [detail, setDetail] = useState<PredictionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const unauthorized = useRef(onUnauthorized);
  unauthorized.current = onUnauthorized;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setDetail(null);
    fetchPrediction(token, row.id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setDetail(data);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 401)
          unauthorized.current();
        else setError(predictionError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, row.id, retry]);
  return (
    <ActionModal
      title="Prediction Detail"
      className="warning-detail-modal prediction-detail-modal"
      busy={false}
      onClose={onClose}
    >
      <div className="warning-detail-identity">
        <div>
          <strong>{detail?.student_name ?? row.student_name}</strong>
          <span className="warning-mono">
            {detail?.student_number ?? row.student_number}
          </span>
        </div>
        <Link href={`/students/${encodeURIComponent(row.student_id)}`}>
          Open Student Profile ↗
        </Link>
      </div>
      {loading && (
        <div
          className="warning-detail-loading"
          role="status"
          aria-label="Loading prediction detail"
        >
          <div className="warning-skeleton warning-skeleton-row" />
          <div className="warning-skeleton warning-chart-skeleton" />
        </div>
      )}
      {error && (
        <div className="dash-inline-error" role="alert">
          <p>{error}</p>
          <button
            className="dash-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry prediction detail
          </button>
        </div>
      )}
      {detail && !loading && (
        <>
          <div className="warning-detail-risk">
            <div>
              <strong>{percent(detail.probability)}</strong>
              <span>Risk probability</span>
            </div>
            <PredictionRiskBadge risk={detail.risk_level} />
          </div>
          <OutcomeSummary prediction={detail} />
          <dl className="warning-detail-meta">
            <dt>Model version</dt>
            <dd>{detail.model_version}</dd>
            <dt>Predicted at</dt>
            <dd>{timestamp(detail.predicted_at)}</dd>
            <dt>Explanation method</dt>
            <dd>{detail.explanation_method}</dd>
            <dt>Created by</dt>
            <dd>{detail.created_by ?? "Not recorded"}</dd>
          </dl>
          <ExplanationFactors factors={detail.top_explanation_factors} />
          <p className="prediction-explanation-note">
            Positive contributions increase estimated dropout risk; negative
            contributions decrease it, under the backend explanation method.
          </p>
          <details className="prediction-feature-snapshot">
            <summary>
              Input Feature Snapshot (
              {Object.keys(detail.feature_snapshot).length})
            </summary>
            {Object.keys(detail.feature_snapshot).length ? (
              <dl className="prediction-metadata">
                {Object.entries(detail.feature_snapshot).map(
                  ([feature, value]) => (
                    <div key={feature}>
                      <dt>
                        {detail.top_explanation_factors.find(
                          (factor) => factor.feature === feature,
                        )?.label || readable(feature)}
                        <small>{feature}</small>
                      </dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ),
                )}
              </dl>
            ) : (
              <p>No input features recorded.</p>
            )}
          </details>
        </>
      )}
      <PredictionHistoryChart
        token={token}
        studentId={row.student_id}
        onUnauthorized={onUnauthorized}
      />
      <div className="prediction-detail-footer">
        <Link className="dash-button" href="/warnings">
          Open Warning Queue
        </Link>
      </div>
    </ActionModal>
  );
}
