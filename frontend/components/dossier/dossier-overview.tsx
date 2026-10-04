import type { ReactNode } from "react";
import type { StudentProfile, ProfileWarning } from "@/types/registry";
import { percent, timestamp } from "@/lib/dashboard";
import {
  DossierCard,
  PredictionRecord,
  ReadinessCard,
  RecordValues,
  WarningRecord,
} from "./dossier-records";

export function DossierOverview({
  profile: p,
  predictionAction,
  warningActions,
  onAcademic,
  onHistory,
  onInterventions,
  onFollowUps,
}: {
  profile: StudentProfile;
  predictionAction: ReactNode;
  warningActions: (warning: ProfileWarning) => ReactNode;
  onAcademic: () => void;
  onHistory: () => void;
  onInterventions: () => void;
  onFollowUps: () => void;
}) {
  return (
    <div className="dossier-overview">
      <DossierCard title="Latest risk assessment" action={predictionAction}>
        {p.latest_prediction ? (
          <PredictionRecord prediction={p.latest_prediction} />
        ) : (
          <p className="dossier-empty">
            No prediction has been recorded for this student.
          </p>
        )}
        <p className="dossier-advisory">
          Predictions support advisor review. They do not replace an individual
          assessment of the student’s situation.
        </p>
      </DossierCard>
      <ReadinessCard profile={p} />
      <DossierCard
        title="Academic snapshot"
        action={
          <button className="dash-button" onClick={onAcademic}>
            View Academic Record
          </button>
        }
      >
        <RecordValues
          record={{
            admission_grade: p.admission?.admission_grade,
            previous_qualification: p.admission?.previous_qualification,
            first_semester_average: p.semester_one?.average_grade,
            approved_units: p.semester_one?.approved_units,
            enrolled_units: p.semester_one?.enrolled_units,
            approval_rate:
              p.semester_one?.approval_rate == null
                ? null
                : percent(p.semester_one.approval_rate),
          }}
        />
      </DossierCard>
      <DossierCard title="Active warning">
        {p.active_warning ? (
          <WarningRecord
            warning={p.active_warning}
            action={warningActions(p.active_warning)}
          />
        ) : (
          <p className="dossier-empty">No active warning.</p>
        )}
      </DossierCard>
      <DossierCard
        title="Recent student history"
        action={
          <button className="dash-button" onClick={onHistory}>
            View Full History
          </button>
        }
      >
        {p.timeline.length === 0 ? (
          <p className="dossier-empty">No activity recorded.</p>
        ) : (
          <ol className="dossier-timeline">
            {p.timeline.slice(0, 5).map((event, index) => (
              <li key={`${event.entity_id}-${index}`}>
                <strong>{event.title}</strong>
                <small>{timestamp(event.occurred_at)}</small>
                <p>{event.summary}</p>
              </li>
            ))}
          </ol>
        )}
      </DossierCard>
      <DossierCard title="Support record">
        <div className="dossier-support-counts">
          <button onClick={onInterventions}>
            <strong>{p.interventions.length}</strong>
            <span>Interventions</span>
          </button>
          <button onClick={onFollowUps}>
            <strong>{p.follow_ups.length}</strong>
            <span>Follow-ups</span>
          </button>
        </div>
      </DossierCard>
    </div>
  );
}
