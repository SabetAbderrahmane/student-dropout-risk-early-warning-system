"use client";
import { useRef, useState } from "react";
import { readable } from "@/lib/dashboard";
export interface DossierField {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "datetime-local" | "textarea";
  optional?: boolean;
  options?: readonly string[];
  maxLength?: number;
  readOnly?: boolean;
}
export function DossierForm({
  fields,
  initial = {},
  submitLabel = "Save",
  onSubmit,
  onCancel,
}: {
  fields: DossierField[];
  initial?: Record<string, string>;
  submitLabel?: string;
  onSubmit: (values: Record<string, string>) => Promise<string | null>;
  onCancel: () => void;
}) {
  const [values, setValues] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  return (
    <form
      className="dossier-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (lock.current) return;
        lock.current = true;
        setBusy(true);
        setError("");
        try {
          const message = await onSubmit(values);
          if (message) setError(message);
        } finally {
          lock.current = false;
          setBusy(false);
        }
      }}
    >
      <fieldset disabled={busy}>
        {fields.map((field) => (
          <label key={field.key}>
            {field.label} {field.optional && <small>Optional</small>}
            {field.options ? (
              <select
                aria-label={field.label}
                required={!field.optional}
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  setValues((v) => ({ ...v, [field.key]: event.target.value }))
                }
              >
                <option value="">Choose…</option>
                {field.options.map((value) => (
                  <option key={value} value={value}>
                    {readable(value)}
                  </option>
                ))}
              </select>
            ) : field.type === "textarea" ? (
              <textarea
                aria-label={field.label}
                rows={4}
                required={!field.optional}
                maxLength={field.maxLength ?? 4000}
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  setValues((v) => ({ ...v, [field.key]: event.target.value }))
                }
              />
            ) : (
              <input
                aria-label={field.label}
                type={field.type ?? "text"}
                step={field.type === "number" ? "any" : undefined}
                required={!field.optional}
                readOnly={field.readOnly}
                maxLength={field.maxLength}
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  setValues((v) => ({ ...v, [field.key]: event.target.value }))
                }
              />
            )}
          </label>
        ))}
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
          onClick={onCancel}
        >
          Close
        </button>
        <button className="dash-button dash-button-primary" disabled={busy}>
          {busy ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
