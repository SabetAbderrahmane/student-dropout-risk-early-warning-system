"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  createIntervention,
  fetchCurrentUser,
  fetchDashboardOverview,
  reviewWarning,
  runBatchPrediction,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { canIntervene, canReview, timestamp } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import type {
  AttentionStudent,
  BatchPredictionResponse,
  DashboardOverview,
  InterventionInput,
  ReviewWarningInput,
} from "@/types/dashboard";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { OverviewView } from "./overview-view";
import { ReviewWarningModal } from "./review-warning-modal";
import { QuickInterventionModal } from "./quick-intervention-modal";
import { Icon } from "./icon";

type SelectedAction = {
  kind: "review" | "intervention";
  student: AttentionStudent;
} | null;
export function DashboardShell() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchResult, setBatchResult] =
    useState<BatchPredictionResponse | null>(null);
  const [feedback, setFeedback] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [action, setAction] = useState<SelectedAction>(null);
  const signOut = useCallback(() => {
    clearAccessToken();
    router.replace("/login");
  }, [router]);
  const failureMessage = useCallback(
    (caught: unknown): string => {
      if (caught instanceof ApiError && caught.status === 401) {
        signOut();
        return "Your session has expired. Redirecting to sign in…";
      }
      return caught instanceof ApiError
        ? caught.message
        : "Unable to reach the academic risk service. Please try again.";
    },
    [signOut],
  );

  useEffect(() => {
    let active = true;
    const token = getAccessToken();
    if (!token) {
      signOut();
      return;
    }
    setLoading(true);
    setError("");
    void (async () => {
      const results = await Promise.allSettled([
        fetchCurrentUser(token),
        fetchDashboardOverview(token),
      ]);
      if (!active) return;
      const authFailure = results.find(
        (result) =>
          result.status === "rejected" &&
          result.reason instanceof ApiError &&
          result.reason.status === 401,
      );
      if (authFailure?.status === "rejected") {
        failureMessage(authFailure.reason);
        return;
      }
      const [identity, overview] = results;
      if (identity.status === "fulfilled") setUser(identity.value);
      if (identity.status === "rejected")
        setError(failureMessage(identity.reason));
      else if (overview.status === "rejected")
        setError(failureMessage(overview.reason));
      else setData(overview.value);
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [retry, signOut, failureMessage]);

  async function refresh() {
    const token = getAccessToken();
    if (!token) {
      signOut();
      return;
    }
    setRefreshing(true);
    setError("");
    try {
      setData(await fetchDashboardOverview(token));
    } catch (caught) {
      setError(failureMessage(caught));
    } finally {
      setRefreshing(false);
    }
  }

  async function submitReview(
    payload: ReviewWarningInput,
  ): Promise<string | null> {
    const token = getAccessToken();
    if (!token) {
      signOut();
      return "Sign in to continue.";
    }
    if (!action || !user || !action.student.warning_id || !canReview(user, action.student))
      return "This warning cannot be reviewed by the current user.";
    try {
      await reviewWarning(token, action.student.warning_id, payload);
    } catch (caught) {
      return failureMessage(caught);
    }
    setAction(null);
    setFeedback("Warning review recorded successfully.");
    setBatchResult(null);
    await refresh();
    return null;
  }

  async function submitIntervention(
    payload: InterventionInput,
  ): Promise<string | null> {
    const token = getAccessToken();
    if (!token) {
      signOut();
      return "Sign in to continue.";
    }
    if (!action || !user || !canIntervene(user, action.student))
      return "This warning is not eligible for a quick intervention by the current user.";
    try {
      await createIntervention(token, payload);
    } catch (caught) {
      return failureMessage(caught);
    }
    setAction(null);
    setFeedback("Academic intervention created successfully.");
    setBatchResult(null);
    await refresh();
    return null;
  }

  async function assess() {
    if (batchBusy || user?.role !== "ACADEMIC_ADMIN") return;
    const token = getAccessToken();
    if (!token) {
      signOut();
      return;
    }
    setBatchBusy(true);
    setError("");
    setFeedback("");
    setBatchResult(null);
    try {
      const result = await runBatchPrediction(token);
      setBatchResult(result);
      setFeedback("Batch risk assessment completed.");
      await refresh();
    } catch (caught) {
      setError(failureMessage(caught));
    } finally {
      setBatchBusy(false);
    }
  }

  return (
    <div className="dash-root">
      <a className="dash-skip-link" href="#dashboard-main">
        Skip to dashboard
      </a>
      <AppSidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="dash-workspace">
        <AppHeader
          user={user}
          menuOpen={menuOpen}
          onMenu={() => setMenuOpen((open) => !open)}
          onSignOut={signOut}
        />
        <main id="dashboard-main" className="dash-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="shield" />
                Institutional decision support
              </p>
              <h1>Academic Risk Overview</h1>
              <p className="dash-description">
                Monitor student records, risk assessments, warnings, and
                academic interventions.
              </p>
            </div>
            <div className="dash-page-actions">
              {data && (
                <button
                  className="dash-button"
                  disabled={refreshing || batchBusy || !!action}
                  onClick={() => void refresh()}
                >
                  <Icon name="refresh" />
                  {refreshing ? "Refreshing…" : "Refresh"}
                </button>
              )}
              {user?.role === "ACADEMIC_ADMIN" && data && (
                <button
                  className="dash-button dash-button-primary"
                  disabled={batchBusy || refreshing || !!action}
                  onClick={() => void assess()}
                >
                  <Icon name="play" />
                  {batchBusy
                    ? "Assessing students…"
                    : "Run Batch Risk Assessment"}
                </button>
              )}
            </div>
          </div>
          {feedback && (
            <div className="dash-banner dash-success" role="status">
              <div>
                <strong>{feedback}</strong>
                {batchResult && (
                  <>
                    <p>
                      Assessed: {batchResult.assessed} · Skipped (not ready):{" "}
                      {batchResult.skipped_not_ready} · Predictions created:{" "}
                      {batchResult.created_predictions} · Warnings created:{" "}
                      {batchResult.created_warnings}
                    </p>
                    <p>
                      Model: {batchResult.model_version} · Completed:{" "}
                      {timestamp(batchResult.completed_at)}
                    </p>
                  </>
                )}
              </div>
              <button
                className="dash-icon-button"
                aria-label="Dismiss success message"
                onClick={() => {
                  setFeedback("");
                  setBatchResult(null);
                }}
              >
                <Icon name="close" />
              </button>
            </div>
          )}
          {error && (
            <div className="dash-banner dash-error" role="alert">
              <div>
                <strong>
                  {data
                    ? "The dashboard may be out of date"
                    : "Unable to load the dashboard"}
                </strong>
                <p>{error}</p>
              </div>
              <button
                className="dash-button"
                disabled={refreshing || batchBusy}
                onClick={() =>
                  data ? void refresh() : setRetry((value) => value + 1)
                }
              >
                Retry
              </button>
            </div>
          )}
          {loading ? (
            <div
              className="dash-loading"
              role="status"
              aria-label="Loading dashboard"
            >
              <div className="dash-kpi-grid">
                {[0, 1, 2, 3].map((index) => (
                  <div className="dash-card dash-skeleton" key={index}>
                    <span />
                    <span />
                    <span />
                  </div>
                ))}
              </div>
              <div className="dash-card dash-loading-panel">
                <Icon name="refresh" />
                <p>Loading your academic risk overview…</p>
              </div>
            </div>
          ) : data && user ? (
            <OverviewView
              data={data}
              user={user}
              disabled={refreshing || batchBusy}
              onReview={(student) => setAction({ kind: "review", student })}
              onIntervene={(student) =>
                setAction({ kind: "intervention", student })
              }
            />
          ) : null}
        </main>
      </div>
      {action?.kind === "review" && (
        <ReviewWarningModal
          student={action.student}
          onClose={() => setAction(null)}
          onSubmit={submitReview}
        />
      )}
      {action?.kind === "intervention" && (
        <QuickInterventionModal
          student={action.student}
          onClose={() => setAction(null)}
          onSubmit={submitIntervention}
        />
      )}
    </div>
  );
}
