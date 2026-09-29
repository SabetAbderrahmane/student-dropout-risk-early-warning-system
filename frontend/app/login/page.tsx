"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { ApiError, fetchCurrentUser, login } from "@/lib/api";
import { clearAccessToken, saveAccessToken } from "@/lib/auth";
import type { User } from "@/types/auth";

export default function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    clearAccessToken();

    try {
      const token = await login(identifier, password);
      saveAccessToken(token.access_token);
      setUser(await fetchCurrentUser(token.access_token));
      setPassword("");
    } catch (caught) {
      clearAccessToken();
      setUser(null);
      setError(caught instanceof ApiError ? caught.message : "Unable to sign in right now.");
    } finally {
      setLoading(false);
    }
  }

  if (user) {
    return (
      <main className="page-shell">
        <section className="auth-card" aria-live="polite">
          <div className="eyebrow">Authenticated</div>
          <h1>Welcome, {user.full_name}</h1>
          <dl className="account-details">
            <div>
              <dt>Username</dt>
              <dd>{user.username}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{user.role.replaceAll("_", " ")}</dd>
            </div>
          </dl>
          <p className="muted">
            Domain workflows and dashboards will be added only in their approved phases.
          </p>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              clearAccessToken();
              setUser(null);
            }}
          >
            Sign out locally
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <section className="auth-card">
        <Link className="back-link" href="/">
          ← Back
        </Link>
        <div className="eyebrow">Secure access</div>
        <h1>Sign in</h1>
        <p className="muted">Use your username or institutional email address.</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="identifier">Username or email</label>
          <input
            autoComplete="username"
            id="identifier"
            maxLength={320}
            onChange={(event) => setIdentifier(event.target.value)}
            required
            value={identifier}
          />
          <label htmlFor="password">Password</label>
          <input
            autoComplete="current-password"
            id="password"
            maxLength={1024}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="primary-button" disabled={loading} type="submit">
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

