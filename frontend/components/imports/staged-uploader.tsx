import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/dashboard/icon";
export function StagedUploader({
  file,
  onFile,
  onUpload,
  busy,
  disabled,
}: {
  file: File | null;
  onFile: (file: File | null) => void;
  onUpload: () => void;
  busy: string;
  disabled: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    if (!file && input.current) input.current.value = "";
  }, [file]);
  return (
    <section
      className={`import-uploader ${dragging ? "is-dragging" : ""}`}
      aria-label="Stage CSV upload"
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        if (!disabled) onFile(event.dataTransfer.files[0] ?? null);
      }}
    >
      <span className="import-upload-icon">
        <Icon name="import" />
      </span>
      <div className="import-upload-copy">
        <h2>Upload a CSV for review</h2>
        <p>
          Use the official 34-column template. UTF-8 with optional BOM · Up to 5
          MiB · 5,000 nonblank data rows.
        </p>
        <p className="import-muted">
          Staging keeps student records unchanged until you explicitly commit.
        </p>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onUpload();
        }}
      >
        <label className="import-file-label">
          {file ? (
            <>
              <strong>{file.name}</strong>
              <span>
                {(file.size / 1024).toLocaleString(undefined, {
                  maximumFractionDigits: 1,
                })}{" "}
                KiB selected
              </span>
            </>
          ) : (
            <>
              <strong>Choose a CSV or drop it here</strong>
              <span>Validated by the backend after upload</span>
            </>
          )}
          <input
            ref={input}
            aria-label="CSV file to stage"
            type="file"
            accept=".csv,text/csv"
            disabled={disabled}
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button
          className="dash-button dash-button-primary"
          disabled={disabled || !file}
          type="submit"
        >
          {busy === "upload" ? "Staging CSV…" : "Stage CSV for Review"}
        </button>
      </form>
    </section>
  );
}
