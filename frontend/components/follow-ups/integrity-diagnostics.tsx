"use client";
import { useState } from "react";
import { fetchCaseworkIntegrity } from "@/lib/api";
import { useFollowUpResource } from "./use-follow-up-resource";

export function IntegrityDiagnostics({
  token,
  revision,
  report,
  onSelect,
}: {
  token: string;
  revision: number;
  report: (caught: unknown) => string;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const resource = useFollowUpResource(
    open ? token : "",
    revision,
    (signal) => fetchCaseworkIntegrity(token, signal),
    report,
  );
  return (
    <details
      className="follow-audit"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Casework integrity diagnostics</summary>
      <p>
        Historical ownership mismatches and scheduled contacts under closed
        cases. Select a record to inspect its obligations and available
        recovery.
      </p>
      {resource.loading && <p role="status">Loading diagnostics…</p>}
      {resource.error && <p role="alert">{resource.error}</p>}
      {resource.data?.length === 0 && <p>No unresolved integrity issues.</p>}
      {resource.data?.map((record) => (
        <button
          key={record.id}
          className="follow-related-row"
          onClick={() => onSelect(record.id)}
        >
          <strong>
            {record.student.name} · {record.purpose}
          </strong>
          <span>{record.integrity_issues.join(", ").replaceAll("_", " ")}</span>
        </button>
      ))}
    </details>
  );
}
