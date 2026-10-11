"use client";
import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { changePassword, accountError } from "@/lib/api";
import { clearAccessToken, getAccessToken, saveAccessToken } from "@/lib/auth";
import { useAuthSession } from "@/components/auth/auth-session";
import { ThemeControl } from "@/components/theme/theme-control";

export default function ChangePasswordPage() {
  const { user } = useAuthSession();
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    if (next !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await changePassword(token, current, next);
      saveAccessToken(result.access_token);
      setCurrent("");
      setNext("");
      setConfirmation("");
      router.replace("/dashboard");
    } catch (caught) {
      setError(accountError(caught));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <main className="page-shell">
      <section className="auth-card">
        <div className="auth-theme-row">
          <span className="eyebrow">Account security</span>
          <ThemeControl />
        </div>
        <h1>Change password</h1>
        <p className="muted">
          {user?.must_change_password
            ? "Your temporary password must be replaced before you can use the workspace."
            : "Choose a new password for your account."}{" "}
          Other sessions will be signed out.
        </p>
        <form onSubmit={submit}>
          <label htmlFor="current-password">Current password</label>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={1024}
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            disabled={busy}
          />
          <label htmlFor="new-password">New password</label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={1024}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            disabled={busy}
          />
          <label htmlFor="confirm-password">Confirm new password</label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={1024}
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            disabled={busy}
          />
          <p className="muted">
            Use at least 12 characters and a different password.
          </p>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <button className="primary-button" disabled={busy}>
            {busy ? "Changing…" : "Change password"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => {
              clearAccessToken();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </form>
      </section>
    </main>
  );
}
