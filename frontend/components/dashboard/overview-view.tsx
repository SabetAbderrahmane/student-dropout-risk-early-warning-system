import type { User } from "@/types/auth";
import type { AttentionStudent, DashboardOverview } from "@/types/dashboard";
import { percent, timestamp } from "@/lib/dashboard";
import { KpiCard } from "./kpi-card";
import { WarningActivityChart } from "./warning-activity-chart";
import { InterventionSummary } from "./intervention-summary";
import { AttentionTable } from "./attention-table";

export function OverviewView({
  data,
  user,
  disabled,
  onReview,
  onIntervene,
}: {
  data: DashboardOverview;
  user: User;
  disabled: boolean;
  onReview: (student: AttentionStudent) => void;
  onIntervene: (student: AttentionStudent) => void;
}) {
  return (
    <>
      <p className="dash-description">
        Risk counts, readiness, and model thresholds show legacy binary
        first-semester assessments. Warning and support totals include all
        prediction stages. Review enrollment and multiclass results in
        Prediction Analytics.
      </p>
      <div className="dash-kpi-grid">
        <KpiCard
          title="Total Students"
          value={data.students.total}
          icon="students"
        >
          <span>
            {data.students.prediction_ready.toLocaleString("en")} prediction
            ready
          </span>
          <span>
            {data.students.with_latest_prediction.toLocaleString("en")} with a
            latest prediction
          </span>
        </KpiCard>
        <KpiCard
          title="Active Warnings"
          value={data.warnings.active}
          icon="warning"
        >
          <span>Current academic warning caseload</span>
          <span>
            {data.warnings.confirmed.toLocaleString("en")} confirmed ·{" "}
            {data.warnings.dismissed.toLocaleString("en")} dismissed
          </span>
        </KpiCard>
        <KpiCard
          title="High-Risk Students"
          value={data.risk_distribution.high}
          icon="activity"
          danger
        >
          <span>
            {data.model.high_threshold === null
              ? "Model threshold not available"
              : `Model threshold: P ≥ ${percent(data.model.high_threshold)}`}
          </span>
          <span>Latest legacy binary assessment per student</span>
        </KpiCard>
        <KpiCard
          title="Pending Reviews"
          value={data.warnings.pending_review}
          icon="shield"
        >
          <span>Awaiting an advisor decision</span>
          <span>Confirm or dismiss with a review note</span>
        </KpiCard>
      </div>
      <div className="dash-analytics-grid">
        <WarningActivityChart data={data} />
        <InterventionSummary data={data} />
      </div>
      <AttentionTable
        students={data.attention_students}
        user={user}
        disabled={disabled}
        onReview={onReview}
        onIntervene={onIntervene}
      />
      <footer className="dash-provenance">
        <div>
          <span>Data freshness</span>
          <p>
            Last successful import:{" "}
            <strong>{timestamp(data.data_freshness.last_import_at)}</strong>
          </p>
          <p>
            Last prediction:{" "}
            <strong>{timestamp(data.data_freshness.last_prediction_at)}</strong>
          </p>
        </div>
        <div>
          <span>Active model</span>
          <p>
            <strong>{data.model.name ?? "No active model"}</strong>
            {data.model.version && ` · ${data.model.version}`}
          </p>
          <p>
            Trained: <strong>{timestamp(data.model.trained_at)}</strong>
          </p>
          <p>
            Low threshold:{" "}
            {data.model.low_threshold === null
              ? "Not available"
              : percent(data.model.low_threshold)}{" "}
            · High threshold:{" "}
            {data.model.high_threshold === null
              ? "Not available"
              : percent(data.model.high_threshold)}
          </p>
        </div>
      </footer>
    </>
  );
}
