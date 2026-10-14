"use client";
import { useState } from "react";
import { recoverFollowUp } from "@/lib/api";
import { FOLLOW_UP_OUTCOMES } from "@/lib/follow-ups";
import {
  DossierForm,
  type DossierField,
} from "@/components/dossier/dossier-form";
import type { FollowUpDetail } from "@/types/casework";
import type { User } from "@/types/auth";

export function IntegrityRecovery({
  record,
  token,
  user,
  busy,
  mutate,
  onDone,
}: {
  record: FollowUpDetail;
  token: string;
  user: User;
  busy: boolean;
  mutate: (work: () => Promise<FollowUpDetail>) => Promise<string | null>;
  onDone: () => void;
}) {
  const [action, setAction] = useState<"ALIGN" | "COMPLETE" | "CANCEL" | null>(
    null,
  );
  if (!record.integrity_issues.length) return null;
  const terminal = record.integrity_issues.includes("TERMINAL_PARENT");
  const fields: DossierField[] = [
    { key: "reason", label: "Recovery reason", type: "textarea" },
  ];
  if (action === "COMPLETE")
    fields.push(
      {
        key: "outcome",
        label: "Genuine follow-up outcome",
        options: FOLLOW_UP_OUTCOMES,
      },
      { key: "notes", label: "Outcome evidence", type: "textarea" },
    );
  return (
    <section className="follow-recorded-outcome">
      <h3>Historical obligation requires recovery</h3>
      <p>
        {terminal
          ? "This scheduled follow-up belongs to a closed intervention. Record its genuine outcome or cancellation reason."
          : "This scheduled follow-up has a different owner from its intervention. Align it with the case owner."}
      </p>
      <p>
        Original ownership remains in the action history. Recovery creates no
        successor.
      </p>
      {user.role === "ACADEMIC_ADMIN" ? (
        <>
          {!action && (
            <div className="follow-detail-actions">
              {terminal ? (
                <>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => setAction("COMPLETE")}
                  >
                    Recover with Outcome
                  </button>
                  <button
                    className="dash-button"
                    disabled={busy}
                    onClick={() => setAction("CANCEL")}
                  >
                    Recover with Cancellation
                  </button>
                </>
              ) : (
                <button
                  className="dash-button"
                  disabled={busy}
                  onClick={() => setAction("ALIGN")}
                >
                  Align with Case Owner
                </button>
              )}
            </div>
          )}
          {action && (
            <DossierForm
              key={action}
              fields={fields}
              submitLabel="Record Recovery"
              onCancel={() => setAction(null)}
              onSubmit={async (values) => {
                const error = await mutate(() =>
                  recoverFollowUp(token, record.id, {
                    action,
                    reason: values.reason,
                    expected_revision: record.revision,
                    ...(action === "COMPLETE"
                      ? {
                          outcome: values.outcome as NonNullable<
                            FollowUpDetail["outcome"]
                          >,
                          notes: values.notes,
                        }
                      : {}),
                  }),
                );
                if (!error) {
                  setAction(null);
                  onDone();
                }
                return error;
              }}
            />
          )}
        </>
      ) : (
        <p>An Academic Admin must resolve this obligation.</p>
      )}
    </section>
  );
}
