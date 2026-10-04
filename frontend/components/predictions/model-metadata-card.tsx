import type { CurrentModel } from "@/types/prediction";
import { timestamp, percent } from "@/lib/dashboard";
export function ModelMetadataCard({
  model,
  loading,
}: {
  model: CurrentModel | null;
  loading: boolean;
}) {
  return (
    <section className="prediction-card">
      <h2>Model Metadata</h2>
      {loading ? (
        <div
          className="warning-skeleton prediction-metadata-skeleton"
          role="status"
          aria-label="Loading model metadata"
        />
      ) : !model ? (
        <p className="prediction-empty">
          No active model metadata is available.
        </p>
      ) : (
        <dl className="prediction-metadata">
          <dt>Model name</dt>
          <dd>{model.name}</dd>
          <dt>Model version</dt>
          <dd>{model.version}</dd>
          <dt>Dataset</dt>
          <dd>{model.dataset.name}</dd>
          <dt>Dataset ID</dt>
          <dd>{model.dataset.dataset_id}</dd>
          <dt>Feature schema</dt>
          <dd>{model.feature_schema_version}</dd>
          <dt>Trained at</dt>
          <dd>{timestamp(model.trained_at)}</dd>
          <dt>Artifact available</dt>
          <dd>{model.artifact_available ? "Yes" : "No"}</dd>
        </dl>
      )}
    </section>
  );
}
export function RiskThresholdCard({
  model,
  loading,
}: {
  model: CurrentModel | null;
  loading: boolean;
}) {
  return (
    <section className="prediction-card">
      <div className="prediction-card-heading">
        <h2>Risk Thresholds</h2>
        <span className="prediction-readonly-label">Read-only</span>
      </div>
      <p className="prediction-muted">
        Calibrated thresholds from the current model metadata.
      </p>
      {loading ? (
        <div
          className="warning-skeleton prediction-metadata-skeleton"
          role="status"
          aria-label="Loading risk thresholds"
        />
      ) : !model ? (
        <p className="prediction-empty">Risk thresholds are unavailable.</p>
      ) : (
        <>
          <div className="prediction-threshold-values">
            <div>
              <span>Low threshold</span>
              <strong>{model.low_threshold}</strong>
            </div>
            <div>
              <span>High threshold</span>
              <strong>{model.high_threshold}</strong>
            </div>
          </div>
          <ul className="prediction-tier-rules">
            <li>
              <b>Low</b>
              <span>Probability &lt; {percent(model.low_threshold)}</span>
            </li>
            <li>
              <b>Medium</b>
              <span>
                {percent(model.low_threshold)} ≤ probability &lt;{" "}
                {percent(model.high_threshold)}
              </span>
            </li>
            <li>
              <b>High</b>
              <span>Probability ≥ {percent(model.high_threshold)}</span>
            </li>
          </ul>
          <p className="prediction-card-note">
            Risk badges use each prediction's backend classification. These
            thresholds cannot be edited here.
          </p>
        </>
      )}
    </section>
  );
}
