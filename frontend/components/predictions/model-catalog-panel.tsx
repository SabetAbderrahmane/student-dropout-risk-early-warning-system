"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import { useAuthSession } from "@/components/auth/auth-session";
import {
  activateStageModel,
  fetchModelCatalog,
  fetchStudentRegistry,
  validateStageModel,
} from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { percent, readable, timestamp } from "@/lib/dashboard";
import { predictionError } from "@/lib/predictions";
import {
  stageLabel,
  type ModelCatalog,
  type ModelCatalogEntry,
  type MulticlassMetrics,
  type StageSelection,
} from "@/types/outcome";
import type { RegistryRow } from "@/types/registry";

export function ModelCatalogPanel({
  revision,
  onChanged,
  onBatch,
  batchBusy,
}: {
  revision: number;
  onChanged: () => void;
  onBatch?: (stage: StageSelection) => void;
  batchBusy: boolean;
}) {
  const { user } = useAuthSession();
  const [data, setData] = useState<ModelCatalog | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [action, setAction] = useState<{
    kind: "validate" | "activate";
    model: ModelCatalogEntry;
  } | null>(null);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void fetchModelCatalog(token, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(predictionError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision, retry]);
  const multiclass =
    data?.items.filter(
      (item) => item.model_target_type === "MULTICLASS_OUTCOME",
    ) ?? [];
  return (
    <section className="outcome-catalog" aria-label="Stage models">
      <div className="prediction-matrix-intro">
        <div>
          <h2>Academic outcome models</h2>
          <p className="prediction-muted">
            Separate enrollment and first-semester assessments. UCI benchmark
            performance supports model review; it does not establish
            institutional validity.
          </p>
        </div>
      </div>
      {loading && <p role="status">Loading registered stage models…</p>}
      {error && (
        <div className="dash-inline-error" role="alert">
          <p>{error}</p>
          <button
            className="dash-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry stage models
          </button>
        </div>
      )}
      {notice && <p role="status">{notice}</p>}
      {!loading && !error && data?.items.length === 0 && (
        <p>No models are registered.</p>
      )}
      {data && !error && (
        <div className="prediction-model-grid">
          {multiclass.map((model) => (
            <StageModelCard
              key={model.id}
              model={model}
              admin={user?.role === "SYSTEM_ADMIN"}
              academic={user?.role === "ACADEMIC_ADMIN"}
              batchBusy={batchBusy}
              onAction={(kind) => {
                setNotice("");
                setAction({ kind, model });
              }}
              onBatch={onBatch}
            />
          ))}
        </div>
      )}
      {multiclass.length > 0 && !error && (
        <div className="prediction-card outcome-comparison">
          <h3>Candidate comparison</h3>
          <p className="prediction-muted">
            Winners were selected from development cross-validation. Final-test
            metrics below were calculated after selection and calibration were
            frozen.
          </p>
          <div
            className="outcome-table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Six candidate comparison"
          >
            <table className="outcome-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Algorithm</th>
                  <th>CV selection score</th>
                  <th>Accuracy</th>
                  <th>Macro F1</th>
                  <th>Dropout PR-AUC</th>
                  <th>Dropout recall</th>
                  <th>Dropout precision</th>
                  <th>Log loss</th>
                </tr>
              </thead>
              <tbody>
                {multiclass.flatMap((model) =>
                  (model.evaluation.candidate_comparison ?? []).map(
                    (candidate) => (
                      <tr key={`${model.version}-${candidate.name}`}>
                        <td>{stageLabel(model.prediction_stage)}</td>
                        <th scope="row">
                          {candidate.name}
                          {candidate.name === model.name ? " · Selected" : ""}
                        </th>
                        <td>{candidate.selection_score.toFixed(4)}</td>
                        <td>{percent(candidate.final_test.accuracy)}</td>
                        <td>{percent(candidate.final_test.macro_f1)}</td>
                        <td>{percent(candidate.final_test.dropout_pr_auc)}</td>
                        <td>{percent(candidate.final_test.dropout_recall)}</td>
                        <td>
                          {percent(candidate.final_test.dropout_precision)}
                        </td>
                        <td>{candidate.final_test.log_loss.toFixed(4)}</td>
                      </tr>
                    ),
                  ),
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {action && (
        <ModelActionDialog
          key={action.model.version + action.kind}
          action={action}
          onClose={() => setAction(null)}
          onDone={() => {
            setNotice(
              action.kind === "validate"
                ? "Model integration validation passed. No academic prediction or warning was retained."
                : "Stage model activated. Existing assessments remain unchanged.",
            );
            setAction(null);
            setRetry((value) => value + 1);
            onChanged();
          }}
        />
      )}
    </section>
  );
}

function StageModelCard({
  model,
  admin,
  academic,
  batchBusy,
  onAction,
  onBatch,
}: {
  model: ModelCatalogEntry;
  admin: boolean;
  academic: boolean;
  batchBusy: boolean;
  onAction: (kind: "validate" | "activate") => void;
  onBatch?: (stage: StageSelection) => void;
}) {
  const metrics = model.evaluation.final_test as MulticlassMetrics;
  const statRows: Array<[string, number | null, boolean?]> = [
    ["Accuracy", metrics.accuracy],
    ["Macro precision", metrics.macro_precision],
    ["Macro recall", metrics.macro_recall],
    ["Macro F1", metrics.macro_f1],
    ["Weighted F1", metrics.weighted_f1],
    ["Dropout PR-AUC", metrics.dropout_pr_auc],
    ["Dropout precision", metrics.dropout_precision],
    ["Dropout recall", metrics.dropout_recall],
    ["OVR ROC-AUC", metrics.multiclass_roc_auc_ovr],
    ["Log loss", metrics.log_loss, true],
    ["Dropout Brier", metrics.calibration.dropout_brier_score, true],
    ["Multiclass Brier", metrics.calibration.multiclass_brier_score, true],
    ["Dropout calibration error", metrics.calibration.dropout_ece_10_bins],
  ];
  return (
    <article className="prediction-card">
      <h3>{stageLabel(model.prediction_stage)}</h3>
      <p>
        <strong>{model.name}</strong> · {model.feature_count} inputs
      </p>
      <p className="prediction-muted">
        {model.version} ·{" "}
        {model.artifact_available
          ? model.is_active
            ? "Active"
            : "Inactive"
          : `Unavailable (${model.availability_error})`}
      </p>
      <p>
        Dropout risk: LOW below {percent(model.low_threshold)} · HIGH from{" "}
        {percent(model.high_threshold)}
      </p>
      <dl className="outcome-metrics">
        {[
          ["Macro F1", metrics.macro_f1],
          ["Dropout PR-AUC", metrics.dropout_pr_auc],
        ].map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{percent(Number(value))}</dd>
          </div>
        ))}
      </dl>
      <p className="prediction-muted">
        Final test: {metrics.sample_size} students. Validation:{" "}
        {model.validated_at
          ? timestamp(model.validated_at)
          : "Required before activation"}
        .
      </p>
      <details>
        <summary>Performance and model details</summary>
        <dl className="outcome-metrics">
          {statRows.map(([label, value, decimal]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>
                {value === null
                  ? "Undefined"
                  : decimal
                    ? value.toFixed(4)
                    : percent(value)}
              </dd>
            </div>
          ))}
        </dl>
        <div
          className="outcome-table-scroll"
          tabIndex={0}
          role="region"
          aria-label={`${stageLabel(model.prediction_stage)} per-class performance`}
        >
          <table className="outcome-table">
            <caption>Final-test per-class metrics</caption>
            <thead>
              <tr>
                <th>Outcome</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1</th>
                <th>Students</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.per_class).map(([name, value]) => (
                <tr key={name}>
                  <th scope="row">{readable(name)}</th>
                  <td>{percent(value.precision)}</td>
                  <td>{percent(value.recall)}</td>
                  <td>{percent(value.f1)}</td>
                  <td>{value.support}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div
          className="outcome-table-scroll"
          tabIndex={0}
          role="region"
          aria-label={`${stageLabel(model.prediction_stage)} confusion matrix`}
        >
          <table className="outcome-table">
            <caption>Confusion matrix: actual rows, predicted columns</caption>
            <thead>
              <tr>
                <th>Actual / predicted</th>
                {metrics.confusion_matrix.labels.map((name) => (
                  <th key={name}>{readable(name)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.confusion_matrix.rows_actual_columns_predicted.map(
                (row, index) => (
                  <tr key={index}>
                    <th scope="row">
                      {readable(metrics.confusion_matrix.labels[index])}
                    </th>
                    {row.map((value, column) => (
                      <td key={column}>{value}</td>
                    ))}
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
        <p>
          Selected on development data: {model.selection.method}.{" "}
          {model.selection.reason}.
        </p>
        <p>
          Probability calibration: {model.probability_calibration?.method};{" "}
          {model.probability_calibration?.sample_size} students.
        </p>
        <p>{model.explanation_method}</p>
        <p className="outcome-checksum">
          SHA-256: {model.artifact_sha256 ?? "Unavailable"}
        </p>
        <p className="prediction-muted">
          Schema {model.feature_schema_version} · Trained{" "}
          {timestamp(model.trained_at)}. Thresholds use a separate development
          sample, with 90% LOW-boundary and 70% HIGH-boundary dropout recall
          targets.
        </p>
        <details>
          <summary>Calibration audit records</summary>
          <pre className="outcome-audit">
            {JSON.stringify(
              {
                probability: model.probability_calibration,
                risk: model.threshold_calibration,
              },
              null,
              2,
            )}
          </pre>
        </details>
      </details>
      <div className="dash-modal-actions">
        {admin && (
          <>
            <button
              className="dash-button"
              disabled={!model.artifact_available}
              onClick={() => onAction("validate")}
            >
              Validate {stageLabel(model.prediction_stage)}
            </button>
            <button
              className="dash-button dash-button-primary"
              disabled={
                !model.artifact_available ||
                !model.validation_id ||
                model.is_active
              }
              onClick={() => onAction("activate")}
            >
              Activate {stageLabel(model.prediction_stage)}
            </button>
          </>
        )}
        {academic && onBatch && (
          <button
            className="dash-button"
            disabled={
              batchBusy || !model.is_active || !model.artifact_available
            }
            onClick={() => onBatch(model.prediction_stage)}
          >
            Run {stageLabel(model.prediction_stage)} Batch
          </button>
        )}
      </div>
    </article>
  );
}

function ModelActionDialog({
  action,
  onClose,
  onDone,
}: {
  action: { kind: "validate" | "activate"; model: ModelCatalogEntry };
  onClose: () => void;
  onDone: () => void;
}) {
  const [search, setSearch] = useState("");
  const [students, setStudents] = useState<RegistryRow[]>([]);
  const [student, setStudent] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  useEffect(() => {
    if (action.kind !== "validate") return;
    const token = getAccessToken();
    if (!token) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      void fetchStudentRegistry(
        token,
        {
          page: 1,
          page_size: 25,
          search: search.trim() || undefined,
          sort: "name",
          order: "asc",
        },
        controller.signal,
      )
        .then((result) => {
          if (!controller.signal.aborted) setStudents(result.items);
        })
        .catch((caught) => {
          if (!controller.signal.aborted) setError(predictionError(caught));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [search, action.kind]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    const token = getAccessToken();
    if (!token) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      if (action.kind === "validate")
        await validateStageModel(token, action.model.version, student);
      else await activateStageModel(token, action.model.version);
      onDone();
    } catch (caught) {
      setError(predictionError(caught));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <ActionModal
      title={`${action.kind === "validate" ? "Validate" : "Activate"} ${stageLabel(action.model.prediction_stage)} Model`}
      eyebrow="Model administration"
      busy={busy}
      onClose={onClose}
    >
      <p>
        {action.model.name} · {action.model.version}
      </p>
      <form onSubmit={submit}>
        <fieldset disabled={busy} className="outcome-form">
          {action.kind === "validate" ? (
            <>
              <p>
                Choose a student with complete inputs for this stage.
                Verification runs actual inference and checks database
                persistence, then removes the probe. It records model validation
                without adding academic decisions.
              </p>
              <label>
                Search students
                <input
                  value={search}
                  maxLength={200}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setStudent("");
                  }}
                />
              </label>
              {loading && <p role="status">Loading students…</p>}
              <label>
                Validation student
                <select
                  required
                  value={student}
                  onChange={(event) => setStudent(event.target.value)}
                >
                  <option value="">Choose a student</option>
                  {students.map((item) => (
                    <option key={item.student_id} value={item.student_id}>
                      {item.name} · {item.student_number}
                    </option>
                  ))}
                </select>
              </label>
              {!loading && students.length === 0 && (
                <p>
                  No matching students. Add student data through the Students
                  workspace first.
                </p>
              )}
            </>
          ) : (
            <p>
              Use this verified model for future{" "}
              {stageLabel(action.model.prediction_stage).toLowerCase()}{" "}
              assessments. Existing predictions, warnings, and support decisions
              are retained.
            </p>
          )}
          <label className="outcome-confirm">
            <input
              type="checkbox"
              required
              checked={accepted}
              onChange={(event) => setAccepted(event.target.checked)}
            />
            I confirm this model operation.
          </label>
        </fieldset>
        {error && (
          <p className="dash-inline-error" role="alert">
            {error}
          </p>
        )}
        <div className="dash-modal-actions">
          <button
            type="button"
            className="dash-button"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="dash-button dash-button-primary"
            disabled={
              busy || !accepted || (action.kind === "validate" && !student)
            }
          >
            {busy
              ? "Working…"
              : action.kind === "validate"
                ? "Run validation"
                : "Activate model"}
          </button>
        </div>
      </form>
    </ActionModal>
  );
}
