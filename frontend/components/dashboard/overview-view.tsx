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
        Current risk combines each student's selected stage-specific risk tier, with
        separately calibrated thresholds. Historical assessments and support
        obligations are counted separately; probabilities are never averaged.
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
            {data.students.current_assessed.toLocaleString("en")} with a
            current assessment
          </span>
        </KpiCard>
        <KpiCard
          title="Active Warnings"
          value={data.warnings.active}
          icon="warning"
        >
          <span>Support workflows across historical assessments</span>
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
            {data.risk_distribution.low} LOW · {data.risk_distribution.medium} MEDIUM · {data.risk_distribution.high} HIGH
          </span>
          <span>One operational assessment per student</span>
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
      <p className="assessment-notice"><strong>{data.students.reassessment_required}</strong> students require reassessment · <strong>{data.students.without_predictions}</strong> have no prediction.</p>
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
          <span>Legacy binary model reference</span>
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
