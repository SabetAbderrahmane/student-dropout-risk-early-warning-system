import { useEffect, useRef, useState } from "react";
import { fetchImports, fetchImportErrors } from "@/lib/api";
import { stagedError } from "@/lib/staged-imports";
import { timestamp, readable } from "@/lib/dashboard";
import { ActionModal } from "@/components/dashboard/action-modal";
import type { ImportJob, ImportJobPage, ImportErrorPage } from "@/types/import";
import { StagedPagination } from "./staged-pagination";
export function ImportHistoryDialog({
  token,
  onClose,
  onError,
}: {
  token: string;
  onClose: () => void;
  onError: (caught: unknown) => void;
}) {
  const [data, setData] = useState<ImportJobPage | null>(null);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [selected, setSelected] = useState<ImportJob | null>(null);
  const [issues, setIssues] = useState<ImportErrorPage | null>(null);
  const [issuePage, setIssuePage] = useState(1);
  const [issueSize, setIssueSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [issueLoading, setIssueLoading] = useState(false);
  const [error, setError] = useState("");
  const [issueError, setIssueError] = useState("");
  const [retry, setRetry] = useState(0);
  const [issueRetry, setIssueRetry] = useState(0);
  const handler = useRef(onError);
  handler.current = onError;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    fetchImports(token, page, size, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(stagedError(caught));
          handler.current(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, page, size, retry]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setIssueLoading(true);
    setIssueError("");
    setIssues(null);
    fetchImportErrors(
      token,
      selected.id,
      issuePage,
      issueSize,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) setIssues(result);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setIssueError(stagedError(caught));
          handler.current(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIssueLoading(false);
      });
    return () => controller.abort();
  }, [token, selected, issuePage, issueSize, issueRetry]);
  return (
    <ActionModal
      title="Import History"
      className="import-history-modal"
      busy={false}
      onClose={onClose}
    >
      <p className="import-muted">
        Historical immediate imports and successful staged commits. Excluded
        staged rows remain in the staged batch, rather than counting as failed
        imports.
      </p>
      {loading && (
        <div
          className="warning-table-loading"
          role="status"
          aria-label="Loading import history"
        >
          <div className="warning-skeleton warning-skeleton-row" />
        </div>
      )}
      {error && (
        <div role="alert" className="dash-inline-error">
          {error}
          <button
            className="dash-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry history
          </button>
        </div>
      )}
      {data && !loading && !data.items.length && (
        <p className="import-empty">No import history yet.</p>
      )}
      {data &&
        !loading &&
        data.items.map((job) => (
          <article className="import-history-item" key={job.id}>
            <div>
              <strong>{job.filename}</strong>
              <span>
                {readable(job.status)} · {timestamp(job.completed_at)}
              </span>
              <p>
                {job.total_rows.toLocaleString()} submitted ·{" "}
                {job.valid_rows.toLocaleString()} imported ·{" "}
                {job.invalid_rows.toLocaleString()} invalid
              </p>
              <small className="import-mono">Receipt {job.id}</small>
            </div>
            <button
              className="dash-button"
              onClick={() => {
                setSelected(job);
                setIssuePage(1);
              }}
            >
              View errors for {job.filename}
            </button>
          </article>
        ))}
      {data && !loading && (
        <StagedPagination
          data={data}
          label="Imports"
          onPage={setPage}
          onSize={(value) => {
            setSize(value);
            setPage(1);
          }}
        />
      )}
      {selected && (
        <section className="import-history-errors">
          <h3>Validation errors · {selected.filename}</h3>
          {issueLoading && (
            <p role="status">Loading import validation errors…</p>
          )}
          {issueError && (
            <p className="dash-inline-error" role="alert">
              {issueError}
              <button
                className="dash-button"
                onClick={() => setIssueRetry((value) => value + 1)}
              >
                Retry history errors
              </button>
            </p>
          )}
          {issues && !issueLoading && (
            <>
              {issues.items.length ? (
                issues.items.map((issue) => (
                  <p key={issue.id} className="import-field-issue">
                    CSV row {issue.row_number} · {issue.field_name ?? "Row"}:{" "}
                    {issue.error_message}
                    <small>{issue.error_code}</small>
                  </p>
                ))
              ) : (
                <p className="import-muted">
                  This import has no recorded validation errors.
                </p>
              )}
              <StagedPagination
                data={issues}
                label="Errors"
                onPage={setIssuePage}
                onSize={(value) => {
                  setIssueSize(value);
                  setIssuePage(1);
                }}
              />
            </>
          )}
        </section>
      )}
    </ActionModal>
  );
}
