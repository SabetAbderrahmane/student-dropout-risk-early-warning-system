"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthSession } from "@/components/auth/auth-session";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { accountError, fetchUsers } from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { readable } from "@/lib/dashboard";
import type { UserRole } from "@/types/auth";
import type { UserPage, UserParams } from "@/types/user-administration";
import { ROLES, UserDialog, type UserAction } from "./user-dialog";

export function UsersWorkspace() {
  const { user } = useAuthSession();
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const [params, setParams] = useState<UserParams>({ page: 1, page_size: 20 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<UserPage | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [revision, setRevision] = useState(0);
  const [action, setAction] = useState<UserAction | null>(null);
  const allowed = user?.role === "SYSTEM_ADMIN";
  useEffect(() => {
    const timer = setTimeout(
      () =>
        setParams((p) => ({
          ...p,
          page: 1,
          search: search.trim() || undefined,
        })),
      300,
    );
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!allowed) return;
    const token = getAccessToken();
    if (!token) return;
    const controller = new AbortController();
    setBusy(true);
    setError("");
    setData(null);
    void fetchUsers(token, params, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.total_pages && result.page > result.total_pages)
          setParams((p) => ({ ...p, page: result.total_pages }));
        else setData(result);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(accountError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [allowed, params, revision]);
  function signOut() {
    clearAccessToken();
    router.replace("/login");
  }
  return (
    <div className="dash-root">
      <a className="dash-skip-link" href="#users-main">
        Skip to user management
      </a>
      <AppSidebar open={menu} onClose={() => setMenu(false)} />
      <div className="dash-workspace">
        <AppHeader
          user={user}
          menuOpen={menu}
          onMenu={() => setMenu(!menu)}
          onSignOut={signOut}
          title="User Management"
        />
        <main id="users-main" className="users-main">
          <div className="users-heading">
            <div>
              <p className="dash-eyebrow">Administration</p>
              <h1>User Management</h1>
              <p>Provision institutional accounts and manage access.</p>
            </div>
            {allowed && (
              <button
                className="dash-button dash-button-primary"
                onClick={() => {
                  setFeedback("");
                  setAction({ kind: "create" });
                }}
              >
                + Create User
              </button>
            )}
          </div>
          {!allowed ? (
            <section className="users-panel" role="alert">
              <h2>Permission denied</h2>
              <p>Only System Admins can manage user accounts.</p>
            </section>
          ) : (
            <>
              <section
                className="users-metrics"
                aria-label="Global user counts"
              >
                {(
                  [
                    ["Total Users", "total"],
                    ["Active Users", "active"],
                    ["Academic Admins", "academic_admins"],
                    ["Advisors", "advisors"],
                  ] as const
                ).map(([label, key]) => (
                  <div className="users-panel" key={key}>
                    <p>{label}</p>
                    <strong>{data ? data.counts[key] : "—"}</strong>
                    <small>Across all accounts</small>
                  </div>
                ))}
              </section>
              <section className="users-panel">
                <div className="users-filters">
                  <label>
                    Search accounts
                    <input
                      type="search"
                      placeholder="Name, username or email"
                      maxLength={200}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                  <label>
                    Role
                    <select
                      value={params.role ?? ""}
                      onChange={(e) =>
                        setParams((p) => ({
                          ...p,
                          page: 1,
                          role: (e.target.value || undefined) as
                            | UserRole
                            | undefined,
                        }))
                      }
                    >
                      <option value="">All roles</option>
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {readable(role)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Status
                    <select
                      value={
                        params.is_active === undefined
                          ? ""
                          : String(params.is_active)
                      }
                      onChange={(e) =>
                        setParams((p) => ({
                          ...p,
                          page: 1,
                          is_active:
                            e.target.value === ""
                              ? undefined
                              : e.target.value === "true",
                        }))
                      }
                    >
                      <option value="">All statuses</option>
                      <option value="true">Active</option>
                      <option value="false">Inactive</option>
                    </select>
                  </label>
                </div>
                {feedback && (
                  <p className="users-feedback" role="status">
                    {feedback}
                  </p>
                )}
                {error && (
                  <div role="alert" className="dash-inline-error">
                    <p>{error}</p>
                    <button
                      className="dash-button"
                      onClick={() => setRevision((v) => v + 1)}
                    >
                      Retry
                    </button>
                  </div>
                )}
                {busy && (
                  <p className="users-state" role="status">
                    Loading accounts…
                  </p>
                )}
                {!busy &&
                  data &&
                  (data.items.length ? (
                    <div className="users-table-scroll">
                      <table className="users-table">
                        <caption className="users-sr-only">
                          Institutional user accounts
                        </caption>
                        <thead>
                          <tr>
                            {[
                              "Name",
                              "Username",
                              "Email",
                              "Role",
                              "Status",
                              "Created",
                              "Actions",
                            ].map((label) => (
                              <th scope="col" key={label}>
                                {label}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {data.items.map((account) => (
                            <tr key={account.id}>
                              <th scope="row">
                                {account.full_name}
                                {account.id === user?.id && <small>You</small>}
                              </th>
                              <td>{account.username}</td>
                              <td>{account.email}</td>
                              <td>{readable(account.role)}</td>
                              <td>
                                <span
                                  className={`users-badge ${account.is_active ? "is-active" : "is-inactive"}`}
                                >
                                  {account.is_active ? "Active" : "Inactive"}
                                </span>
                                {account.must_change_password && (
                                  <span className="users-badge needs-password">
                                    Password change required
                                  </span>
                                )}
                              </td>
                              <td>
                                <time dateTime={account.created_at}>
                                  {new Intl.DateTimeFormat("en", {
                                    dateStyle: "medium",
                                  }).format(new Date(account.created_at))}
                                </time>
                              </td>
                              <td>
                                <div className="users-actions">
                                  {(
                                    [
                                      ["edit", "Edit"],
                                      ["role", "Role"],
                                      ["reset", "Reset password"],
                                      [
                                        "status",
                                        account.is_active
                                          ? "Deactivate"
                                          : "Activate",
                                      ],
                                    ] as const
                                  ).map(([kind, label]) => (
                                    <button
                                      className="dash-button"
                                      key={kind}
                                      aria-label={`${label} ${account.username}`}
                                      disabled={
                                        kind === "status" &&
                                        account.is_active &&
                                        account.id === user?.id
                                      }
                                      title={
                                        kind === "status" &&
                                        account.id === user?.id
                                          ? "You cannot deactivate your own account"
                                          : undefined
                                      }
                                      onClick={() => {
                                        setFeedback("");
                                        setAction({ kind, user: account });
                                      }}
                                    >
                                      {label}
                                    </button>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="users-state">
                      <h2>No matching accounts</h2>
                      <p>
                        Change your search or filters to see other accounts.
                      </p>
                    </div>
                  ))}
                {data && (
                  <nav
                    className="users-pagination"
                    aria-label="User pagination"
                  >
                    <span>
                      {data.total} matching accounts · Page {data.page} of{" "}
                      {Math.max(1, data.total_pages)}
                    </span>
                    <div>
                      <button
                        className="dash-button"
                        disabled={busy || params.page <= 1}
                        onClick={() =>
                          setParams((p) => ({ ...p, page: p.page - 1 }))
                        }
                      >
                        Previous
                      </button>
                      <button
                        className="dash-button"
                        disabled={busy || params.page >= data.total_pages}
                        onClick={() =>
                          setParams((p) => ({ ...p, page: p.page + 1 }))
                        }
                      >
                        Next
                      </button>
                    </div>
                  </nav>
                )}
              </section>
            </>
          )}
        </main>
        {action && allowed && (
          <UserDialog
            key={action.kind + ("user" in action ? action.user.id : "")}
            action={action}
            onClose={() => setAction(null)}
            onDone={(result, message) => {
              setAction(null);
              setFeedback(message);
              setRevision((v) => v + 1);
              if (
                result.id === user?.id &&
                (result.role !== user.role ||
                  result.username !== user.username ||
                  result.email !== user.email ||
                  result.must_change_password)
              )
                signOut();
              else if (result.id === user?.id)
                window.dispatchEvent(new Event("academic-session-refresh"));
            }}
          />
        )}
      </div>
    </div>
  );
}
