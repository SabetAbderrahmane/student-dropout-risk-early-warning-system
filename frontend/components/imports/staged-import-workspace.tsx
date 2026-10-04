"use client";
import Link from "next/link";
import { useState } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { ActionModal } from "@/components/dashboard/action-modal";
import { Icon } from "@/components/dashboard/icon";
import { useStagedReview } from "./use-staged-review";
import { StagedUploader } from "./staged-uploader";
import { StagedSummary } from "./staged-summary";
import { StagedToolbar } from "./staged-toolbar";
import { StagedRowsTable } from "./staged-rows-table";
import { StagedBatches } from "./staged-batches";
import { StagedEditDialog } from "./staged-edit-dialog";
import { StagedCommitPanel } from "./staged-commit-panel";
import { StagedAuditDialog } from "./staged-audit-dialog";
import { ImportHistoryDialog } from "./import-history-dialog";
export function StagedImportWorkspace() {
  const state = useStagedReview();
  const [menuOpen, setMenuOpen] = useState(false);
  const [history, setHistory] = useState(false);
  const [audit, setAudit] = useState(false);
  const [confirm, setConfirm] = useState<"commit" | "cancel" | null>(null);
  const busy = !!state.busy;
  const editable = state.canWrite && state.mutable && state.coherent;
  const step =
    state.batch?.status === "COMMITTED"
      ? 3
      : state.batch?.status === "READY_TO_COMMIT"
        ? 2
        : state.selectedId
          ? 1
          : 0;
  return (
    <div className="dash-root warning-root import-root">
      <a className="dash-skip-link" href="#imports-main">
        Skip to CSV import review
      </a>
      <AppSidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Data Import / CSV Review"
          user={state.user}
          menuOpen={menuOpen}
          onMenu={() => setMenuOpen((value) => !value)}
          onSignOut={state.signOut}
        />
        <main className="dash-main" id="imports-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="import" />
                Academic data onboarding
              </p>
              <h1>Import Student Records</h1>
              <p className="dash-description">
                Stage a CSV, review backend validation, correct source values
                and commit included rows.
              </p>
            </div>
            <div className="dash-page-actions">
              <button
                className="dash-button"
                disabled={busy || state.authLoading}
                onClick={state.refresh}
              >
                <Icon name="refresh" />
                Refresh
              </button>
              {state.canRead && (
                <>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => void state.downloadTemplate()}
                  >
                    {state.busy === "template"
                      ? "Downloading Template…"
                      : "CSV Schema Template"}
                  </button>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => setHistory(true)}
                  >
                    Import History
                  </button>
                </>
              )}
            </div>
          </div>
          {state.error && (
            <div className="dash-banner dash-error" role="alert">
              <p>{state.error}</p>
              <button
                className="dash-button"
                disabled={busy}
                onClick={state.refresh}
              >
                Reload Latest Data
              </button>
            </div>
          )}
          {state.notice && (
            <div className="dash-banner dash-success" role="status">
              <Icon name="check" />
              <p>{state.notice}</p>
            </div>
          )}
          {state.authLoading && (
            <div
              className="warning-table-loading"
              role="status"
              aria-label="Loading import access"
            >
              <div className="warning-skeleton warning-skeleton-row" />
            </div>
          )}
          {!state.authLoading && state.user && !state.canRead && (
            <section className="import-card import-no-access">
              <Icon name="shield" />
              <h2>Import access is restricted</h2>
              <p>
                Staged import review is available to System Admin and Academic
                Admin accounts.
              </p>
              <Link className="dash-button" href="/students">
                Return to Student Registry
              </Link>
            </section>
          )}
          {state.canRead && (
            <>
              <ol className="import-steps" aria-label="CSV import workflow">
                {[
                  "Upload CSV",
                  "Review Validation",
                  "Ready to Commit",
                  "Import Receipt",
                ].map((label, index) => (
                  <li
                    key={label}
                    className={
                      state.batch?.status === "CANCELLED"
                        ? ""
                        : index < step
                          ? "is-complete"
                          : index === step
                            ? "is-current"
                            : ""
                    }
                    aria-current={
                      state.batch?.status !== "CANCELLED" && index === step
                        ? "step"
                        : undefined
                    }
                  >
                    <span>
                      {index < step && state.batch?.status !== "CANCELLED" ? (
                        <Icon name="check" />
                      ) : (
                        index + 1
                      )}
                    </span>
                    <strong>{label}</strong>
                  </li>
                ))}
              </ol>
              {state.canWrite && (
                <StagedUploader
                  file={state.file}
                  onFile={state.setFile}
                  onUpload={() => void state.upload()}
                  busy={state.busy}
                  disabled={busy}
                />
              )}
              <StagedBatches
                data={state.list}
                params={state.listParams}
                loading={state.listLoading}
                error={state.listError}
                selectedId={state.selectedId}
                disabled={busy}
                onChange={state.setListParams}
                onSelect={state.select}
                onRetry={state.refresh}
              />
              {!state.selectedId && (
                <section className="import-start-note">
                  <Icon name="shield" />
                  <div>
                    <h2>
                      {state.canWrite
                        ? "Ready to stage your first review"
                        : "Select a batch to inspect its source rows"}
                    </h2>
                    <p className="import-muted">
                      No batch is selected. Resume a staged batch above
                      {state.canWrite
                        ? " or upload a completed official template"
                        : ""}
                      . Student records are persisted only after an explicit
                      successful commit.
                    </p>
                  </div>
                </section>
              )}
              {state.selectedId && (
                <>
                  {state.batchLoading && (
                    <div
                      className="import-summary-cards"
                      role="status"
                      aria-label="Loading batch summary"
                    >
                      {[0, 1, 2, 3].map((index) => (
                        <div
                          key={index}
                          className="warning-skeleton import-summary-skeleton"
                        />
                      ))}
                    </div>
                  )}
                  {state.batchError && (
                    <div className="warning-empty" role="alert">
                      <strong>Unable to load this batch</strong>
                      <p>{state.batchError}</p>
                      <button
                        className="dash-button"
                        disabled={busy}
                        onClick={state.refresh}
                      >
                        Retry batch
                      </button>
                      <button
                        className="dash-button"
                        disabled={busy}
                        onClick={() => state.select("")}
                      >
                        Choose another batch
                      </button>
                    </div>
                  )}
                  {state.batch && <StagedSummary batch={state.batch} />}
                  {state.batch &&
                    state.rows &&
                    !state.coherent &&
                    !state.rowsLoading &&
                    !state.batchLoading && (
                      <div className="dash-banner dash-error" role="alert">
                        <p>
                          The batch changed while rows were loading. Reload its
                          latest revision before editing.
                        </p>
                        <button className="dash-button" onClick={state.refresh}>
                          Reload batch and rows
                        </button>
                      </div>
                    )}
                  <StagedToolbar
                    params={state.rowParams}
                    search={state.search}
                    onSearch={state.setSearch}
                    onFilter={state.filter}
                    onClear={state.clearFilters}
                    disabled={busy}
                  />
                  <StagedRowsTable
                    data={state.rows}
                    batch={state.batch}
                    loading={state.rowsLoading}
                    error={state.rowsError}
                    editable={editable}
                    busy={busy}
                    onOpen={state.openRow}
                    onInclude={(row) => {
                      if (state.batch)
                        void state.correct(
                          row,
                          state.batch.version,
                          { included: !row.included },
                          row.included ? "exclude" : "restore",
                        );
                    }}
                    onPage={(page) =>
                      state.setRowParams((current) => ({ ...current, page }))
                    }
                    onSize={(page_size) => state.filter({ page_size })}
                    onRetry={state.refresh}
                    onClear={state.clearFilters}
                  />
                  {state.batch && (
                    <StagedCommitPanel
                      batch={state.batch}
                      canWrite={state.canWrite}
                      coherent={state.coherent}
                      busy={state.busy}
                      onCommit={() => setConfirm("commit")}
                      onCancel={() => setConfirm("cancel")}
                      onExport={() => void state.exportCsv()}
                      onAudit={() => setAudit(true)}
                    />
                  )}
                </>
              )}
              <p className="warning-footnote">
                <Icon name="shield" />
                Original and edited source values remain recorded. Validation
                and readiness are determined by the backend.
              </p>
            </>
          )}
        </main>
      </div>
      {state.editor && (
        <StagedEditDialog
          key={state.editor.row.id}
          session={state.editor}
          readOnly={
            !state.canWrite || !state.mutable || (!state.coherent && !busy)
          }
          busy={busy}
          error={state.error}
          onClose={() => state.setEditor(null)}
          onSave={(changes) => {
            if (state.editor)
              void state.correct(
                state.editor.row,
                state.editor.batchVersion,
                changes,
              );
          }}
        />
      )}
      {history && state.canRead && (
        <ImportHistoryDialog
          token={state.token}
          onClose={() => setHistory(false)}
          onError={state.report}
        />
      )}
      {audit && state.batch && state.canRead && (
        <StagedAuditDialog
          key={state.batch.id}
          batchId={state.batch.id}
          token={state.token}
          onClose={() => setAudit(false)}
          onError={state.report}
        />
      )}
      {confirm && state.batch && state.canWrite && (
        <ActionModal
          title={
            confirm === "commit"
              ? "Commit Reviewed Batch"
              : "Cancel Pending Batch"
          }
          busy={busy}
          onClose={() => setConfirm(null)}
        >
          <p className="import-confirm-copy">
            {confirm === "commit"
              ? `Commit ${state.batch.included_rows.toLocaleString()} included rows from ${state.batch.filename}? The backend will revalidate the current source values before persisting student records.`
              : `Cancel ${state.batch.filename}? This pending operation will become read-only. Source values and audit records remain available.`}
          </p>
          <div className="import-dialog-actions">
            <button
              className="dash-button"
              disabled={busy}
              onClick={() => setConfirm(null)}
            >
              Keep Reviewing
            </button>
            <button
              className="dash-button dash-button-primary"
              disabled={
                busy ||
                !state.coherent ||
                !state.mutable ||
                (confirm === "commit" &&
                  (state.batch.status !== "READY_TO_COMMIT" ||
                    !state.batch.included_rows))
              }
              onClick={() => {
                const task =
                  confirm === "commit" ? state.commit() : state.cancel();
                void task.finally(() => setConfirm(null));
              }}
            >
              {busy
                ? "Submitting…"
                : confirm === "commit"
                  ? "Confirm Commit"
                  : "Confirm Cancellation"}
            </button>
          </div>
        </ActionModal>
      )}
    </div>
  );
}
