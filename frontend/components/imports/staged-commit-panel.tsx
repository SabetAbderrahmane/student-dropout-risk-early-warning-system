import { Icon } from "@/components/dashboard/icon";
import { isMutableBatch } from "@/lib/staged-imports";
import type { StagedBatch } from "@/types/staged-import";
export function StagedCommitPanel({
  batch,
  canWrite,
  coherent,
  busy,
  onCommit,
  onCancel,
  onExport,
  onAudit,
}: {
  batch: StagedBatch;
  canWrite: boolean;
  coherent: boolean;
  busy: string;
  onCommit: () => void;
  onCancel: () => void;
  onExport: () => void;
  onAudit: () => void;
}) {
  const mutable = isMutableBatch(batch);
  const ready = batch.status === "READY_TO_COMMIT";
  return (
    <section
      className="import-commit-panel"
      aria-label="Batch execution controls"
    >
      <div className="import-commit-context">
        <span className="import-commit-icon">
          <Icon name={batch.status === "COMMITTED" ? "check" : "shield"} />
        </span>
        <div>
          <h2>
            {batch.status === "COMMITTED"
              ? "Import completed"
              : batch.status === "CANCELLED"
                ? "Cancelled batch · Read-only"
                : ready
                  ? "Ready for a reviewed commit"
                  : "Review included rows before committing"}
          </h2>
          <p>
            {mutable
              ? `${batch.included_rows.toLocaleString()} included rows · ${batch.invalid_included_rows.toLocaleString()} invalid included rows · ${batch.included_issue_count.toLocaleString()} included validation issues`
              : `Source values, canonical export and audit remain available.`}
          </p>
          {!canWrite && mutable && (
            <small>Your account has read-only access.</small>
          )}
        </div>
      </div>
      <div className="import-commit-actions">
        <button className="dash-button" disabled={!!busy} onClick={onAudit}>
          Audit Actions
        </button>
        <button className="dash-button" disabled={!!busy} onClick={onExport}>
          {busy === "export" ? "Exporting CSV…" : "Export Edited CSV"}
        </button>
        {canWrite && mutable && (
          <>
            <button
              className="dash-button"
              disabled={!!busy || !coherent}
              onClick={onCancel}
            >
              {busy === "cancel" ? "Cancelling…" : "Cancel Batch"}
            </button>
            <button
              className="dash-button import-commit-button"
              disabled={!!busy || !coherent || !ready || !batch.included_rows}
              onClick={onCommit}
            >
              {busy === "commit" ? "Committing…" : "Commit Included Rows"}
            </button>
          </>
        )}
      </div>
    </section>
  );
}
