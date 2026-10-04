import type {
  StagedBatch,
  StagedRow,
  StagedRowPage,
} from "@/types/staged-import";
import { StagedPagination } from "./staged-pagination";
export function StagedRowsTable({
  data,
  batch,
  loading,
  error,
  editable,
  busy,
  onOpen,
  onInclude,
  onPage,
  onSize,
  onRetry,
  onClear,
}: {
  data: StagedRowPage | null;
  batch: StagedBatch | null;
  loading: boolean;
  error: string;
  editable: boolean;
  busy: boolean;
  onOpen: (row: StagedRow) => void;
  onInclude: (row: StagedRow) => void;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
  onRetry: () => void;
  onClear: () => void;
}) {
  return (
    <section
      className="import-card import-table-card"
      aria-label="Staged review rows"
      aria-busy={loading}
    >
      <div className="import-section-heading">
        <h2>
          Row Validation Review{" "}
          {data && (
            <span className="warning-count">{data.total.toLocaleString()}</span>
          )}
        </h2>
        <span className="import-muted">
          Original source values preserved · Backend validation
        </span>
      </div>
      {loading && (
        <div
          className="warning-table-loading"
          role="status"
          aria-label="Loading review rows"
        >
          {[0, 1, 2, 3].map((index) => (
            <div
              key={index}
              className="warning-skeleton warning-skeleton-row"
            />
          ))}
        </div>
      )}
      {error && (
        <div className="warning-empty" role="alert">
          <strong>Unable to load review rows</strong>
          <p>{error}</p>
          <button className="dash-button" disabled={busy} onClick={onRetry}>
            Retry rows
          </button>
        </div>
      )}
      {!loading && !error && data?.items.length === 0 && (
        <div className="warning-empty">
          <strong>
            {batch?.total_rows === 0
              ? "This batch has no data rows"
              : data.total > 0
                ? "No rows on this page"
                : "No rows match these filters"}
          </strong>
          <p>
            {batch?.total_rows === 0
              ? "The CSV contains only its header. At least one included valid row is required to commit."
              : data.total > 0
                ? "The backend result changed. Return to the first page to review the remaining rows."
                : "Adjust the validation, inclusion or search filters to view other rows in this batch."}
          </p>
          <button className="dash-button" disabled={busy} onClick={onClear}>
            Clear row filters
          </button>
          {data.total > 0 && (
            <button className="dash-button" onClick={() => onPage(1)}>
              Return to first row page
            </button>
          )}
        </div>
      )}
      {!loading && !error && !!data?.items.length && (
        <div
          className="import-table-scroll"
          role="region"
          aria-label="CSV review table, scroll for columns"
          tabIndex={0}
        >
          <table className="import-table">
            <thead>
              <tr>
                {[
                  "CSV row",
                  "Student number",
                  "Student name",
                  "Inclusion",
                  "Validation diagnostic",
                  "Actions",
                ].map((label) => (
                  <th scope="col" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr
                  key={row.id}
                  className={
                    !row.included
                      ? "row-excluded"
                      : !row.is_valid
                        ? "row-invalid"
                        : ""
                  }
                >
                  <td>
                    <strong>{row.row_number}</strong>
                    <small>Revision {row.version}</small>
                  </td>
                  <td>
                    <span
                      className="import-cell-value import-mono"
                      title={row.edited_values.student_number}
                    >
                      {row.edited_values.student_number ||
                        "(empty student number)"}
                    </span>
                    {row.original_values.student_number !==
                      row.edited_values.student_number && (
                      <small>
                        Original:{" "}
                        {row.original_values.student_number || "(empty)"}
                      </small>
                    )}
                  </td>
                  <td>
                    <strong
                      className="import-cell-value"
                      title={row.edited_values.name}
                    >
                      {row.edited_values.name || "(empty name)"}
                    </strong>
                    {row.original_values.name !== row.edited_values.name && (
                      <small>
                        Original: {row.original_values.name || "(empty)"}
                      </small>
                    )}
                  </td>
                  <td>
                    <span
                      className={`import-inclusion ${row.included ? "is-included" : ""}`}
                    >
                      {row.included ? "Included" : "Excluded"}
                    </span>
                  </td>
                  <td>
                    {row.is_valid ? (
                      <span className="import-valid">
                        Valid · No validation issues
                      </span>
                    ) : (
                      <ul className="import-diagnostics">
                        {row.issues.map((issue, index) => (
                          <li key={`${issue.error_code}-${index}`}>
                            <strong>{issue.field_name ?? "Row"}</strong> ·{" "}
                            {issue.error_message}
                            <small>{issue.error_code}</small>
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td>
                    <div className="import-row-actions">
                      <button
                        className="dash-button"
                        disabled={busy}
                        aria-label={`${editable ? "Edit" : "View"} CSV row ${row.row_number}`}
                        onClick={() => onOpen(row)}
                      >
                        {editable ? "Edit row" : "View row"}
                      </button>
                      {editable && (
                        <button
                          className="import-text-button"
                          disabled={busy}
                          aria-label={`${row.included ? "Exclude" : "Restore"} CSV row ${row.row_number}`}
                          onClick={() => onInclude(row)}
                        >
                          {row.included ? "Exclude" : "Restore"}
                        </button>
                      )}
                    </div>
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
          label="Rows"
          onPage={onPage}
          onSize={onSize}
          disabled={busy}
        />
      )}
    </section>
  );
}
