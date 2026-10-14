"use client";
import Link from "next/link";
import { useState } from "react";
import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { ActionModal } from "@/components/dashboard/action-modal";
import { QuickInterventionModal } from "@/components/dashboard/quick-intervention-modal";
import { WarningReviewForm } from "@/components/warnings/warning-review-form";
import {
  assignStudentWarning,
  createIntervention,
  predictStudent,
  reviewWarning,
  reconsiderWarning,
} from "@/lib/api";
import { percent, readable, timestamp } from "@/lib/dashboard";
import type { ProfileWarning } from "@/types/registry";
import { useDossier } from "./use-dossier";
import { AcademicEditor, type AcademicSection } from "./academic-editor";
import {
  DossierBadge,
  DossierCard,
  DossierTimeline,
  PredictionRecord,
  ReadinessCard,
  RecordValues,
  WarningRecord,
} from "./dossier-records";
import { CaseDetail } from "./case-detail";
import { FollowUpDetail } from "./follow-up-detail";
import { DossierOverview } from "./dossier-overview";
import { DossierForm } from "./dossier-form";
import { stageLabel, type StageSelection } from "@/types/outcome";

const tabs = [
  "Overview",
  "Academic record",
  "Predictions",
  "Warnings",
  "Interventions",
  "Follow-ups",
  "History",
] as const;
type Tab = (typeof tabs)[number];
type Dialog =
  | { kind: "academic"; section: AcademicSection }
  | { kind: "review" | "assign" | "create"; warning: ProfileWarning }
  | { kind: "case" | "follow"; id: string }
  | { kind: "predict" };
export function StudentDossier({ studentId }: { studentId: string }) {
  const state = useDossier(studentId);
  const [menu, setMenu] = useState(false);
  const [tab, setTab] = useState<Tab>("Overview");
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [predictionStage, setPredictionStage] =
    useState<StageSelection>("ENROLLMENT");
  const p = state.profile;
  const u = state.user;
  const close = () => {
    if (!state.busy && !reviewBusy) setDialog(null);
  };
  const owned = (owner: string | undefined) =>
    state.canCase && (u?.role === "ACADEMIC_ADMIN" || u?.id === owner);
  const warningActions = (warning: ProfileWarning) => (
    <div className="dossier-actions">
      {state.canEdit && (
        <button
          className="dash-button"
          disabled={state.busy}
          onClick={() => setDialog({ kind: "assign", warning })}
        >
          Assign Advisor
        </button>
      )}
      {state.canCase &&
        u?.role === "ACADEMIC_ADVISOR" &&
        warning.assigned_advisor?.user_id === u.id && (
          <button
            className="dash-button"
            disabled={state.busy}
            onClick={() => setDialog({ kind: "review", warning })}
          >
            {warning.review_state === "PENDING_REVIEW"
              ? "Review Warning"
              : "Reconsider Warning"}
          </button>
        )}
      {owned(warning.assigned_advisor?.user_id) &&
        warning.assigned_advisor &&
        warning.review_state === "CONFIRMED" && (
          <button
            className="dash-button dash-button-primary"
            disabled={state.busy}
            onClick={() => setDialog({ kind: "create", warning })}
          >
            Create Intervention
          </button>
        )}
    </div>
  );
  const editButton = (section: AcademicSection) =>
    state.canEdit ? (
      <button
        className="dash-button"
        disabled={state.busy}
        onClick={() => setDialog({ kind: "academic", section })}
      >
        {p?.[section] ? "Edit" : "Add"}{" "}
        {section === "semester_one" ? "Semester Record" : readable(section)}
      </button>
    ) : undefined;
  const predictionButton = state.canEdit ? (
    <button
      className="dash-button dash-button-primary"
      disabled={
        state.busy ||
        !(
          p?.prediction_readiness.status === "READY" ||
          p?.stage_readiness.some((stage) => stage.status === "READY")
        )
      }
      onClick={() => {
        setPredictionStage(
          p?.recommended_target_type === "BINARY_DROPOUT"
            ? "LEGACY"
            : (p?.recommended_stage ?? "ENROLLMENT"),
        );
        setDialog({ kind: "predict" });
      }}
    >
      Run Prediction
    </button>
  ) : undefined;
  return (
    <div className="dash-root dossier-root">
      <a className="dash-skip-link" href="#dossier-main">
        Skip to student dossier
      </a>
      <AppSidebar open={menu} onClose={() => setMenu(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Student Dossier"
          user={u}
          menuOpen={menu}
          onMenu={() => setMenu((v) => !v)}
          onSignOut={state.signOut}
        />
        <main className="dash-main" id="dossier-main" aria-busy={state.loading}>
          <div className="dossier-breadcrumb">
            <Link href="/students">← Students Registry</Link>
            <span>/ Student Dossier</span>
            <button
              className="dash-button"
              disabled={state.loading || state.busy}
              onClick={state.refresh}
            >
              Refresh Dossier
            </button>
          </div>
          {state.error && (
            <div className="dash-inline-error" role="alert">
              {state.error}
            </div>
          )}
          {state.notice && (
            <div className="dash-notice" role="status">
              {state.notice}
            </div>
          )}
          {state.loading && (
            <section className="dossier-card dossier-loading" role="status">
              <h1>Student Dossier</h1>
              <p>Loading student, academic records and case history…</p>
            </section>
          )}
          {!state.loading && !p && (
            <section className="dossier-card">
              <h1>Student dossier unavailable</h1>
              <p>The student’s records could not be loaded.</p>
              <button className="dash-button" onClick={state.refresh}>
                Retry
              </button>
            </section>
          )}
          {p && (
            <>
              <section className="dossier-identity">
                <div className="dossier-avatar" aria-hidden="true">
                  {p.student.name
                    .split(" ")
                    .filter(Boolean)
                    .map((part) => part[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </div>
                <div className="dossier-identity-copy">
                  <p className="dash-eyebrow">
                    Student profile & case management
                  </p>
                  <div className="dossier-row">
                    <h1>{p.student.name}</h1>
                    <span className="dossier-number">
                      {p.student.student_number}
                    </span>
                    {p.operational_prediction && (
                      <DossierBadge
                        value={p.operational_prediction.risk_level}
                      />
                    )}
                  </div>
                  <p>
                    {p.admission?.course_label ?? "Course not recorded"} ·{" "}
                    {p.student.gender ?? "Gender not recorded"}
                  </p>
                  <p className="dossier-muted">
                    Warning advisor:{" "}
                    {p.open_warnings[0]
                      ? (p.open_warnings[0].assigned_advisor?.full_name ??
                        "Unassigned")
                      : "No active warning"}
                  </p>
                </div>
                <div className="dossier-identity-risk">
                  <small>
                    Current dropout probability
                    {p.operational_prediction
                      ? ` · ${stageLabel(p.operational_prediction.prediction_stage)}`
                      : ""}
                  </small>
                  <strong>
                    {p.operational_prediction
                      ? percent(p.operational_prediction.probability)
                      : "Unavailable"}
                  </strong>
                  <span>
                    {p.operational_prediction
                      ? timestamp(p.operational_prediction.predicted_at)
                      : p.latest_historical_prediction
                        ? "Reassessment required"
                        : "Not assessed"}
                  </span>
                </div>
              </section>
              <div
                className="dossier-workflow"
                aria-label="Student support workflow"
              >
                <span>Admission data</span>
                <span>Semester 1</span>
                <span>Prediction</span>
                <span>Advisor review</span>
                <span>Support & outcomes</span>
              </div>
              <nav className="dossier-tabs" aria-label="Dossier sections">
                {tabs.map((value) => (
                  <button
                    key={value}
                    aria-label={value}
                    aria-pressed={tab === value}
                    onClick={() => setTab(value)}
                  >
                    {value}
                    {value === "Interventions" && (
                      <small>{p.interventions.length}</small>
                    )}
                    {value === "Follow-ups" && (
                      <small>{p.follow_ups.length}</small>
                    )}
                  </button>
                ))}
              </nav>
              <section className="dossier-section" aria-label={tab}>
                {tab === "Overview" && (
                  <DossierOverview
                    profile={p}
                    predictionAction={predictionButton}
                    warningActions={warningActions}
                    onAcademic={() => setTab("Academic record")}
                    onHistory={() => setTab("History")}
                    onInterventions={() => setTab("Interventions")}
                    onFollowUps={() => setTab("Follow-ups")}
                  />
                )}
                {tab === "Academic record" && (
                  <div className="dossier-stack">
                    <DossierCard
                      title="Student & demographics"
                      action={editButton("student")}
                    >
                      <RecordValues record={p.student} />
                    </DossierCard>
                    <DossierCard
                      title="Admission data"
                      action={editButton("admission")}
                    >
                      {p.admission ? (
                        <RecordValues record={p.admission} />
                      ) : (
                        <p className="dossier-empty">No admission record.</p>
                      )}
                    </DossierCard>
                    <DossierCard
                      title="First-semester academic data"
                      action={editButton("semester_one")}
                    >
                      {p.semester_one ? (
                        <RecordValues record={{ ...p.semester_one }} />
                      ) : (
                        <p className="dossier-empty">
                          No first-semester record.
                        </p>
                      )}
                    </DossierCard>
                    <ReadinessCard profile={p} />
                  </div>
                )}
                {tab === "Predictions" && (
                  <div className="dossier-stack">
                    <ReadinessCard profile={p} action={predictionButton} />
                    <DossierCard title="Prediction history">
                      {p.prediction_history.length === 0 ? (
                        <p className="dossier-empty">No saved predictions.</p>
                      ) : (
                        p.prediction_history.map((item) => (
                          <PredictionRecord key={item.id} prediction={item} />
                        ))
                      )}
                    </DossierCard>
                  </div>
                )}
                {tab === "Warnings" && (
                  <div className="dossier-stack">
                    <DossierCard title="Active warning">
                      {p.open_warnings[0] ? (
                        <WarningRecord
                          warning={p.open_warnings[0]}
                          action={warningActions(p.open_warnings[0])}
                        />
                      ) : (
                        <p className="dossier-empty">No active warning.</p>
                      )}
                    </DossierCard>
                    <DossierCard title="Warning history">
                      {p.warning_history.length === 0 ? (
                        <p className="dossier-empty">No warnings recorded.</p>
                      ) : (
                        p.warning_history.map((item) => (
                          <WarningRecord
                            key={item.id}
                            warning={item}
                            action={warningActions(item)}
                          />
                        ))
                      )}
                    </DossierCard>
                  </div>
                )}
                {tab === "Interventions" && (
                  <DossierCard title="Interventions & advisor notes">
                    <p className="dossier-muted">
                      Open an intervention to inspect its notes, follow-ups and
                      recorded outcome.
                    </p>
                    {p.interventions.length === 0 ? (
                      <p className="dossier-empty">
                        No interventions recorded. A confirmed warning is
                        required to create an intervention.
                      </p>
                    ) : (
                      p.interventions.map((item) => (
                        <article className="dossier-case" key={item.id}>
                          <div className="dossier-row">
                            <h3>{item.title}</h3>
                            <DossierBadge value={item.status} />
                            <DossierBadge value={item.priority} />
                          </div>
                          <p>
                            {readable(item.type)} ·{" "}
                            {item.assigned_advisor?.full_name ??
                              "Advisor unavailable"}
                          </p>
                          <p className="dossier-muted">
                            Start {item.start_date} · Target{" "}
                            {item.target_date ?? "Not recorded"}
                            {item.completion_outcome &&
                              ` · Outcome: ${readable(item.completion_outcome)}`}
                          </p>
                          <button
                            className="dash-button"
                            disabled={state.busy}
                            onClick={() =>
                              setDialog({ kind: "case", id: item.id })
                            }
                          >
                            Open Intervention: {item.title}
                          </button>
                        </article>
                      ))
                    )}
                  </DossierCard>
                )}
                {tab === "Follow-ups" && (
                  <DossierCard title="Scheduled follow-ups & outcomes">
                    {p.follow_ups.length === 0 ? (
                      <p className="dossier-empty">
                        No follow-ups recorded. Schedule a follow-up from an
                        intervention.
                      </p>
                    ) : (
                      p.follow_ups.map((item) => (
                        <article className="dossier-case" key={item.id}>
                          <div className="dossier-row">
                            <h3>{item.purpose}</h3>
                            <DossierBadge value={item.effective_status} />
                          </div>
                          <p>
                            {timestamp(item.scheduled_for)} ·{" "}
                            {readable(item.method)} ·{" "}
                            {item.assigned_advisor?.full_name ??
                              "Advisor unavailable"}
                          </p>
                          {item.outcome && (
                            <p>Outcome: {readable(item.outcome)}</p>
                          )}
                          <button
                            className="dash-button"
                            disabled={state.busy}
                            onClick={() =>
                              setDialog({ kind: "follow", id: item.id })
                            }
                          >
                            Open Follow-Up: {item.purpose}
                          </button>
                        </article>
                      ))
                    )}
                  </DossierCard>
                )}
                {tab === "History" && <DossierTimeline profile={p} />}
              </section>
            </>
          )}
        </main>
      </div>
      {dialog?.kind === "academic" && p && state.canEdit && (
        <AcademicEditor
          section={dialog.section}
          profile={p}
          token={state.token}
          busy={state.busy}
          onClose={close}
          mutate={state.mutate}
        />
      )}
      {dialog?.kind === "predict" && p && state.canEdit && (
        <ActionModal
          title="Run Student Prediction"
          busy={state.busy}
          onClose={close}
        >
          <p>
            Create a new assessment for {p.student.name} from their current
            recorded features.
          </p>
          <p className="dossier-muted">
            Readiness is checked again before the prediction is saved.
          </p>
          <label className="dossier-stage-select">
            Prediction stage
            <select
              disabled={state.busy}
              value={predictionStage}
              onChange={(event) =>
                setPredictionStage(event.target.value as StageSelection)
              }
            >
              {(["ENROLLMENT", "FIRST_SEMESTER", "LEGACY"] as const).map(
                (stage) => (
                  <option key={stage} value={stage}>
                    {stageLabel(stage)}
                  </option>
                ),
              )}
            </select>
          </label>
          <p className="dossier-muted">
            {predictionStage === "LEGACY"
              ? "Uses the preserved binary model and its 30-input contract."
              : `${p.stage_readiness.find((stage) => stage.prediction_stage === predictionStage)?.available_feature_count ?? 0} / ${p.stage_readiness.find((stage) => stage.prediction_stage === predictionStage)?.required_feature_count ?? 0} inputs available · Model ${p.stage_readiness.find((stage) => stage.prediction_stage === predictionStage)?.model_status.toLowerCase() ?? "unavailable"}.`}
          </p>
          {state.error && (
            <p className="dash-inline-error" role="alert">
              {state.error}
            </p>
          )}
          <div className="dash-modal-actions">
            <button
              className="dash-button"
              disabled={state.busy}
              onClick={close}
            >
              Close
            </button>
            <button
              className="dash-button dash-button-primary"
              disabled={
                state.busy ||
                (predictionStage === "LEGACY"
                  ? p.prediction_readiness.status !== "READY"
                  : p.stage_readiness.find(
                      (stage) => stage.prediction_stage === predictionStage,
                    )?.status !== "READY")
              }
              onClick={() =>
                void state
                  .mutate(
                    () =>
                      predictStudent(
                        state.token,
                        studentId,
                        predictionStage === "LEGACY"
                          ? undefined
                          : predictionStage,
                      ),
                    "Prediction saved. Risk and warning information have been refreshed.",
                  )
                  .then((error) => {
                    if (!error) setDialog(null);
                  })
              }
            >
              {state.busy ? "Running…" : "Confirm Prediction"}
            </button>
          </div>
        </ActionModal>
      )}
      {dialog?.kind === "assign" && state.canEdit && (
        <ActionModal
          title="Assign Warning Advisor"
          busy={state.busy}
          onClose={close}
        >
          <p>
            Choose an active Academic Advisor from the directory, or select
            Unassigned to remove the assignment.
          </p>
          <DossierForm
            fields={[
              { key: "assigned_to", label: "Assigned advisor", optional: true },
            ]}
            initial={{
              assigned_to: dialog.warning.assigned_advisor?.user_id ?? "",
            }}
            onCancel={close}
            onSubmit={async (values) => {
              const result = await state.mutate(() =>
                assignStudentWarning(
                  state.token,
                  dialog.warning.id,
                  values.assigned_to || null,
                  dialog.warning.revision,
                ),
              );
              if (!result || result.includes("This record changed"))
                setDialog(null);
              return result;
            }}
          />
        </ActionModal>
      )}
      {dialog?.kind === "review" &&
        state.canCase &&
        u?.role === "ACADEMIC_ADVISOR" &&
        dialog.warning.assigned_advisor?.user_id === u.id && (
          <ActionModal
            title="Review Student Warning"
            busy={state.busy || reviewBusy}
            onClose={close}
          >
            <WarningReviewForm
              reconsider={dialog.warning.review_state !== "PENDING_REVIEW"}
              onBusy={setReviewBusy}
              onSubmit={async (input) => {
                const result = await state.mutate(() =>
                  dialog.warning.review_state === "PENDING_REVIEW"
                    ? reviewWarning(state.token, dialog.warning.id, {
                        ...input,
                        expected_revision: dialog.warning.revision,
                      })
                    : reconsiderWarning(state.token, dialog.warning.id, {
                        ...input,
                        reason: input.reason!,
                        expected_revision: dialog.warning.revision,
                      }),
                );
                if (!result || result.includes("This record changed"))
                  setDialog(null);
                return result;
              }}
            />
          </ActionModal>
        )}
      {dialog?.kind === "create" && p && state.canCase && (
        <QuickInterventionModal
          title="Create Student Intervention"
          student={{
            student_id: studentId,
            warning_id: dialog.warning.id,
            name: p.student.name,
            student_number: p.student.student_number,
            priority: dialog.warning.priority,
            assigned_advisor: dialog.warning.assigned_advisor,
          }}
          onClose={close}
          onSubmit={async (input) => {
            const result = await state.mutate(() =>
              createIntervention(state.token, input),
            );
            if (!result) setDialog(null);
            return result;
          }}
        />
      )}
      {dialog?.kind === "case" && u && (
        <CaseDetail
          key={dialog.id}
          id={dialog.id}
          token={state.token}
          user={u}
          canCase={state.canCase}
          recoveryRevision={state.recoveryRevision}
          busy={state.busy}
          mutate={state.mutate}
          report={state.report}
          onClose={close}
        />
      )}
      {dialog?.kind === "follow" && u && (
        <FollowUpDetail
          key={dialog.id}
          id={dialog.id}
          token={state.token}
          user={u}
          canCase={state.canCase}
          recoveryRevision={state.recoveryRevision}
          caseOwned={
            p?.interventions.find(
              (item) =>
                item.id ===
                p.follow_ups.find((f) => f.id === dialog.id)?.intervention_id,
            )?.assigned_advisor?.user_id === u.id
          }
          busy={state.busy}
          mutate={state.mutate}
          report={state.report}
          onClose={close}
        />
      )}
    </div>
  );
}
