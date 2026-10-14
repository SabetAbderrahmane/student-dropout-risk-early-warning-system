import type { AssessmentFields, PredictionFreshnessFields, PredictionFreshness } from "@/types/assessment";
import { readable } from "@/lib/dashboard";
import { stageLabel } from "@/types/outcome";

const labels: Record<PredictionFreshness, string> = {
  NOT_SELECTED: "Inputs match · not selected",
  CURRENT: "Current", INPUTS_CHANGED: "Academic inputs changed",
  INPUTS_INCOMPLETE: "Required inputs incomplete", MODEL_SUPERSEDED: "Model superseded",
  MODEL_UNAVAILABLE: "Model unavailable", STAGE_REASSESSMENT_REQUIRED: "Semester reassessment required",
  NO_PREDICTION: "No prediction",
};
export function FreshnessBadge({ prediction }: { prediction: PredictionFreshnessFields }) {
  return <span className="assessment-status">{prediction.is_operational_current ? "Current assessment" : `Historical assessment · ${prediction.prediction_freshness === "CURRENT" ? "Inputs match" : labels[prediction.prediction_freshness]}`}</span>;
}
export function AssessmentStatus({ assessment, compact = false }: { assessment: AssessmentFields; compact?: boolean }) {
  if (compact) return <span className="assessment-status">{labels[assessment.assessment_status]}</span>;
  return <div className="assessment-notice">
    <span className="assessment-status">{labels[assessment.assessment_status]}</span>
    {assessment.reassessment_required && <p>Reassessment required · {stageLabel(assessment.recommended_stage)}{assessment.recommended_target_type === "BINARY_DROPOUT" ? " · Legacy binary fallback" : ""}</p>}
    {assessment.assessment_status !== "CURRENT" && <p>No current dropout probability is available. Historical assessments remain in prediction history.</p>}
    {!assessment.recommended_model_available && <p>The recommended model is inactive or unavailable. Review model availability in Prediction Analytics.</p>}
  </div>;
}
export function InputChanges({ prediction }: { prediction: PredictionFreshnessFields }) {
  const entries = [...prediction.changed_features.map(name => `${readable(name)}: changed`), ...prediction.missing_features.map(name => `${readable(name)}: not recorded`)];
  return entries.length ? <details><summary>Relevant input changes ({entries.length})</summary><ul>{entries.map(value => <li key={value}>{value}</li>)}</ul></details> : null;
}
