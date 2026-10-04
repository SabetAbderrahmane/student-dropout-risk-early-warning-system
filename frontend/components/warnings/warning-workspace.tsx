"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  fetchCurrentUser,
  fetchWarnings,
  fetchDashboardOverview,
  createIntervention,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import {
  canCreateWarningIntervention,
  warningError,
  exportWarningPage,
} from "@/lib/warnings";
import type { User } from "@/types/auth";
import type { DashboardOverview, InterventionInput } from "@/types/dashboard";
import type {
  WarningPage,
  WarningRow,
  WarningDetail,
  WarningParams,
} from "@/types/warning";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { Icon } from "@/components/dashboard/icon";
import { WarningKpiStrip } from "./warning-kpi-strip";
import { WarningFilters, WARNING_INITIAL } from "./warning-filters";
import { WarningTable } from "./warning-table";
import { WarningDetailModal } from "./warning-detail-modal";
import { CreateInterventionModal } from "./create-intervention-modal";

export function WarningWorkspace() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [authRetry, setAuthRetry] = useState(0);
  const [revision, setRevision] = useState(0);
  const [params, setParams] = useState<WarningParams>(WARNING_INITIAL);
  const [searchInput, setSearchInput] = useState("");
  const [queue, setQueue] = useState<WarningPage | null>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [highRisk, setHighRisk] = useState<number | null>(null);
  const [queueLoading, setQueueLoading] = useState(true);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [metricsError, setMetricsError] = useState("");
  const [message, setMessage] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [compact, setCompact] = useState(false);
  const [selected, setSelected] = useState<WarningRow | null>(null);
  const [intervention, setIntervention] = useState<WarningDetail | null>(null);
  function signOut() {
    clearAccessToken();
    router.replace("/login");
  }
  function refresh() {
    if (!token) setAuthRetry((value) => value + 1);
    else setRevision((value) => value + 1);
  }
  function change(values: Partial<WarningParams>) {
    setParams((current) => ({ ...current, ...values, page: 1 }));
  }
  function clear() {
    setSearchInput("");
    setParams((current) => ({
      ...WARNING_INITIAL,
      page_size: current.page_size,
      sort: current.sort,
      order: current.order,
    }));
  }

  useEffect(() => {
    let active = true;
    const accessToken = getAccessToken();
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    setQueueLoading(true);
    setMetricsLoading(true);
    setQueueError("");
    fetchCurrentUser(accessToken)
      .then((current) => {
        if (active) {
          setUser(current);
          setToken(accessToken);
        }
      })
      .catch((caught: unknown) => {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        } else {
          setQueueError(warningError(caught));
          setQueueLoading(false);
          setMetricsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [router, authRetry]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setQueueLoading(true);
    setQueueError("");
    setQueue(null);
    fetchWarnings(token, params, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setQueue(data);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        } else setQueueError(warningError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setQueueLoading(false);
      });
    return () => controller.abort();
  }, [token, params, revision, router]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setMetricsLoading(true);
    setMetricsError("");
    setOverview(null);
    setHighRisk(null);
    void Promise.allSettled([
      fetchDashboardOverview(token, controller.signal),
      fetchWarnings(
        token,
        { risk_level: "HIGH", page: 1, page_size: 1 },
        controller.signal,
      ),
    ]).then(([dashboard, count]) => {
      if (controller.signal.aborted) return;
      const errors: string[] = [];
      if (dashboard.status === "fulfilled") setOverview(dashboard.value);
      else {
        if (
          dashboard.reason instanceof ApiError &&
          dashboard.reason.status === 401
        ) {
          clearAccessToken();
          router.replace("/login");
        }
        errors.push(warningError(dashboard.reason));
      }
      if (count.status === "fulfilled") setHighRisk(count.value.total);
      else {
        if (count.reason instanceof ApiError && count.reason.status === 401) {
          clearAccessToken();
          router.replace("/login");
        }
        errors.push(warningError(count.reason));
      }
      setMetricsError(errors.join(" "));
      setMetricsLoading(false);
    });
    return () => controller.abort();
  }, [token, revision, router]);

  useEffect(() => {
    const timer = setTimeout(
      () =>
        setParams((current) =>
          current.search === (searchInput.trim() || undefined)
            ? current
            : { ...current, search: searchInput.trim() || undefined, page: 1 },
        ),
      300,
    );
    return () => clearTimeout(timer);
  }, [searchInput]);

  async function submitIntervention(
    payload: InterventionInput,
  ): Promise<string | null> {
    if (
      !user ||
      !intervention ||
      !canCreateWarningIntervention(user, intervention)
    )
      return "This warning is not eligible for intervention creation by your account.";
    try {
      const receipt = await createIntervention(token, payload);
      setIntervention(null);
      setMessage(`Intervention “${receipt.title}” created successfully.`);
      refresh();
      return null;
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) signOut();
      return warningError(caught);
    }
  }

  return (
    <div className="dash-root warning-root">
      <a className="dash-skip-link" href="#warning-main">
        Skip to warning workspace
      </a>
      <AppSidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Early Warnings / Advisor Triage"
          user={user}
          menuOpen={menuOpen}
          onMenu={() => setMenuOpen((value) => !value)}
          onSignOut={signOut}
        />
        <main id="warning-main" className="dash-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="warning" />
                Academic early warning
              </p>
              <h1>
                Early Warnings{" "}
                <span className="warning-title-note">/ Advisor Triage</span>
              </h1>
              <p className="dash-description">
                Review model evidence, make individual decisions, and coordinate
                academic support.
              </p>
            </div>
            <div className="dash-page-actions">
              <button
                className="dash-button"
                disabled={queueLoading || !queue?.items.length}
                onClick={() => {
                  if (queue) exportWarningPage(queue.items);
                }}
              >
                Export current page CSV
              </button>
              <button
                className="dash-button"
                disabled={queueLoading || metricsLoading}
                onClick={refresh}
              >
                <Icon name="refresh" />
                Refresh workspace
              </button>
            </div>
          </div>
          {message && (
            <div className="dash-banner dash-success" role="status">
              <p>{message}</p>
              <button
                className="dash-icon-button"
                aria-label="Dismiss success message"
                onClick={() => setMessage("")}
              >
                <Icon name="close" />
              </button>
            </div>
          )}
          <div className="warning-metric-context">
            <span className="warning-label">
              Institution-wide warning totals
            </span>
            <span className="warning-muted">Queue filters apply below</span>
          </div>
          <WarningKpiStrip
            overview={overview}
            highRisk={highRisk}
            loading={metricsLoading}
            params={params}
            onFilter={change}
          />
          {metricsError && (
            <div className="dash-banner dash-error" role="alert">
              <p>Some warning totals are unavailable. {metricsError}</p>
              <button className="dash-button" onClick={refresh}>
                Retry metrics
              </button>
            </div>
          )}
          <WarningFilters
            user={user}
            params={params}
            searchInput={searchInput}
            onSearch={setSearchInput}
            onChange={change}
            onClear={clear}
            compact={compact}
            onDensity={setCompact}
          />
          <WarningTable
            data={queue}
            user={user}
            loading={queueLoading}
            error={queueError}
            compact={compact}
            onOpen={setSelected}
            onRetry={refresh}
            onPage={(page) => setParams((current) => ({ ...current, page }))}
            onPageSize={(size) => {
              if ([25, 50, 100].includes(size)) change({ page_size: size });
            }}
            onClear={clear}
          />
          <p className="warning-footnote">
            <Icon name="shield" />
            Model estimates inform support decisions. Each review requires an
            advisor's rationale.
          </p>
        </main>
      </div>
      {selected && user && (
        <WarningDetailModal
          key={selected.id}
          token={token}
          user={user}
          row={selected}
          onClose={() => setSelected(null)}
          onUnauthorized={signOut}
          onReviewed={(decision) => {
            setMessage(
              `Warning ${decision === "CONFIRMED" ? "confirmed" : "dismissed"} successfully. No intervention has been created.`,
            );
            refresh();
          }}
          onIntervention={(detail) => {
            if (canCreateWarningIntervention(user, detail)) {
              setSelected(null);
              setIntervention(detail);
            }
          }}
        />
      )}
      {intervention && (
        <CreateInterventionModal
          warning={intervention}
          onClose={() => setIntervention(null)}
          onSubmit={submitIntervention}
        />
      )}
    </div>
  );
}
