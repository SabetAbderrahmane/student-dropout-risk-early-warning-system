import type { BatchPredictionResponse } from "@/types/dashboard";
import { timestamp } from "@/lib/dashboard";
import { Icon } from "@/components/dashboard/icon";
export function BatchPredictionResult({
  result,
  onClose,
}: {
  result: BatchPredictionResponse;
  onClose: () => void;
}) {
  return (
    <div
      className="dash-banner dash-success prediction-batch-result"
      role="status"
    >
      <div>
        <strong>Batch prediction completed</strong>
        <dl>
          {(
            [
              "assessed",
              "skipped_not_ready",
              "created_predictions",
              "created_warnings",
            ] as const
          ).map((key) => (
            <div key={key}>
              <dt>
                {
                  {
                    assessed: "Assessed",
                    skipped_not_ready: "Skipped: not ready",
                    created_predictions: "Predictions created",
                    created_warnings: "Warnings created",
                  }[key]
                }
              </dt>
              <dd>{result[key].toLocaleString()}</dd>
            </div>
          ))}
        </dl>
        <p>
          Model: {result.model_version} · Completed{" "}
          {timestamp(result.completed_at)}
        </p>
      </div>
      <button
        className="dash-icon-button"
        aria-label="Dismiss batch result"
        onClick={onClose}
      >
        <Icon name="close" />
      </button>
    </div>
  );
}
