import type { DashboardOverview } from "@/types/dashboard";
import type { ModelPerformance } from "@/types/prediction";
import { percent } from "@/lib/dashboard";
export function ModelKpiStrip({
  dashboard,
  performance,
  loading,
}: {
  dashboard: DashboardOverview | null;
  performance: ModelPerformance | null;
  loading: boolean;
}) {
  const counts = dashboard?.risk_distribution;
  const total = counts ? counts.low + counts.medium + counts.high : 0;
  const value = (text: string | undefined) =>
    loading ? (
      <span
        className="warning-skeleton prediction-kpi-skeleton"
        aria-label="Loading metric"
      />
    ) : (
      <strong className="prediction-kpi-value">{text ?? "—"}</strong>
    );
  return (
    <section
      className="prediction-kpis"
      aria-label="Student and model metrics"
      aria-busy={loading}
    >
      <article className="prediction-card">
        <h2>Students Assessed</h2>
        {value(dashboard?.students.with_latest_prediction.toLocaleString())}
        <p className="prediction-muted">
          {dashboard
            ? `${dashboard.students.total.toLocaleString()} registered · ${dashboard.students.prediction_ready.toLocaleString()} prediction ready`
            : "Unique students with a latest prediction"}
        </p>
      </article>
      <article className="prediction-card">
        <h2>Risk Distribution</h2>
        {value(counts?.high.toLocaleString())}
        <p className="prediction-muted">
          Students with a high-risk latest prediction
        </p>
        {counts && !loading && (
          <>
            <div
              className="prediction-distribution"
              aria-label={`Low ${counts.low}, medium ${counts.medium}, high ${counts.high}`}
            >
              {(["low", "medium", "high"] as const).map((risk) => (
                <span
                  key={risk}
                  className={`tier-${risk}`}
                  style={{
                    width: `${total ? (counts[risk] / total) * 100 : 0}%`,
                  }}
                />
              ))}
            </div>
            <div className="prediction-distribution-legend">
              {(["low", "medium", "high"] as const).map((risk) => (
                <span key={risk}>
                  {risk.charAt(0).toUpperCase() + risk.slice(1)}{" "}
                  <b>{counts[risk].toLocaleString()}</b>
                </span>
              ))}
            </div>
          </>
        )}
      </article>
      <article className="prediction-card">
        <h2>Predictive Performance</h2>
        {value(performance?.roc_auc.toFixed(3))}
        <p className="prediction-muted">ROC-AUC · Final Test Set</p>
        <div className="prediction-kpi-pair">
          <span>
            PR-AUC <b>{performance?.pr_auc.toFixed(3) ?? "—"}</b>
          </span>
          <span>
            F1 <b>{performance?.f1.toFixed(3) ?? "—"}</b>
          </span>
        </div>
      </article>
      <article className="prediction-card">
        <h2>Calibration / Reliability</h2>
        {value(performance?.brier_score.toFixed(3))}
        <p className="prediction-muted">Brier Score · Final Test Set</p>
        <div className="prediction-kpi-pair">
          <span>
            Accuracy <b>{performance ? percent(performance.accuracy) : "—"}</b>
          </span>
          <span>
            Precision{" "}
            <b>{performance ? percent(performance.precision) : "—"}</b>
          </span>
          <span>
            Recall <b>{performance ? percent(performance.recall) : "—"}</b>
          </span>
        </div>
      </article>
    </section>
  );
}
