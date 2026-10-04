import type { ModelPerformance } from "@/types/prediction";
import { percent, readable } from "@/lib/dashboard";
export function PerformanceCard({
  performance,
  loading,
}: {
  performance: ModelPerformance | null;
  loading: boolean;
}) {
  const matrix = performance?.confusion_matrix;
  return (
    <section className="prediction-card">
      <h2>Final Test Performance</h2>
      <p className="prediction-muted">
        Performance metrics are from the final held-out test set.
      </p>
      {loading ? (
        <div
          role="status"
          aria-label="Loading model performance"
          className="warning-skeleton prediction-performance-skeleton"
        />
      ) : !performance || !matrix ? (
        <p className="prediction-empty">Model performance is unavailable.</p>
      ) : (
        <>
          <div className="prediction-performance-metrics">
            {(["recall", "precision", "f1", "accuracy"] as const).map((key) => (
              <div key={key}>
                <span>{key === "f1" ? "F1" : readable(key)}</span>
                <strong>
                  {key === "f1"
                    ? performance[key].toFixed(3)
                    : percent(performance[key])}
                </strong>
              </div>
            ))}
          </div>
          <div className="prediction-matrix-heading">
            <h3>Final Test Confusion Matrix</h3>
            <p>
              Evaluation Scope: {readable(performance.evaluation_scope)} · N ={" "}
              {performance.sample_size.toLocaleString()}
            </p>
          </div>
          <table className="prediction-confusion">
            <caption className="prediction-sr-only">
              Binary dropout versus non-dropout evaluation on the final held-out
              test set
            </caption>
            <thead>
              <tr>
                <th scope="col">Actual / Predicted</th>
                <th scope="col">Dropout</th>
                <th scope="col">Non-dropout</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Dropout</th>
                <td className="matrix-tp">
                  <span>TP</span>
                  <strong>{matrix.tp.toLocaleString()}</strong>
                  <small>Dropout cases correctly identified</small>
                </td>
                <td className="matrix-fn">
                  <span>FN</span>
                  <strong>{matrix.fn.toLocaleString()}</strong>
                  <small>Dropout cases missed</small>
                </td>
              </tr>
              <tr>
                <th scope="row">Non-dropout</th>
                <td className="matrix-fp">
                  <span>FP</span>
                  <strong>{matrix.fp.toLocaleString()}</strong>
                  <small>Non-dropout cases incorrectly flagged</small>
                </td>
                <td className="matrix-tn">
                  <span>TN</span>
                  <strong>{matrix.tn.toLocaleString()}</strong>
                  <small>Non-dropout cases correctly classified</small>
                </td>
              </tr>
            </tbody>
          </table>
          <p className="prediction-card-note">
            This binary evaluation is separate from the operational Low / Medium
            / High risk tiers.
          </p>
        </>
      )}
    </section>
  );
}
