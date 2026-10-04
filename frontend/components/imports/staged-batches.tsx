import type {
  StagedBatchPage,
  StagedBatchParams,
  StagedImportStatus,
} from "@/types/staged-import";
import { STAGED_STATUSES } from "@/lib/staged-imports";
import { readable, timestamp } from "@/lib/dashboard";
import { StagedStatus } from "./staged-summary";
import { StagedPagination } from "./staged-pagination";
export function StagedBatches({
  data,
  params,
  loading,
  error,
  selectedId,
  disabled,
  onChange,
  onSelect,
  onRetry,
}: {
  data: StagedBatchPage | null;
  params: StagedBatchParams;
  loading: boolean;
  error: string;
  selectedId: string;
  disabled: boolean;
  onChange: (params: StagedBatchParams) => void;
  onSelect: (id: string) => void;
  onRetry: () => void;
}) {
  return (
    <details className="import-card import-batches" open={!selectedId}>
      <summary>
        Staged Batches{" "}
        {data && (
          <span className="warning-count">{data.total.toLocaleString()}</span>
        )}
        <span className="import-muted">
          Resume a review or inspect a completed batch
        </span>
      </summary>
      <div className="import-section-heading">
        <h2>Available staged batches</h2>
        <label className="import-select-label">
          Batch status
          <select
            aria-label="Batch status"
            disabled={disabled}
            value={params.status ?? ""}
            onChange={(event) =>
              onChange({
                ...params,
                status: (event.target.value || undefined) as
                  StagedImportStatus | undefined,
                page: 1,
              })
            }
          >
            <option value="">All statuses</option>
            {STAGED_STATUSES.map((status) => (
              <option key={status} value={status}>
                {readable(status)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading && (
        <div
          className="warning-table-loading"
          role="status"
          aria-label="Loading staged batches"
        >
          <div className="warning-skeleton warning-skeleton-row" />
          <div className="warning-skeleton warning-skeleton-row" />
        </div>
      )}
      {error && (
        <div className="warning-empty" role="alert">
          <p>{error}</p>
          <button className="dash-button" disabled={disabled} onClick={onRetry}>
            Retry batches
          </button>
        </div>
      )}
      {!loading && !error && data?.items.length === 0 && (
        <p className="import-empty">
          No staged batches match this status. Upload a CSV with an Academic
          Admin account to begin.
        </p>
      )}
      {!loading && !error && !!data?.items.length && (
        <div
          className="import-table-scroll"
          tabIndex={0}
          role="region"
          aria-label="Staged batches, scroll for columns"
        >
          <table className="import-table import-batch-table">
            <thead>
              <tr>
                {[
                  "Source file",
                  "Status",
                  "Staged rows",
                  "Issues",
                  "Updated",
                  "Review",
                ].map((label) => (
                  <th key={label} scope="col">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((batch) => (
                <tr key={batch.id}>
                  <td>
                    <strong>{batch.filename}</strong>
                    <small>Revision {batch.version}</small>
                  </td>
                  <td>
                    <StagedStatus status={batch.status} />
                  </td>
                  <td>
                    {batch.total_rows.toLocaleString()}
                    <small>
                      {batch.included_rows.toLocaleString()} included
                    </small>
                  </td>
                  <td>
                    {batch.validation_issue_count.toLocaleString()}
                    <small>
                      {batch.invalid_rows.toLocaleString()} invalid rows
                    </small>
                  </td>
                  <td>{timestamp(batch.updated_at)}</td>
                  <td>
                    <button
                      className="dash-button"
                      disabled={disabled}
                      aria-label={`Open batch ${batch.filename}`}
                      onClick={() => onSelect(batch.id)}
                    >
                      {selectedId === batch.id ? "Selected" : "Open batch"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && !loading && !error && (
        <StagedPagination
          data={data}
          label="Batches"
          disabled={disabled}
          onPage={(page) => onChange({ ...params, page })}
          onSize={(page_size) => onChange({ ...params, page_size, page: 1 })}
        />
      )}
    </details>
  );
}
