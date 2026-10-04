import { useState } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import { readable } from "@/lib/dashboard";
import type { StagedCorrectionRequest } from "@/types/staged-import";
import type { RowSession } from "./use-staged-review";
export function StagedEditDialog({
  session,
  readOnly,
  busy,
  error,
  onClose,
  onSave,
}: {
  session: RowSession;
  readOnly: boolean;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (
    changes: Omit<
      StagedCorrectionRequest,
      "expected_batch_version" | "expected_row_version"
    >,
  ) => void;
}) {
  const { row } = session;
  const [draft, setDraft] = useState({ ...row.edited_values });
  const [included, setIncluded] = useState(row.included);
  const changes = Object.fromEntries(
    Object.entries(draft).filter(
      ([field, value]) => value !== row.edited_values[field],
    ),
  );
  const changed = Object.keys(changes).length > 0 || included !== row.included;
  return (
    <ActionModal
      title={`${readOnly ? "View" : "Correct"} CSV Row ${row.row_number}`}
      className="import-edit-modal"
      busy={busy}
      onClose={onClose}
    >
      <p className="import-muted">
        Batch revision {session.batchVersion} · Row revision {row.version}.
        Enter actual source values; numeric cells are sent as strings.
      </p>
      {error && (
        <div className="dash-inline-error" role="alert">
          {error}
        </div>
      )}
      {session.blocked && (
        <p className="import-draft-notice" role="status">
          Your draft has not been saved. The latest batch and rows have been
          reloaded. Close this dialog to review them before making another
          correction.
        </p>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!readOnly && !busy && !session.blocked && changed)
            onSave({
              ...(Object.keys(changes).length ? { values: changes } : {}),
              ...(included !== row.included ? { included } : {}),
            });
        }}
      >
        {readOnly ? (
          <p className="import-edit-inclusion">
            {included ? "Included in the commit" : "Excluded from the commit"}
          </p>
        ) : (
          <label className="import-edit-inclusion">
            <input
              type="checkbox"
              checked={included}
              disabled={readOnly || busy || session.blocked}
              onChange={(event) => setIncluded(event.target.checked)}
            />
            Include this row in the commit
          </label>
        )}
        <div className="import-edit-fields">
          {Object.keys(row.edited_values).map((field) => (
            <section
              key={field}
              className={
                row.issues.some((issue) => issue.field_name === field)
                  ? "field-has-issues"
                  : ""
              }
            >
              <div>
                <label htmlFor={`csv-field-${field}`}>{readable(field)}</label>
                <small className="import-mono">{field}</small>
                <p>
                  Original value{" "}
                  <span className="import-source-value">
                    {row.original_values[field] === ""
                      ? "(empty source cell)"
                      : row.original_values[field]}
                  </span>
                </p>
              </div>
              <div>
                {readOnly ? (
                  <div className="import-read-value">
                    <span className="import-muted">Current edited value</span>
                    <p className="import-source-value">
                      {draft[field] === ""
                        ? "(empty edited cell)"
                        : draft[field]}
                    </p>
                  </div>
                ) : (
                  <>
                    <label
                      className="import-muted"
                      htmlFor={`csv-field-${field}`}
                    >
                      Current edited value
                    </label>
                    <input
                      id={`csv-field-${field}`}
                      aria-label={`Edited ${field}`}
                      type="text"
                      value={draft[field]}
                      disabled={busy || session.blocked}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          [field]: event.target.value,
                        }))
                      }
                    />
                  </>
                )}
                {row.issues
                  .filter((issue) => issue.field_name === field)
                  .map((issue, index) => (
                    <p className="import-field-issue" key={index}>
                      {issue.error_message}
                      <small>{issue.error_code}</small>
                    </p>
                  ))}
              </div>
            </section>
          ))}
        </div>
        {row.issues
          .filter((issue) => !issue.field_name)
          .map((issue, index) => (
            <p className="import-field-issue" key={index}>
              {issue.error_message}
            </p>
          ))}
        <div className="import-dialog-actions">
          <button
            type="button"
            className="dash-button"
            disabled={busy}
            onClick={onClose}
          >
            {session.blocked ? "Close and review latest rows" : "Close"}
          </button>
          {!readOnly && (
            <button
              type="submit"
              className="dash-button dash-button-primary"
              disabled={busy || session.blocked || !changed}
            >
              {busy ? "Saving and revalidating…" : "Save Correction"}
            </button>
          )}
        </div>
      </form>
    </ActionModal>
  );
}
