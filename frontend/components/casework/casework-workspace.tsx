"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  fetchCurrentUser,
  fetchInterventions,
  fetchFollowUps,
  fetchInterventionDetail,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { readable, timestamp } from "@/lib/dashboard";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { Icon } from "@/components/dashboard/icon";
import { ActionModal } from "@/components/dashboard/action-modal";
import { CaseDetail } from "@/components/dossier/case-detail";
import { FollowUpDetail } from "@/components/dossier/follow-up-detail";
import { DossierBadge } from "@/components/dossier/dossier-records";
import type { User } from "@/types/auth";
import type {
  InterventionParams,
  InterventionPage,
  FollowUpPage,
  FollowUpDetail as FollowUp,
  InterventionDetail,
} from "@/types/casework";
import {
  CreateCaseDrawer,
  CASE_TYPES,
  CASE_PRIORITIES,
} from "./create-case-drawer";
import { CaseworkPagination } from "./pagination";

const INITIAL: InterventionParams = {
  page: 1,
  page_size: 25,
  sort: "urgency",
  order: "asc",
};
const STATUSES = [
  "PLANNED",
  "IN_PROGRESS",
  "ACTION_REQUIRED",
  "COMPLETED",
  "CANCELLED",
] as const;
const SORTS = [
  "urgency",
  "status",
  "priority",
  "updated_at",
  "created_at",
  "start_date",
  "target_date",
  "student_number",
] as const;
type Totals = {
  active: number | null;
  action: number | null;
  completed: number | null;
  follow: number | null;
};

export function CaseworkWorkspace() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [authRetry, setAuthRetry] = useState(0);
  const [revision, setRevision] = useState(0);
  const [menu, setMenu] = useState(false);
  const [params, setParams] = useState<InterventionParams>(INITIAL);
  const [search, setSearch] = useState("");
  const [cases, setCases] = useState<InterventionPage | null>(null);
  const [caseLoading, setCaseLoading] = useState(true);
  const [caseError, setCaseError] = useState("");
  const [totals, setTotals] = useState<Totals>({
    active: null,
    action: null,
    completed: null,
    follow: null,
  });
  const [metricError, setMetricError] = useState("");
  const [followStatus, setFollowStatus] =
    useState<FollowUp["effective_status"]>("OVERDUE");
  const [followPage, setFollowPage] = useState(1);
  const [follows, setFollows] = useState<FollowUpPage | null>(null);
  const [followLoading, setFollowLoading] = useState(true);
  const [followError, setFollowError] = useState("");
  const [caseId, setCaseId] = useState<string | null>(null);
  const [follow, setFollow] = useState<{
    id: string;
    intervention_id: string;
  } | null>(null);
  const [followParent, setFollowParent] = useState<InterventionDetail | null>(
    null,
  );
  const [parentError, setParentError] = useState("");
  const [create, setCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const lock = useRef(false);
  const canCase =
    user?.role === "ACADEMIC_ADMIN" || user?.role === "ACADEMIC_ADVISOR";
  function signOut() {
    clearAccessToken();
    router.replace("/login");
  }
  function report(caught: unknown): string {
    if (caught instanceof ApiError && caught.status === 401) signOut();
    return caught instanceof Error
      ? caught.message
      : "The request could not be completed. Please retry.";
  }
  function refresh() {
    if (!token) setAuthRetry((r) => r + 1);
    else setRevision((r) => r + 1);
  }
  function change(values: Partial<InterventionParams>) {
    setParams((p) => ({ ...p, ...values, page: 1 }));
  }
  function clear() {
    setSearch("");
    setParams(INITIAL);
  }
  async function mutate(work: () => Promise<unknown>): Promise<string | null> {
    if (lock.current) return "A casework action is already in progress.";
    lock.current = true;
    setBusy(true);
    setMessage("");
    try {
      await work();
      setMessage("Casework action saved successfully.");
      setRevision((r) => r + 1);
      return null;
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409)
        setRevision((r) => r + 1);
      return report(caught);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    const access = getAccessToken();
    let active = true;
    if (!access) {
      router.replace("/login");
      return;
    }
    setCaseLoading(true);
    setCaseError("");
    fetchCurrentUser(access)
      .then((current) => {
        if (active) {
          setUser(current);
          setToken(access);
        }
      })
      .catch((caught) => {
        if (active) {
          setCaseError(report(caught));
          setCaseLoading(false);
          setFollowLoading(false);
        }
      });
    const context = new URLSearchParams(window.location.search);
    const interventionId = context.get("intervention_id");
    if (interventionId) setCaseId(interventionId);
    const student_id = context.get("student_id"),
      warning_id = context.get("warning_id");
    if (student_id || warning_id)
      setParams((p) => ({
        ...p,
        ...(student_id ? { student_id } : {}),
        ...(warning_id ? { warning_id } : {}),
      }));
    return () => {
      active = false;
    };
  }, [router, authRetry]);
  useEffect(() => {
    const timer = setTimeout(
      () =>
        setParams((p) =>
          p.search === (search.trim() || undefined)
            ? p
            : { ...p, search: search.trim() || undefined, page: 1 },
        ),
      300,
    );
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!token) return;
    const c = new AbortController();
    setCaseLoading(true);
    setCases(null);
    setCaseError("");
    fetchInterventions(token, params, c.signal)
      .then((data) => {
        if (!c.signal.aborted) {
          if (data.total_pages && data.page > data.total_pages)
            setParams((p) => ({ ...p, page: data.total_pages }));
          else setCases(data);
        }
      })
      .catch((caught) => {
        if (!c.signal.aborted) setCaseError(report(caught));
      })
      .finally(() => {
        if (!c.signal.aborted) setCaseLoading(false);
      });
    return () => c.abort();
  }, [token, params, revision]);
  useEffect(() => {
    if (!token) return;
    const c = new AbortController();
    setMetricError("");
    setTotals({ active: null, action: null, completed: null, follow: null });
    void Promise.allSettled([
      ...["PLANNED", "IN_PROGRESS", "ACTION_REQUIRED", "COMPLETED"].map(
        (status) =>
          fetchInterventions(
            token,
            {
              page: 1,
              page_size: 1,
              status: status as InterventionParams["status"],
            },
            c.signal,
          ),
      ),
      ...["DUE", "OVERDUE"].map((status) =>
        fetchFollowUps(
          token,
          {
            page: 1,
            page_size: 1,
            status: status as FollowUp["effective_status"],
          },
          c.signal,
        ),
      ),
    ]).then((results) => {
      if (c.signal.aborted) return;
      const count = (index: number) =>
        results[index].status === "fulfilled"
          ? results[index].value.total
          : null;
      const sum = (indexes: number[]) =>
        indexes.every((i) => count(i) !== null)
          ? indexes.reduce((total, i) => total + count(i)!, 0)
          : null;
      setTotals({
        active: sum([0, 1, 2]),
        action: count(2),
        completed: count(3),
        follow: sum([4, 5]),
      });
      const errors = results
        .filter((r) => r.status === "rejected")
        .map((r) => report(r.reason));
      setMetricError([...new Set(errors)].join(" "));
    });
    return () => c.abort();
  }, [token, revision]);
  useEffect(() => {
    if (!token) return;
    const c = new AbortController();
    setFollowLoading(true);
    setFollowError("");
    setFollows(null);
    fetchFollowUps(
      token,
      {
        page: followPage,
        page_size: 6,
        status: followStatus,
        sort: "scheduled_for",
        order: "asc",
      },
      c.signal,
    )
      .then((data) => {
        if (!c.signal.aborted) {
          if (data.total_pages && data.page > data.total_pages)
            setFollowPage(data.total_pages);
          else setFollows(data);
        }
      })
      .catch((caught) => {
        if (!c.signal.aborted) setFollowError(report(caught));
      })
      .finally(() => {
        if (!c.signal.aborted) setFollowLoading(false);
      });
    return () => c.abort();
  }, [token, followPage, followStatus, revision]);
  useEffect(() => {
    if (!follow || !token) return;
    const c = new AbortController();
    setFollowParent(null);
    setParentError("");
    fetchInterventionDetail(token, follow.intervention_id, c.signal)
      .then((data) => {
        if (!c.signal.aborted) setFollowParent(data);
      })
      .catch((caught) => {
        if (!c.signal.aborted) setParentError(report(caught));
      });
    return () => c.abort();
  }, [token, follow, revision]);

  return (
    <div className="dash-root dossier-root casework-root">
      <a className="dash-skip-link" href="#casework-main">
        Skip to casework
      </a>
      <AppSidebar open={menu} onClose={() => setMenu(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Interventions & Casework"
          user={user}
          menuOpen={menu}
          onMenu={() => setMenu((v) => !v)}
          onSignOut={signOut}
        />
        <main id="casework-main" className="dash-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="activity" /> Academic support
              </p>
              <h1>Interventions & Casework</h1>
              <p className="dash-description">
                Coordinate support, record case notes, and follow through on
                confirmed warnings.
              </p>
            </div>
            <div className="dash-page-actions">
              <button className="dash-button" disabled={busy} onClick={refresh}>
                <Icon name="refresh" /> Refresh workspace
              </button>
              {canCase && (
                <button
                  className="dash-button dash-button-primary"
                  disabled={busy}
                  onClick={() => setCreate(true)}
                >
                  Create Intervention
                </button>
              )}
            </div>
          </div>
          {message && (
            <div className="dash-banner dash-success" role="status">
              <p>{message}</p>
              <button className="dash-button" onClick={() => setMessage("")}>
                Dismiss
              </button>
            </div>
          )}
          <p className="casework-context">
            Institution-wide totals · Filters apply to the case table below
          </p>
          <section className="casework-metrics" aria-label="Casework totals">
            {[
              [
                "Active Interventions",
                totals.active,
                "Planned, in progress, and action required",
              ],
              ["Action Required", totals.action, "Cases awaiting action"],
              ["Completed", totals.completed, "Recorded intervention outcomes"],
              [
                "Due / Overdue Follow-Ups",
                totals.follow,
                "Scheduled contacts requiring attention",
              ],
            ].map(([label, value, caption]) => (
              <article key={String(label)}>
                <span>{label}</span>
                <strong>
                  {typeof value === "number" ? value.toLocaleString() : "—"}
                </strong>
                <small>{caption}</small>
              </article>
            ))}
          </section>
          {metricError && (
            <div className="dash-banner dash-error" role="alert">
              <p>Some totals are unavailable. {metricError}</p>
              <button className="dash-button" onClick={refresh}>
                Retry totals
              </button>
            </div>
          )}
          <section
            id="follow-ups"
            className="casework-follow-panel"
            aria-labelledby="follow-heading"
          >
            <header className="casework-section-heading">
              <div>
                <p className="dash-eyebrow">Follow through</p>
                <h2 id="follow-heading">Due / Overdue Follow-Ups</h2>
                <p>Review scheduled contacts and record their outcomes.</p>
              </div>
              <div className="casework-tabs" aria-label="Follow-up status">
                {["OVERDUE", "DUE", "SCHEDULED", "COMPLETED", "CANCELLED"].map(
                  (status) => (
                    <button
                      key={status}
                      aria-pressed={followStatus === status}
                      onClick={() => {
                        setFollowStatus(status as FollowUp["effective_status"]);
                        setFollowPage(1);
                      }}
                    >
                      {readable(status)}
                    </button>
                  ),
                )}
              </div>
            </header>
            {followLoading && (
              <p className="casework-empty" role="status">
                Loading follow-ups…
              </p>
            )}
            {followError && (
              <div className="casework-empty" role="alert">
                {followError}{" "}
                <button className="dash-button" onClick={refresh}>
                  Retry follow-ups
                </button>
              </div>
            )}
            {!followLoading &&
              !followError &&
              follows &&
              !follows.items.length && (
                <p className="casework-empty">
                  No {readable(followStatus).toLowerCase()} follow-ups.
                </p>
              )}
            <div className="casework-follow-grid">
              {follows?.items.map((item) => (
                <article key={item.id}>
                  <div className="casework-card-heading">
                    <Link
                      href={`/students/${encodeURIComponent(item.student.id)}`}
                    >
                      <strong>{item.student.name}</strong>
                      <small>{item.student.student_number}</small>
                    </Link>
                    <DossierBadge value={item.effective_status} />
                  </div>
                  <p>{item.purpose}</p>
                  <dl>
                    <dt>Scheduled</dt>
                    <dd>{timestamp(item.scheduled_for)}</dd>
                    <dt>Method</dt>
                    <dd>{readable(item.method)}</dd>
                    <dt>Advisor</dt>
                    <dd>{item.assigned_advisor.full_name}</dd>
                    {item.completed_at && (
                      <>
                        <dt>Completed</dt>
                        <dd>{timestamp(item.completed_at)}</dd>
                      </>
                    )}
                  </dl>
                  <div className="casework-card-actions">
                    <button
                      className="dash-button"
                      onClick={() =>
                        setFollow({
                          id: item.id,
                          intervention_id: item.intervention_id,
                        })
                      }
                    >
                      Open Follow-Up
                    </button>
                    <button
                      className="dash-button"
                      onClick={() => setCaseId(item.intervention_id)}
                    >
                      Related Intervention
                    </button>
                  </div>
                </article>
              ))}
            </div>
            {follows && !followLoading && !followError && (
              <CaseworkPagination
                data={follows}
                noun="follow-ups"
                onPage={setFollowPage}
              />
            )}
          </section>
          <section
            className="casework-filters"
            aria-label="Intervention filters"
          >
            <label className="casework-search">
              Search
              <input
                maxLength={200}
                placeholder="Student name, number, or intervention title"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <label>
              Status
              <select
                value={params.status ?? ""}
                onChange={(e) =>
                  change({
                    status:
                      (e.target.value as InterventionParams["status"]) ||
                      undefined,
                  })
                }
              >
                <option value="">All statuses</option>
                {STATUSES.map((v) => (
                  <option key={v} value={v}>
                    {readable(v)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select
                value={params.priority ?? ""}
                onChange={(e) =>
                  change({
                    priority:
                      (e.target.value as InterventionParams["priority"]) ||
                      undefined,
                  })
                }
              >
                <option value="">All priorities</option>
                {CASE_PRIORITIES.map((v) => (
                  <option key={v} value={v}>
                    {readable(v)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Support type
              <select
                value={params.type ?? ""}
                onChange={(e) =>
                  change({
                    type:
                      (e.target.value as InterventionParams["type"]) ||
                      undefined,
                  })
                }
              >
                <option value="">All types</option>
                {CASE_TYPES.map((v) => (
                  <option key={v} value={v}>
                    {readable(v)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Assignee
              <select
                value={params.assigned_to ? "mine" : "all"}
                disabled={!user}
                onChange={(e) =>
                  change({
                    assigned_to:
                      e.target.value === "mine" ? user?.id : undefined,
                  })
                }
              >
                <option value="all">All advisors</option>
                <option value="mine">My Interventions</option>
              </select>
            </label>
            <label>
              Sort by
              <select
                value={params.sort}
                onChange={(e) =>
                  change({ sort: e.target.value as InterventionParams["sort"] })
                }
              >
                {SORTS.map((v) => (
                  <option key={v} value={v}>
                    {readable(v)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Order
              <select
                disabled={params.sort === "urgency"}
                value={params.order}
                onChange={(e) =>
                  change({ order: e.target.value as "asc" | "desc" })
                }
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </label>
            <button className="dash-button" onClick={clear}>
              Clear filters
            </button>
            {(params.student_id || params.warning_id) && (
              <p className="casework-context">
                Navigation context:{" "}
                {params.student_id && `student ${params.student_id}`}{" "}
                {params.warning_id && `warning ${params.warning_id}`}
              </p>
            )}
          </section>
          <section
            className="casework-table-panel"
            aria-labelledby="case-heading"
          >
            <header className="casework-section-heading">
              <h2 id="case-heading">Intervention cases</h2>
              <span>
                {cases
                  ? `${cases.total.toLocaleString()} matching cases`
                  : "Casework records"}
              </span>
            </header>
            {caseLoading && (
              <p className="casework-empty" role="status">
                Loading intervention cases…
              </p>
            )}
            {caseError && (
              <div className="casework-empty" role="alert">
                {caseError}{" "}
                <button className="dash-button" onClick={refresh}>
                  Retry cases
                </button>
              </div>
            )}
            {!caseLoading && !caseError && cases && !cases.items.length && (
              <div className="casework-empty">
                <p>No interventions match these filters.</p>
                <button className="dash-button" onClick={clear}>
                  Clear filters
                </button>
              </div>
            )}
            {!!cases?.items.length && (
              <div className="casework-table-scroll">
                <table>
                  <thead>
                    <tr>
                      {[
                        "Student",
                        "Related Warning",
                        "Intervention",
                        "Priority",
                        "Assigned Advisor",
                        "Start Date",
                        "Target Date",
                        "Status",
                        "Actions",
                      ].map((label) => (
                        <th key={label} scope="col">
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {cases.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link
                            href={`/students/${encodeURIComponent(item.student.id)}`}
                          >
                            <strong>{item.student.name}</strong>
                            <small>{item.student.student_number}</small>
                          </Link>
                        </td>
                        <td>
                          <span>{readable(item.warning.review_state)}</span>
                          <small title={item.warning.id}>
                            Warning {item.warning.id.slice(0, 8)}
                          </small>
                        </td>
                        <td>
                          <strong>{item.title}</strong>
                          <small>{readable(item.type)}</small>
                        </td>
                        <td>
                          <DossierBadge value={item.priority} />
                        </td>
                        <td>{item.assigned_advisor.full_name}</td>
                        <td>{item.start_date}</td>
                        <td>{item.target_date ?? "—"}</td>
                        <td>
                          <DossierBadge value={item.status} />
                        </td>
                        <td>
                          <button
                            className="dash-button"
                            aria-label={`Open intervention ${item.title} for ${item.student.name}`}
                            onClick={() => setCaseId(item.id)}
                          >
                            Open Case
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {cases && !caseLoading && !caseError && (
              <CaseworkPagination
                data={cases}
                noun="interventions"
                onPage={(page) => setParams((p) => ({ ...p, page }))}
                onSize={(page_size) => change({ page_size })}
              />
            )}
          </section>
        </main>
      </div>
      {caseId && user && (
        <CaseDetail
          key={caseId}
          id={caseId}
          token={token}
          user={user}
          canCase={!!canCase}
          recoveryRevision={revision}
          busy={busy}
          mutate={mutate}
          report={report}
          onClose={() => setCaseId(null)}
          onFollowUp={(id) => {
            setFollow({ id, intervention_id: caseId });
            setCaseId(null);
          }}
        />
      )}
      {follow && !followParent && (
        <ActionModal
          title="Follow-Up"
          busy={busy}
          onClose={() => setFollow(null)}
        >
          <p role={parentError ? "alert" : "status"}>
            {parentError || "Loading linked intervention…"}
          </p>
          {parentError && (
            <button className="dash-button" onClick={refresh}>
              Retry
            </button>
          )}
          <button className="dash-button" onClick={() => setFollow(null)}>
            Close
          </button>
        </ActionModal>
      )}
      {follow && followParent && user && (
        <FollowUpDetail
          key={follow.id}
          id={follow.id}
          token={token}
          user={user}
          caseOwned={followParent.assigned_advisor.id === user.id}
          canCase={!!canCase}
          recoveryRevision={revision}
          busy={busy}
          mutate={mutate}
          report={report}
          onClose={() => setFollow(null)}
        />
      )}
      {create && user && (
        <CreateCaseDrawer
          token={token}
          user={user}
          busy={busy}
          report={report}
          mutate={mutate}
          onClose={() => setCreate(false)}
        />
      )}
    </div>
  );
}
