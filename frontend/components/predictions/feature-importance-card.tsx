import type { ModelPerformance } from "@/types/prediction";
import { exportFeatureImportance } from "@/lib/predictions";
import { readable } from "@/lib/dashboard";
export function FeatureImportanceCard({
  performance,
  loading,
}: {
  performance: ModelPerformance | null;
  loading: boolean;
}) {
  const items = performance?.global_feature_importance ?? [];
  const max = Math.max(0, ...items.map((item) => Math.abs(item.importance)));
  return (
    <section className="prediction-card prediction-importance">
      <div className="prediction-card-heading">
        <div>
          <h2>Global Feature Importance</h2>
          <p className="prediction-muted">
            Permutation importance on development data · PR-AUC scoring
          </p>
        </div>
        <button
          className="dash-button"
          disabled={loading || !items.length}
          onClick={() => exportFeatureImportance(items)}
        >
          Export Feature Importance
        </button>
      </div>
      {loading ? (
        <div
          role="status"
          aria-label="Loading feature importance"
          className="prediction-loading-bars"
        >
          {[0, 1, 2, 3, 4].map((index) => (
            <div
              key={index}
              className="warning-skeleton warning-skeleton-row"
            />
          ))}
        </div>
      ) : !performance ? (
        <p className="prediction-empty">Feature importance is unavailable.</p>
      ) : !items.length ? (
        <p className="prediction-empty">
          No global feature importance returned.
        </p>
      ) : (
        <ol className="prediction-feature-bars">
          {items.map((item, index) => (
            <li key={`${item.feature}-${index}`}>
              <div>
                <strong>{item.label || readable(item.feature)}</strong>
                <span>
                  {new Intl.NumberFormat("en", {
                    maximumFractionDigits: 6,
                  }).format(item.importance)}{" "}
                  importance
                </span>
              </div>
              <div className="prediction-importance-track" aria-hidden="true">
                <span
                  style={{
                    width: `${max ? (Math.abs(item.importance) / max) * 100 : 0}%`,
                  }}
                />
              </div>
              <small>{item.feature}</small>
            </li>
          ))}
        </ol>
      )}
      <p className="prediction-card-note">
        Bar lengths show relative magnitude, scaled to the largest absolute
        returned importance. Values are not assumed to sum to one.
      </p>
    </section>
  );
}
