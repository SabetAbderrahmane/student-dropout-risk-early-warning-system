"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError, fetchStudentProfile } from "@/lib/api";
import { percent, readable, timestamp } from "@/lib/dashboard";
import type { RegistryRow, StudentProfile } from "@/types/registry";
import { Icon } from "@/components/dashboard/icon";

export function StudentProfileDrawer({
  token,
  student,
  onClose,
  onUnauthorized,
}: {
  token: string;
  student: RegistryRow;
  onClose: () => void;
  onUnauthorized: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [tab, setTab] = useState<"overview" | "support" | "history">(
    "overview",
  );
  const unauthorizedRef = useRef(onUnauthorized);
  unauthorizedRef.current = onUnauthorized;
  useEffect(() => {
    const dialog = dialogRef.current;
    const previous = document.activeElement;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setProfile(null);
    fetchStudentProfile(token, student.student_id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setProfile(data);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 401)
          unauthorizedRef.current();
        else
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load profile.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, student.student_id, retry]);
  return (
    <dialog
      ref={dialogRef}
      className="registry-drawer"
      aria-labelledby="student-profile-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="registry-drawer-heading">
        <div>
          <p className="dash-eyebrow">Student profile</p>
          <h2 id="student-profile-title">{student.name}</h2>
          <p className="registry-muted registry-mono">
            {student.student_number}
          </p>
        </div>
        <button
          className="dash-icon-button"
          aria-label="Close student profile"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </header>
      <div
        className="registry-drawer-tabs"
        role="group"
        aria-label="Profile sections"
      >
        {(["overview", "support", "history"] as const).map((value) => (
          <button
            key={value}
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
          >
            {readable(value)}
          </button>
        ))}
      </div>
      <div className="registry-drawer-body" aria-busy={loading}>
        {loading && <p role="status">Loading student profile…</p>}
        {error && (
          <div role="alert">
            <p>{error}</p>
            <button
              className="dash-button"
              onClick={() => setRetry((value) => value + 1)}
            >
              Retry
            </button>
          </div>
        )}
        {profile && tab === "overview" && (
          <>
            <section>
              <h3>Academic record</h3>
              <dl className="registry-profile-grid">
                <dt>Course</dt>
                <dd>{profile.admission?.course_label ?? "Not recorded"}</dd>
                <dt>Admission method</dt>
                <dd>{profile.admission?.admission_method ?? "Not recorded"}</dd>
                <dt>Admission grade</dt>
                <dd>{profile.admission?.admission_grade ?? "Not recorded"}</dd>
                <dt>Semester 1 average</dt>
                <dd>{profile.semester_one?.average_grade ?? "Not recorded"}</dd>
                <dt>Units approved / enrolled</dt>
                <dd>
                  {profile.semester_one
                    ? `${profile.semester_one.approved_units} / ${profile.semester_one.enrolled_units}`
                    : "Not recorded"}
                </dd>
                <dt>Approval rate</dt>
                <dd>
                  {profile.semester_one?.approval_rate != null
                    ? percent(profile.semester_one.approval_rate)
                    : "Not available"}
                </dd>
              </dl>
            </section>
            <section>
              <h3>Prediction readiness</h3>
              <p>
                <strong>{readable(profile.prediction_readiness.status)}</strong>{" "}
                · {profile.prediction_readiness.available_feature_count} /{" "}
                {profile.prediction_readiness.required_feature_count} required
                features available
              </p>
              {profile.prediction_readiness.missing_features.length > 0 && (
                <>
                  <p className="registry-muted">Missing features</p>
                  <ul>
                    {profile.prediction_readiness.missing_features.map(
                      (feature) => (
                        <li key={feature}>{readable(feature)}</li>
                      ),
                    )}
                  </ul>
                </>
              )}
            </section>
            <section>
              <h3>Latest risk assessment</h3>
              {profile.latest_prediction ? (
                <>
                  <div className="registry-profile-risk">
                    <strong>
                      {percent(profile.latest_prediction.probability)}
                    </strong>
                    <span>
                      {readable(profile.latest_prediction.risk_level)} risk
                    </span>
                  </div>
                  <p className="registry-muted">
                    {timestamp(profile.latest_prediction.predicted_at)} · Model{" "}
                    {profile.latest_prediction.model_version}
                  </p>
                </>
              ) : (
                <p className="registry-muted">No prediction recorded.</p>
              )}
            </section>
          </>
        )}
        {profile && tab === "support" && (
          <>
            <section>
              <h3>Active warning</h3>
              {profile.active_warning ? (
                <>
                  <p>
                    <strong>
                      {readable(profile.active_warning.review_state)}
                    </strong>{" "}
                    · {readable(profile.active_warning.priority)}
                  </p>
                  <p>
                    Case owner:{" "}
                    {profile.active_warning.assigned_advisor?.full_name ??
                      "Unassigned"}
                  </p>
                  {profile.active_warning.reviews.map((review) => (
                    <article className="registry-history-item" key={review.id}>
                      <strong>{readable(review.decision)}</strong>
                      <p>{review.note}</p>
                      <small>
                        {review.reviewer?.full_name ?? "Reviewer unavailable"} ·{" "}
                        {timestamp(review.reviewed_at)}
                      </small>
                    </article>
                  ))}
                </>
              ) : (
                <p className="registry-muted">No active warning.</p>
              )}
            </section>
            <section>
              <h3>Interventions</h3>
              {profile.interventions.length === 0 ? (
                <p className="registry-muted">No interventions recorded.</p>
              ) : (
                profile.interventions.map((item) => (
                  <article className="registry-history-item" key={item.id}>
                    <strong>{item.title}</strong>
                    <p>
                      {readable(item.status)} · {readable(item.type)}
                    </p>
                    <small>
                      {item.assigned_advisor?.full_name ?? "Unassigned"} · Start{" "}
                      {item.start_date}
                      {item.target_date ? ` · Target ${item.target_date}` : ""}
                    </small>
                    {item.completion_outcome && (
                      <p>{item.completion_outcome}</p>
                    )}
                  </article>
                ))
              )}
            </section>
            <section>
              <h3>Follow-ups</h3>
              {profile.follow_ups.length === 0 ? (
                <p className="registry-muted">No follow-ups recorded.</p>
              ) : (
                profile.follow_ups.map((item) => (
                  <article className="registry-history-item" key={item.id}>
                    <strong>{item.purpose}</strong>
                    <p>
                      {readable(item.effective_status)} ·{" "}
                      {readable(item.method)}
                    </p>
                    <small>{timestamp(item.scheduled_for)}</small>
                    {item.outcome && <p>{item.outcome}</p>}
                  </article>
                ))
              )}
            </section>
          </>
        )}
        {profile && tab === "history" && (
          <>
            <section>
              <h3>Activity timeline</h3>
              {profile.timeline.length === 0 ? (
                <p className="registry-muted">No activity recorded.</p>
              ) : (
                <ol className="registry-timeline">
                  {profile.timeline.map((item, index) => (
                    <li key={`${item.type}-${item.entity_id}-${index}`}>
                      <small>{timestamp(item.occurred_at)}</small>
                      <strong>{item.title}</strong>
                      <p>{item.summary}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
            <section>
              <h3>Prediction history</h3>
              {profile.prediction_history.length === 0 ? (
                <p className="registry-muted">No predictions recorded.</p>
              ) : (
                profile.prediction_history.map((item) => (
                  <article className="registry-history-item" key={item.id}>
                    <strong>
                      {percent(item.probability)} · {readable(item.risk_level)}{" "}
                      risk
                    </strong>
                    <small>
                      {timestamp(item.predicted_at)} · {item.model_version}
                    </small>
                  </article>
                ))
              )}
            </section>
            <section>
              <h3>Warning history</h3>
              {profile.warning_history.length === 0 ? (
                <p className="registry-muted">No warnings recorded.</p>
              ) : (
                profile.warning_history.map((item) => (
                  <article className="registry-history-item" key={item.id}>
                    <strong>
                      {readable(item.review_state)} · {readable(item.priority)}
                    </strong>
                    <small>{timestamp(item.created_at)}</small>
                  </article>
                ))
              )}
            </section>
          </>
        )}
      </div>
      <footer className="registry-drawer-footer">
        <Link
          className="dash-button dash-button-primary"
          href={`/students/${encodeURIComponent(student.student_id)}`}
        >
          Open full student record <Icon name="arrow" />
        </Link>
      </footer>
    </dialog>
  );
}
