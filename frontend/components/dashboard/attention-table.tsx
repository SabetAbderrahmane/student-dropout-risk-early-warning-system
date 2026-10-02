import Link from "next/link";
import { useState } from "react";
import type { User } from "@/types/auth";
import type { AttentionStudent } from "@/types/dashboard";
import {
  canIntervene,
  canReview,
  factorLabel,
  percent,
  readable,
  timestamp,
} from "@/lib/dashboard";
import { Icon } from "./icon";

const filters = ["All", "High Risk", "Pending Review", "Confirmed"] as const;
export function AttentionTable({
  students,
  user,
  disabled,
  onReview,
  onIntervene,
}: {
  students: AttentionStudent[];
  user: User;
  disabled: boolean;
  onReview: (student: AttentionStudent) => void;
  onIntervene: (student: AttentionStudent) => void;
}) {
  const [filter, setFilter] = useState<(typeof filters)[number]>("All");
  const filtered = students.filter(
    (student) =>
      filter === "All" ||
      (filter === "High Risk"
        ? student.risk_level === "HIGH"
        : student.review_state ===
          (filter === "Confirmed" ? "CONFIRMED" : "PENDING_REVIEW")),
  );
  return (
    <section
      className="dash-card dash-attention"
      aria-labelledby="attention-title"
    >
      <div className="dash-section-heading">
        <div>
          <h2 id="attention-title">
            Students Requiring Attention{" "}
            <span className="dash-count">{students.length}</span>
          </h2>
          <p>Priority-ranked cases selected by the early warning system</p>
        </div>
        <Link className="dash-text-link" href="/students">
          View Full Registry <Icon name="arrow" />
        </Link>
      </div>
      <div className="dash-table-toolbar">
        <div
          className="dash-filter-tabs"
          role="group"
          aria-label="Filter attention students"
        >
          {filters.map((item) => (
            <button
              key={item}
              aria-pressed={filter === item}
              onClick={() => setFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <span>
          {filtered.length} of {students.length} attention cases
        </span>
      </div>
      {filtered.length === 0 ? (
        <div className="dash-empty">
          <span className="dash-empty-icon">
            <Icon name="check" />
          </span>
          <strong>
            {students.length === 0
              ? "No students requiring attention"
              : "No cases match this filter"}
          </strong>
          <p>
            {students.length === 0
              ? "Priority cases will appear here when the system identifies active warnings."
              : "Choose another filter to see the available attention cases."}
          </p>
        </div>
      ) : (
        <div
          className="dash-table-scroll"
          tabIndex={0}
          role="region"
          aria-label="Attention students table, scroll horizontally for more columns"
        >
          <table>
            <thead>
              <tr>
                <th>Student / ID</th>
                <th>Risk probability</th>
                <th>Risk level</th>
                <th>Explanation factors</th>
                <th>Warning priority</th>
                <th>Review state</th>
                <th>Assigned advisor</th>
                <th>Predicted</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((student) => (
                <tr key={student.warning_id}>
                  <td>
                    <Link
                      className="dash-student-name"
                      href={`/students/${encodeURIComponent(student.student_id)}`}
                    >
                      {student.name}
                    </Link>
                    <small className="dash-student-number">
                      {student.student_number}
                    </small>
                  </td>
                  <td>
                    <strong className="dash-probability">
                      {percent(student.probability)}
                    </strong>
                    <div className="dash-probability-track" aria-hidden="true">
                      <span
                        className={
                          student.risk_level === "HIGH"
                            ? "dash-risk-high"
                            : "dash-risk-medium"
                        }
                        style={{
                          width: `${Math.max(0, Math.min(1, student.probability)) * 100}%`,
                        }}
                      />
                    </div>
                  </td>
                  <td>
                    <span
                      className={`dash-badge ${student.risk_level === "HIGH" ? "is-danger" : student.risk_level === "LOW" ? "is-low" : "is-medium"}`}
                    >
                      {readable(student.risk_level)} Risk
                    </span>
                  </td>
                  <td>
                    <div className="dash-factors">
                      {student.top_explanation_factors.length ? (
                        student.top_explanation_factors.map((factor, index) => (
                          <span key={index}>{factorLabel(factor)}</span>
                        ))
                      ) : (
                        <span>No explanation available</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span
                      className={`dash-priority ${student.priority === "P1_URGENT" ? "is-urgent" : ""}`}
                    >
                      {readable(student.priority)}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`dash-badge ${student.review_state === "CONFIRMED" ? "is-confirmed" : ""}`}
                    >
                      {readable(student.review_state)}
                    </span>
                  </td>
                  <td>
                    {student.assigned_advisor?.full_name ?? (
                      <span className="dash-subtle">Unassigned</span>
                    )}
                  </td>
                  <td className="dash-predicted">
                    <time dateTime={student.predicted_at}>
                      {timestamp(student.predicted_at)}
                    </time>
                  </td>
                  <td>
                    <div className="dash-row-actions">
                      {canReview(user, student) && (
                        <button
                          className="dash-button dash-button-small"
                          disabled={disabled}
                          onClick={() => onReview(student)}
                        >
                          Review Case
                        </button>
                      )}
                      {canIntervene(user, student) && (
                        <button
                          className="dash-button dash-button-small"
                          disabled={disabled}
                          onClick={() => onIntervene(student)}
                        >
                          Quick Intervention
                        </button>
                      )}
                      <Link
                        href={`/students/${encodeURIComponent(student.student_id)}`}
                      >
                        View student →
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="dash-table-footer">
        This overview shows the backend priority list. The full student registry
        contains all student records.
      </div>
    </section>
  );
}
