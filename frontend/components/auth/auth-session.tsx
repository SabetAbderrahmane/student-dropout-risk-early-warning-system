"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { ApiError, fetchCurrentUser } from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import type { User } from "@/types/auth";

const SessionContext = createContext<{ user: User | null }>({ user: null });
export const useAuthSession = () => useContext(SessionContext);

export function AuthSession({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const publicPage = pathname === "/" || pathname === "/login";
  const [session, setSession] = useState<{
    user: User;
    path: string;
    token: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const fail = (event: Event) => {
      setSession(null);
      if ((event as CustomEvent).detail === "change-password")
        router.replace("/change-password");
      else {
        clearAccessToken();
        router.replace("/login");
      }
    };
    const refresh = () => setRevision((v) => v + 1);
    window.addEventListener("academic-auth-error", fail);
    window.addEventListener("focus", refresh);
    window.addEventListener("academic-session-refresh", refresh);
    return () => {
      window.removeEventListener("academic-auth-error", fail);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("academic-session-refresh", refresh);
    };
  }, [router]);
  useEffect(() => {
    if (publicPage) {
      setSession(null);
      return;
    }
    let active = true;
    const token = getAccessToken();
    setError("");
    if (!token) {
      setSession(null);
      router.replace("/login");
      return;
    }
    void fetchCurrentUser(token)
      .then((user) => {
        if (!active || token !== getAccessToken()) return;
        if (user.must_change_password && pathname !== "/change-password") {
          setSession(null);
          router.replace("/change-password");
        } else setSession({ user, path: pathname, token });
      })
      .catch((caught) => {
        if (!active || token !== getAccessToken()) return;
        setSession(null);
        if (
          caught instanceof ApiError &&
          (caught.status === 401 || caught.code === "USER_INACTIVE")
        ) {
          clearAccessToken();
          router.replace("/login");
        } else
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Unable to verify your session. Check your connection and retry.",
          );
      });
    return () => {
      active = false;
    };
  }, [pathname, publicPage, revision, router]);
  const user = session?.user ?? null;
  if (
    !publicPage &&
    (!session ||
      session.path !== pathname ||
      session.token !== getAccessToken())
  )
    return (
      <main className="page-shell">
        <section className="auth-card" aria-live="polite">
          <h1>{error ? "Session unavailable" : "Verifying access…"}</h1>
          {error && (
            <>
              <p role="alert">{error}</p>
              <button onClick={() => setRevision((v) => v + 1)}>Retry</button>
            </>
          )}
        </section>
      </main>
    );
  return (
    <SessionContext.Provider value={{ user }}>
      {children}
    </SessionContext.Provider>
  );
}
