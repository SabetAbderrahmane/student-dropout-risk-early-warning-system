import { useState } from "react";
import type { DashboardOverview } from "@/types/dashboard";
import { calendarDate, percent } from "@/lib/dashboard";

export function WarningActivityChart({ data }: { data: DashboardOverview }) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const activity = data.warning_activity;
  const selected =
    activity.find((day) => day.date === selectedDate) ??
    activity[activity.length - 1];
  const maximum = Math.max(
    1,
    ...activity.map((day) =>
      Math.max(day.created, day.confirmed + day.dismissed),
    ),
  );
  const total =
    data.risk_distribution.low +
    data.risk_distribution.medium +
    data.risk_distribution.high;
  const width = 680,
    height = 190,
    left = 38,
    bottom = 155;
  const step = (width - left - 12) / Math.max(1, activity.length);
  return (
    <section
      className="dash-card dash-chart"
      aria-labelledby="warning-chart-title"
    >
      <div className="dash-section-heading">
        <div>
          <h2 id="warning-chart-title">
            Warning Activity <span>— Last 14 Days</span>
          </h2>
          <p>Created warnings and completed advisor reviews</p>
        </div>
        <span className="dash-tag">Daily activity</span>
      </div>
      <div className="dash-stratification">
        <div className="dash-inline">
          <strong>Cohort risk distribution</strong>
          <span>{total.toLocaleString("en")} with a risk classification</span>
        </div>
        <div className="dash-risk-track" aria-hidden="true">
          {(["low", "medium", "high"] as const).map((level) => (
            <span
              key={level}
              className={`dash-risk-${level}`}
              style={{
                width: `${total ? (data.risk_distribution[level] / total) * 100 : 0}%`,
              }}
            />
          ))}
        </div>
        <div className="dash-risk-legend">
          {(["low", "medium", "high"] as const).map((level) => (
            <span key={level}>
              <i className={`dash-risk-${level}`} />
              {level.charAt(0).toUpperCase() + level.slice(1)}{" "}
              <strong>
                {data.risk_distribution[level].toLocaleString("en")}
              </strong>
              {total > 0 && (
                <small>
                  ({percent(data.risk_distribution[level] / total)})
                </small>
              )}
            </span>
          ))}
        </div>
      </div>
      {activity.length === 0 ? (
        <div className="dash-empty dash-chart-empty">
          <strong>No warning activity yet</strong>
          <p>
            Recent activity will appear after warnings are created or reviewed.
          </p>
        </div>
      ) : (
        <>
          <svg
            className="dash-activity-svg"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Daily warnings created and reviewed. Exact values are available in the date buttons below."
          >
            {[0, 0.5, 1].map((ratio) => (
              <g key={ratio}>
                <line
                  x1={left}
                  x2={width}
                  y1={bottom - ratio * 130}
                  y2={bottom - ratio * 130}
                  stroke="#e7eaf0"
                  strokeDasharray="4 4"
                />
                <text
                  x={left - 8}
                  y={bottom - ratio * 130 + 4}
                  textAnchor="end"
                >
                  {Math.ceil(maximum * ratio)}
                </text>
              </g>
            ))}
            {activity.map((day, index) => {
              const x = left + step * index + step / 2,
                barHeight = (day.created / maximum) * 130;
              return (
                <g key={day.date}>
                  <title>
                    {calendarDate(day.date)}: {day.created} created,{" "}
                    {day.confirmed} confirmed, {day.dismissed} dismissed
                  </title>
                  <rect
                    x={x - Math.min(step * 0.27, 16)}
                    y={bottom - barHeight}
                    width={Math.min(step * 0.54, 32)}
                    height={barHeight}
                    rx="3"
                    fill="#adc8f5"
                  />
                  <text x={x} y={181} textAnchor="middle">
                    {index % Math.max(1, Math.ceil(activity.length / 7)) ===
                      0 || index === activity.length - 1
                      ? calendarDate(day.date)
                      : ""}
                  </text>
                </g>
              );
            })}
            <polyline
              points={activity
                .map(
                  (day, index) =>
                    `${left + step * index + step / 2},${bottom - ((day.confirmed + day.dismissed) / maximum) * 130}`,
                )
                .join(" ")}
              fill="none"
              stroke="#2d6197"
              strokeWidth="2.5"
            />
            {activity.map((day, index) => (
              <circle
                key={day.date}
                cx={left + step * index + step / 2}
                cy={bottom - ((day.confirmed + day.dismissed) / maximum) * 130}
                r="3"
                fill="#2d6197"
              />
            ))}
          </svg>
          <div
            className="dash-date-selector"
            aria-label="Inspect daily warning activity"
          >
            {activity.map((day) => (
              <button
                key={day.date}
                aria-pressed={selected?.date === day.date}
                onClick={() => setSelectedDate(day.date)}
                title={`${day.date}: ${day.created} created, ${day.confirmed} confirmed, ${day.dismissed} dismissed`}
              >
                {calendarDate(day.date)}
              </button>
            ))}
          </div>
          <div className="dash-chart-readout" aria-live="polite">
            <strong>{selected && calendarDate(selected.date)}</strong>
            <span>
              <i className="dash-risk-low" />
              Created <b>{selected?.created ?? 0}</b>
            </span>
            <span>
              <i className="dash-risk-medium" />
              Reviewed{" "}
              <b>{selected ? selected.confirmed + selected.dismissed : 0}</b>
            </span>
            <small>
              {selected?.confirmed ?? 0} confirmed · {selected?.dismissed ?? 0}{" "}
              dismissed
            </small>
          </div>
        </>
      )}
    </section>
  );
}
