import Link from "next/link";
import { readable, timestamp } from "@/lib/dashboard";
import type { StagedBatch } from "@/types/staged-import";
export function StagedStatus({ status }: { status: string }) {
  return (
    <span className={`import-status state-${status.toLowerCase()}`}>
      {readable(status)}
    </span>
  );
}
export function StagedSummary({ batch }: { batch: StagedBatch }) {
  const terminal = batch.status === "COMMITTED" || batch.status === "CANCELLED";
  return (
    <section aria-label="Batch summary">
      <div className="import-batch-identity">
        <div>
          <p className="dash-eyebrow">Selected staged batch</p>
          <h2>{batch.filename}</h2>
          <p className="import-muted">
            Uploaded {timestamp(batch.created_at)} · Updated{" "}
            {timestamp(batch.updated_at)} · Revision {batch.version}
          </p>
          <small className="import-mono">
            Batch {batch.id} · Uploader {batch.uploaded_by}
          </small>
        </div>
        <StagedStatus status={batch.status} />
      </div>
      <div className="import-summary-cards">
        <article className="import-card">
          <h3>Total staged rows</h3>
          <strong className="import-metric">
            {batch.total_rows.toLocaleString()}
          </strong>
          <p>
            {batch.included_rows.toLocaleString()} included ·{" "}
            {batch.excluded_rows.toLocaleString()} excluded
          </p>
        </article>
        <article className="import-card metric-valid">
          <h3>Valid included rows</h3>
          <strong className="import-metric">
            {batch.valid_included_rows.toLocaleString()}
          </strong>
          <p>{batch.valid_rows.toLocaleString()} valid across all rows</p>
        </article>
        <article className="import-card metric-invalid">
          <h3>Invalid included rows</h3>
          <strong className="import-metric">
            {batch.invalid_included_rows.toLocaleString()}
          </strong>
          <p>{batch.invalid_rows.toLocaleString()} invalid across all rows</p>
        </article>
        <article className="import-card">
          <h3>Validation issues</h3>
          <strong className="import-metric">
            {batch.validation_issue_count.toLocaleString()}
          </strong>
          <p>
            {batch.included_issue_count.toLocaleString()} issues in included
            rows
          </p>
        </article>
      </div>
      {batch.last_commit_error && (
        <div className="dash-banner dash-error" role="alert">
          <p>{batch.last_commit_error}</p>
        </div>
      )}
      {batch.status === "COMMITTED" && batch.import_job && (
        <section
          className="import-receipt"
          role="status"
          aria-label="Import receipt"
        >
          <h3>Import committed successfully</h3>
          <p>
            {batch.import_job.valid_rows.toLocaleString()} students imported
            from {batch.import_job.filename}.{" "}
            {batch.excluded_rows.toLocaleString()} staged rows were excluded.
          </p>
          <dl>
            <dt>History receipt</dt>
            <dd className="import-mono">{batch.import_job_id}</dd>
            <dt>Import status</dt>
            <dd>{readable(batch.import_job.status)}</dd>
            <dt>Rows submitted</dt>
            <dd>{batch.import_job.total_rows.toLocaleString()}</dd>
            <dt>Imported / invalid</dt>
            <dd>
              {batch.import_job.valid_rows.toLocaleString()} /{" "}
              {batch.import_job.invalid_rows.toLocaleString()}
            </dd>
            <dt>Completed</dt>
            <dd>{timestamp(batch.import_job.completed_at)}</dd>
          </dl>
          <Link className="dash-button" href="/students">
            Open Student Registry ↗
          </Link>
        </section>
      )}
      {terminal && (
        <p className="import-terminal-note">
          {batch.status === "CANCELLED"
            ? `Cancelled ${timestamp(batch.cancelled_at)}. The pending import is discarded; source values and audit records remain available.`
            : "This batch is committed and read-only. Export and audit remain available."}
        </p>
      )}
    </section>
  );
}
