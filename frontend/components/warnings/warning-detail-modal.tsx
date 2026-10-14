import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchWarning,
  reviewWarning,
  reconsiderWarning,
} from "@/lib/api";
import {
  canReviewWarning,
  canReconsiderWarning,
  canCreateWarningIntervention,
  warningError,
} from "@/lib/warnings";
import { percent, readable, timestamp } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import type { ReviewWarningInput, ReviewDecision } from "@/types/dashboard";
import type { WarningDetail, WarningRow } from "@/types/warning";
import { ActionModal } from "@/components/dashboard/action-modal";
import { WarningBadge } from "./warning-table";
import { ExplanationFactors } from "./explanation-factors";
import { PredictionHistoryChart } from "./prediction-history-chart";
import { WarningReviewForm } from "./warning-review-form";

export function WarningDetailModal({
  token,
  user,
  row,
  onClose,
  onUnauthorized,
  onReviewed,
  onIntervention,
}: {
  token: string;
  user: User;
  row: WarningRow;
  onClose: () => void;
  onUnauthorized: () => void;
  onReviewed: (decision: ReviewDecision) => void;
  onIntervention: (warning: WarningDetail) => void;
}) {
  const [detail, setDetail] = useState<WarningDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const unauthorized = useRef(onUnauthorized);
  unauthorized.current = onUnauthorized;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchWarning(token, row.id, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setDetail(result);
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
  }, [token, row.id, retry]);
  async function submit(payload: ReviewWarningInput): Promise<string | null> {
    if (
      !detail ||
      !(canReviewWarning(user, detail) || canReconsiderWarning(user, detail))
    )
      return "Only the assigned academic advisor may review a pending warning.";
    try {
      const result =
        detail.review_state === "PENDING_REVIEW"
          ? await reviewWarning(token, detail.id, {
              ...payload,
              expected_revision: detail.revision,
            })
          : await reconsiderWarning(token, detail.id, {
              ...payload,
              reason: payload.reason!,
              expected_revision: detail.revision,
            });
      setDetail(result);
      setSuccess(
        `Warning ${readable(result.review_state).toLowerCase()} successfully. Intervention creation remains a separate action.`,
      );
      onReviewed(payload.decision);
      setRetry((value) => value + 1);
      return null;
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) onUnauthorized();
      if (caught instanceof ApiError && caught.status === 409) {
        try {
          setDetail(await fetchWarning(token, row.id));
        } catch (refreshError) {
          setDetail(null);
          setError(warningError(refreshError));
        }
      }
      return warningError(caught);
    }
  }
  return (
    <ActionModal
      title="Warning detail & advisor review"
      className="warning-detail-modal"
      busy={busy}
      onClose={onClose}
    >
      <div className="warning-detail-identity">
        <div>
          <strong>{detail?.student.name ?? row.student_name}</strong>
          <span className="warning-mono">
            {detail?.student.student_number ?? row.student_number}
          </span>
        </div>
        <Link href={`/students/${encodeURIComponent(row.student_id)}`}>
          Open Student Profile ↗
        </Link>
      </div>
      {success && (
        <div className="warning-detail-success" role="status">
          {success}
        </div>
      )}
      {loading && (
        <div
          role="status"
          aria-label="Loading warning detail"
          className="warning-detail-loading"
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
            Retry warning detail
          </button>
        </div>
      )}
      {detail && !loading && !error && (
        <>
          <div className="warning-detail-risk">
            <div>
              <strong>{percent(detail.probability)}</strong>
              <span>Historical warning risk probability</span>
            </div>
            <div>
              <WarningBadge value={detail.risk_level} />
              <WarningBadge value={detail.priority} />
              <WarningBadge value={detail.review_state} />
            </div>
          </div>
          <dl className="warning-detail-meta">
            <dt>Assigned advisor</dt>
            <dd>
              {detail.assigned_advisor?.full_name ??
                "Unassigned · Awaiting assignment"}
            </dd>
            <dt>Warning created</dt>
            <dd>{timestamp(detail.created_at)}</dd>
            <dt>Prediction timestamp</dt>
            <dd>{timestamp(detail.predicted_at)}</dd>
            <dt>Model version</dt>
            <dd>{detail.model_version}</dd>
          </dl>
          <ExplanationFactors factors={detail.prediction_explanation} />
        </>
      )}
      <PredictionHistoryChart
        token={token}
        studentId={row.student_id}
        onUnauthorized={onUnauthorized}
      />
      {detail && !loading && !error && (
        <>
          <section>
            <h3>Review history</h3>
            {detail.review_history.length === 0 ? (
              <p className="warning-muted">No advisor reviews recorded.</p>
            ) : (
              <ol className="warning-review-history">
                {detail.review_history.map((review) => (
                  <li key={review.id}>
                    <div>
                      <WarningBadge value={review.decision} />
                      <small>{timestamp(review.reviewed_at)}</small>
                    </div>
                    <strong>{review.reviewer_name}</strong>
                    <p>{review.note}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
          {canReviewWarning(user, detail) ||
          canReconsiderWarning(user, detail) ? (
            <WarningReviewForm
              onSubmit={submit}
              onBusy={setBusy}
              reconsider={detail.review_state !== "PENDING_REVIEW"}
            />
          ) : (
            <div className="warning-readonly">
              <strong>
                {!detail.assigned_advisor
                  ? "Awaiting assignment"
                  : "Read-only review record"}
              </strong>
              <p>
                {!detail.assigned_advisor
                  ? "An academic administrator must assign this warning before an advisor can review it."
                  : detail.review_state !== "PENDING_REVIEW"
                    ? "This warning already has a review decision."
                    : "Only this warning's assigned academic advisor may submit a review."}
              </p>
            </div>
          )}
          {canCreateWarningIntervention(user, detail) && (
            <div className="warning-next-step">
              <div>
                <h3>Plan academic support</h3>
                <p className="warning-muted">
                  This confirmed warning is eligible for a separate
                  intervention.
                </p>
              </div>
              <button
                className="dash-button dash-button-primary"
                disabled={busy}
                onClick={() => onIntervention(detail)}
              >
                Create Intervention
              </button>
            </div>
          )}
        </>
      )}
    </ActionModal>
  );
}
