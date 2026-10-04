import { readable, percent, timestamp } from "@/lib/dashboard";
import type {
  StudentProfile,
  ProfilePrediction,
  ProfileWarning,
} from "@/types/registry";
import type { ReactNode } from "react";
export function DossierCard({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="dossier-card">
      <header>
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}
export function RecordValues({ record }: { record: Record<string, unknown> }) {
  return (
    <dl className="dossier-values">
      {Object.entries(record).map(([key, value]) => (
        <div key={key}>
          <dt>{readable(key)}</dt>
          <dd>
            {value === null || value === undefined
              ? "Not recorded"
              : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function DossierBadge({ value }: { value: string }) {
  return (
    <span className={`dossier-badge dossier-status-${value.toLowerCase()}`}>
      {readable(value)}
    </span>
  );
}
export function ReadinessCard({
  profile,
  action,
}: {
  profile: StudentProfile;
  action?: ReactNode;
}) {
  const readiness = profile.prediction_readiness;
  return (
    <DossierCard title="Prediction readiness" action={action}>
      <div className="dossier-readiness">
        <DossierBadge value={readiness.status} />
        <strong>
          {readiness.available_feature_count} /{" "}
          {readiness.required_feature_count}
        </strong>
        <span>Required features available</span>
      </div>
      {readiness.missing_features.length > 0 ? (
        <details>
          <summary>
            Missing features ({readiness.missing_features.length})
          </summary>
          <ul className="dossier-feature-list">
            {readiness.missing_features.map((field) => (
              <li key={field}>{readable(field)}</li>
            ))}
          </ul>
        </details>
      ) : (
        <p className="dossier-muted">
          All required prediction features are available.
        </p>
      )}
    </DossierCard>
  );
}
export function PredictionRecord({
  prediction,
}: {
  prediction: ProfilePrediction;
}) {
  return (
    <article className="dossier-prediction">
      <div className="dossier-row">
        <strong>{percent(prediction.probability)} dropout probability</strong>
        <DossierBadge value={prediction.risk_level} />
      </div>
      <p className="dossier-muted">
        {timestamp(prediction.predicted_at)} · Model {prediction.model_version}
      </p>
      <p className="dossier-id">Prediction {prediction.id}</p>
      <details>
        <summary>
          Recorded explanation factors ({prediction.explanation.length})
        </summary>
        {prediction.explanation.length === 0 ? (
          <p>No explanation factors recorded.</p>
        ) : (
          <div className="dossier-factors">
            {prediction.explanation.map((factor, index) => (
              <div key={index}>
                <RecordValues record={factor} />
              </div>
            ))}
          </div>
        )}
      </details>
    </article>
  );
}
export function WarningRecord({
  warning,
  action,
}: {
  warning: ProfileWarning;
  action?: ReactNode;
}) {
  return (
    <article className="dossier-warning">
      <div className="dossier-row">
        <DossierBadge value={warning.review_state} />
        <DossierBadge value={warning.priority} />
        {action}
      </div>
      <p>
        <strong>{readable(warning.risk_level)} risk</strong> · Assigned advisor:{" "}
        {warning.assigned_advisor?.full_name ?? "Unassigned"}
      </p>
      <p className="dossier-muted">Created {timestamp(warning.created_at)}</p>
      <p className="dossier-id">
        Warning {warning.id} · Prediction {warning.prediction_id}
      </p>
      {warning.reviews.length > 0 ? (
        <ol className="dossier-timeline">
          {warning.reviews.map((review) => (
            <li key={review.id}>
              <strong>{readable(review.decision)}</strong>
              <small>
                {review.reviewer?.full_name ?? "Reviewer unavailable"} ·{" "}
                {timestamp(review.reviewed_at)}
              </small>
              <p>{review.note}</p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="dossier-muted">No advisor review recorded.</p>
      )}
    </article>
  );
}
export function DossierTimeline({ profile }: { profile: StudentProfile }) {
  return (
    <DossierCard title="Student history">
      {profile.timeline.length === 0 ? (
        <p className="dossier-empty">
          No activity has been recorded for this student.
        </p>
      ) : (
        <ol className="dossier-timeline">
          {profile.timeline.map((event, index) => (
            <li key={`${event.type}-${event.entity_id}-${index}`}>
              <div className="dossier-row">
                <strong>{event.title}</strong>
                <time dateTime={event.occurred_at}>
                  {timestamp(event.occurred_at)}
                </time>
              </div>
              <p>{event.summary}</p>
              <small>{readable(event.type)}</small>
            </li>
          ))}
        </ol>
      )}
    </DossierCard>
  );
}
