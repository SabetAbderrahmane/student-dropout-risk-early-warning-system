import { percent, readable } from "@/lib/dashboard";
import {
  stageLabel,
  type AcademicOutcome,
  type ClassProbabilities,
  type ModelTargetType,
  type PredictionStage,
} from "@/types/outcome";

export function OutcomeSummary({
  prediction,
}: {
  prediction: {
    prediction_stage: PredictionStage;
    model_target_type: ModelTargetType;
    predicted_outcome: AcademicOutcome | null;
    class_probabilities: ClassProbabilities | null;
  };
}) {
  const multiclass = prediction.model_target_type === "MULTICLASS_OUTCOME";
  return (
    <div className="outcome-summary">
      <p>
        <strong>
          {stageLabel(multiclass ? prediction.prediction_stage : "LEGACY")}
        </strong>
        {multiclass && prediction.predicted_outcome && (
          <>
            {" "}
            · Most likely outcome:{" "}
            <strong>{readable(prediction.predicted_outcome)}</strong>
          </>
        )}
      </p>
      {multiclass && prediction.class_probabilities ? (
        <dl
          className="dossier-values outcome-probabilities"
          aria-label="Academic outcome probabilities"
        >
          {(["DROPOUT", "ENROLLED", "GRADUATE"] as const).map((outcome) => (
            <div key={outcome}>
              <dt>{readable(outcome)}</dt>
              <dd>{percent(prediction.class_probabilities![outcome])}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="prediction-muted">
          Binary assessment; separate Enrolled and Graduate probabilities are
          unavailable.
        </p>
      )}
    </div>
  );
}
