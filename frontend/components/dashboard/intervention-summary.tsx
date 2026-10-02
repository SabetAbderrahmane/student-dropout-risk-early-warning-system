import type { DashboardOverview } from "@/types/dashboard";

export function InterventionSummary({ data }: { data: DashboardOverview }) {
  const { interventions: counts, follow_ups: followUps } = data;
  const stages = [
    { label: "Planned", value: counts.planned, color: "#c4c6cf" },
    { label: "In progress", value: counts.in_progress, color: "#022448" },
    {
      label: "Action required",
      value: counts.action_required,
      color: "#ba1a1a",
    },
    { label: "Completed", value: counts.completed, color: "#2d6197" },
  ];
  const total = stages.reduce((sum, stage) => sum + stage.value, 0);
  let offset = 0;
  return (
    <section
      className="dash-card dash-interventions"
      aria-labelledby="intervention-summary-title"
    >
      <div className="dash-section-heading">
        <div>
          <h2 id="intervention-summary-title">Intervention Status</h2>
          <p>Academic support and follow-up workload</p>
        </div>
      </div>
      <div className="dash-intervention-overview">
        <div className="dash-donut">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle
              cx="60"
              cy="60"
              r="49"
              fill="none"
              stroke="#e7eaf0"
              strokeWidth="9"
            />
            {stages.map((stage) => {
              const length = total ? (stage.value / total) * 100 : 0;
              const start = offset;
              offset += length;
              return (
                <circle
                  key={stage.label}
                  cx="60"
                  cy="60"
                  r="49"
                  fill="none"
                  stroke={stage.color}
                  strokeWidth="9"
                  pathLength="100"
                  strokeDasharray={`${length} ${100 - length}`}
                  strokeDashoffset={-start}
                  transform="rotate(-90 60 60)"
                />
              );
            })}
          </svg>
          <div>
            <strong>{counts.active.toLocaleString("en")}</strong>
            <small>Active</small>
          </div>
        </div>
        <dl className="dash-stage-list">
          {stages.map((stage) => (
            <div key={stage.label}>
              <dt>
                <i style={{ background: stage.color }} />
                {stage.label}
              </dt>
              <dd>{stage.value.toLocaleString("en")}</dd>
            </div>
          ))}
        </dl>
      </div>
      {total === 0 && (
        <p className="dash-subtle">
          No interventions recorded yet. Confirmed warnings can lead to an
          academic support plan.
        </p>
      )}
      <div className="dash-follow-ups">
        <div>
          <small>Follow-ups due today</small>
          <strong>{followUps.due_today.toLocaleString("en")}</strong>
        </div>
        <div className={followUps.overdue > 0 ? "dash-overdue" : ""}>
          <small>Overdue follow-ups</small>
          <strong>{followUps.overdue.toLocaleString("en")}</strong>
        </div>
      </div>
      <p className="dash-panel-note">
        Warning reviews and interventions are separate steps in the support
        workflow.
      </p>
    </section>
  );
}
