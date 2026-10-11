"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError, fetchCurrentUser, login } from "@/lib/api";
import { clearAccessToken, saveAccessToken } from "@/lib/auth";
import { ThemeControl } from "@/components/theme/theme-control";

export default function LoginPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
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
      const user = await fetchCurrentUser(token.access_token);
      setPassword("");
      router.replace(
        user.must_change_password ? "/change-password" : "/dashboard",
      );
    } catch (caught) {
      clearAccessToken();
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Unable to sign in right now.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="auth-card">
        <div className="auth-theme-row">
          <Link className="back-link" href="/">
            ← Back
          </Link>
          <ThemeControl />
        </div>
        <div className="eyebrow">Secure access</div>
        <h1>Sign in</h1>
        <p className="muted">
          Use your username or institutional email address.
        </p>
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
