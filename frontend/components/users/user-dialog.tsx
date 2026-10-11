"use client";
import { useRef, useState, type FormEvent } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import {
  accountError,
  createUser,
  resetUserPassword,
  setUserActive,
  updateUser,
} from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { readable } from "@/lib/dashboard";
import type { User, UserRole } from "@/types/auth";

export const ROLES: UserRole[] = [
  "SYSTEM_ADMIN",
  "ACADEMIC_ADMIN",
  "ACADEMIC_ADVISOR",
];
export type UserAction =
  | { kind: "create" }
  | { kind: "edit" | "role" | "status" | "reset"; user: User };
export function UserDialog({
  action,
  onClose,
  onDone,
}: {
  action: UserAction;
  onClose: () => void;
  onDone: (user: User, message: string) => void;
}) {
  const target = "user" in action ? action.user : null;
  const [username, setUsername] = useState(target?.username ?? "");
  const [email, setEmail] = useState(target?.email ?? "");
  const [name, setName] = useState(target?.full_name ?? "");
  const [role, setRole] = useState<UserRole>(
    target?.role ?? "ACADEMIC_ADVISOR",
  );
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const title =
    action.kind === "create"
      ? "Create User"
      : action.kind === "edit"
        ? "Edit User"
        : action.kind === "role"
          ? "Change Role"
          : action.kind === "reset"
            ? "Reset Password"
            : target?.is_active
              ? "Deactivate User"
              : "Activate User";
  const profile = action.kind === "create" || action.kind === "edit";
  const credentials = action.kind === "create" || action.kind === "reset";
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    if (credentials && password !== confirmation) {
      setError("The temporary passwords do not match.");
      return;
    }
    const token = getAccessToken();
    if (!token) {
      setError("Sign in again to continue.");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const result =
        action.kind === "create"
          ? await createUser(token, {
              username,
              email,
              full_name: name,
              role,
              initial_password: password,
            })
          : action.kind === "edit"
            ? await updateUser(token, target!.id, {
                username,
                email,
                full_name: name,
              })
            : action.kind === "role"
              ? await updateUser(token, target!.id, { role })
              : action.kind === "reset"
                ? await resetUserPassword(token, target!.id, password)
                : await setUserActive(token, target!.id, !target!.is_active);
      setPassword("");
      setConfirmation("");
      onDone(
        result,
        action.kind === "create"
          ? "Account created. Share the temporary credentials through your institution's secure channel; the owner must change the password."
          : action.kind === "reset"
            ? "Temporary password set. Existing sessions have been revoked; the owner must change the password at sign-in."
            : "Account change saved.",
      );
    } catch (caught) {
      setError(accountError(caught));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <ActionModal
      title={title}
      busy={busy}
      onClose={onClose}
      eyebrow="Account administration"
      className="users-dialog"
    >
      {target && (
        <p className="users-target">
          {target.full_name} · {target.username}
        </p>
      )}
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          {profile && (
            <>
              <label>
                Full name
                <input
                  required
                  maxLength={200}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <label>
                Username
                <input
                  required
                  minLength={3}
                  maxLength={50}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  required
                  maxLength={320}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="off"
                />
              </label>
            </>
          )}
          {(action.kind === "role" || action.kind === "create") && (
            <label>
              Role
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {readable(r)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {credentials && (
            <>
              <label>
                Temporary password
                <input
                  type="password"
                  required
                  minLength={12}
                  maxLength={1024}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <label>
                Confirm temporary password
                <input
                  type="password"
                  required
                  minLength={12}
                  maxLength={1024}
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </label>
              <p>
                Use at least 12 characters. Share credentials securely; no
                invitation email is sent. The owner must replace this password
                before using the application.
              </p>
            </>
          )}
          {action.kind === "edit" && (
            <p>
              Changing a username or email revokes existing sessions. The
              account will use its updated login identifiers.
            </p>
          )}
          {action.kind === "role" && (
            <p>
              Changing this role revokes existing sessions and changes access
              permissions immediately. Active advisor assignments must first be
              transferred or completed.
            </p>
          )}
          {action.kind === "status" && (
            <p>
              {target?.is_active
                ? "Deactivation immediately revokes access. Active advisor assignments must first be transferred or completed. Historical records are retained."
                : "Activation restores sign-in eligibility. Any required password change remains in effect."}
            </p>
          )}
          {action.kind === "reset" && (
            <p>
              This reset invalidates the previous password and every existing
              access token.
            </p>
          )}
          <label className="users-confirm">
            <input
              type="checkbox"
              required
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
            />
            I confirm this account change and its access implications.
          </label>
        </fieldset>
        {error && (
          <p role="alert" className="dash-inline-error">
            {error}
          </p>
        )}
        <div className="dash-modal-actions">
          <button
            type="button"
            className="dash-button"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="dash-button dash-button-primary"
            disabled={
              busy ||
              !accepted ||
              (action.kind === "role" && role === target?.role)
            }
          >
            {busy ? "Saving…" : title}
          </button>
        </div>
      </form>
    </ActionModal>
  );
}
