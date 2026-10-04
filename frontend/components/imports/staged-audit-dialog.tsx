import { useEffect, useRef, useState } from "react";
import { fetchStagedActions } from "@/lib/api";
import { stagedError } from "@/lib/staged-imports";
import { readable, timestamp } from "@/lib/dashboard";
import { ActionModal } from "@/components/dashboard/action-modal";
import type { StagedActionPage } from "@/types/staged-import";
import { StagedPagination } from "./staged-pagination";
export function StagedAuditDialog({
  batchId,
  token,
  onClose,
  onError,
}: {
  batchId: string;
  token: string;
  onClose: () => void;
  onError: (caught: unknown) => void;
}) {
  const [data, setData] = useState<StagedActionPage | null>(null);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const errorHandler = useRef(onError);
  errorHandler.current = onError;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    fetchStagedActions(token, batchId, page, size, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(stagedError(caught));
          errorHandler.current(caught);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, batchId, page, size, retry]);
  return (
    <ActionModal
      title="Batch Audit Actions"
      className="import-audit-modal"
      busy={false}
      onClose={onClose}
    >
      <p className="import-muted">
        Backend action records show who changed the batch, when and what
        changed.
      </p>
      {loading && (
        <div
          className="warning-table-loading"
          role="status"
          aria-label="Loading batch audit"
        >
          <div className="warning-skeleton warning-skeleton-row" />
        </div>
      )}
      {error && (
        <div className="dash-inline-error" role="alert">
          {error}
          <button
            className="dash-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry audit
          </button>
        </div>
      )}
      {data && !loading && !data.items.length && (
        <p className="import-empty">No action records returned.</p>
      )}
      {data &&
        !loading &&
        data.items.map((action) => (
          <article key={action.id} className="import-audit-item">
            <div>
              <strong>{readable(action.action)}</strong>
              <span>
                Revision {action.batch_version} · {timestamp(action.created_at)}
              </span>
            </div>
            <p className="import-mono">
              Actor {action.actor_id}
              {action.row_id ? ` · Row ${action.row_id}` : ""}
            </p>
            <details>
              <summary>Recorded changes</summary>
              <pre>{JSON.stringify(action.changes, null, 2)}</pre>
            </details>
          </article>
        ))}
      {data && !loading && (
        <StagedPagination
          data={data}
          label="Actions"
          onPage={setPage}
          onSize={(value) => {
            setSize(value);
            setPage(1);
          }}
        />
      )}
    </ActionModal>
  );
}
