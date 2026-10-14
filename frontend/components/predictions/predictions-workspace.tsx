"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  fetchCurrentUser,
  fetchPredictions,
  fetchCurrentModel,
  fetchCurrentModelPerformance,
  fetchDashboardOverview,
  runBatchPrediction,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { hasRole } from "@/lib/permissions";
import { predictionError, exportPredictionPage } from "@/lib/predictions";
import type { User } from "@/types/auth";
import type {
  DashboardOverview,
  BatchPredictionResponse,
} from "@/types/dashboard";
import type {
  CurrentModel,
  ModelPerformance,
  PredictionPage,
  PredictionRow,
  PredictionParams,
} from "@/types/prediction";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { Icon } from "@/components/dashboard/icon";
import { ModelKpiStrip } from "./model-kpi-strip";
import { FeatureImportanceCard } from "./feature-importance-card";
import { PerformanceCard } from "./performance-card";
import { ModelMetadataCard, RiskThresholdCard } from "./model-metadata-card";
import { PredictionsFilters, PREDICTION_INITIAL } from "./predictions-filters";
import { PredictionsTable } from "./predictions-table";
import { PredictionDetailModal } from "./prediction-detail-modal";
import { ModelDetailsModal } from "./model-details-modal";
import { BatchPredictionResult } from "./batch-prediction-result";
import { ModelCatalogPanel } from "./model-catalog-panel";
import type { StageSelection } from "@/types/outcome";
export function PredictionsWorkspace() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [authRetry, setAuthRetry] = useState(0);
  const [revision, setRevision] = useState(0);
  const [model, setModel] = useState<CurrentModel | null>(null);
  const [performance, setPerformance] = useState<ModelPerformance | null>(null);
  const [dashboard, setDashboard] = useState<DashboardOverview | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [analyticsError, setAnalyticsError] = useState("");
  const [data, setData] = useState<PredictionPage | null>(null);
  const [params, setParams] = useState<PredictionParams>(PREDICTION_INITIAL);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [compact, setCompact] = useState(false);
  const [selected, setSelected] = useState<PredictionRow | null>(null);
  const [showModel, setShowModel] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);
  const batchLock = useRef(false);
  const [batchError, setBatchError] = useState("");
  const [lastBatchStage, setLastBatchStage] =
    useState<StageSelection>("LEGACY");
  const [batchResult, setBatchResult] =
    useState<BatchPredictionResponse | null>(null);
  function signOut() {
    clearAccessToken();
    router.replace("/login");
  }
  function refresh() {
    if (!token) setAuthRetry((value) => value + 1);
    else setRevision((value) => value + 1);
  }
  function change(values: Partial<PredictionParams>) {
    setParams((current) => ({ ...current, ...values, page: 1 }));
  }
  function clear() {
    setSearch("");
    setParams((current) => ({
      ...PREDICTION_INITIAL,
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
    setLoading(true);
    setAnalyticsLoading(true);
    setError("");
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
          setError(predictionError(caught));
          setLoading(false);
          setAnalyticsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [router, authRetry]);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    fetchPredictions(token, params, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        } else setError(predictionError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, params, revision, router]);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setAnalyticsLoading(true);
    setAnalyticsError("");
    setModel(null);
    setPerformance(null);
    setDashboard(null);
    void Promise.allSettled([
      fetchCurrentModel(token, controller.signal),
      fetchCurrentModelPerformance(token, controller.signal),
      fetchDashboardOverview(token, controller.signal, "LEGACY_BINARY_FIRST_SEMESTER"),
    ]).then(([metadata, metrics, overview]) => {
      if (controller.signal.aborted) return;
      const failures: string[] = [];
      function failure(source: string, caught: unknown) {
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        }
        failures.push(`${source}: ${predictionError(caught)}`);
      }
      if (metadata.status === "fulfilled") setModel(metadata.value);
      else failure("Model metadata", metadata.reason);
      if (metrics.status === "fulfilled") setPerformance(metrics.value);
      else failure("Performance", metrics.reason);
      if (overview.status === "fulfilled") setDashboard(overview.value);
      else failure("Student aggregates", overview.reason);
      setAnalyticsError(failures.join(" "));
      setAnalyticsLoading(false);
    });
    return () => controller.abort();
  }, [token, revision, router]);
  useEffect(() => {
    const timer = setTimeout(
      () =>
        setParams((current) =>
          current.search === (search.trim() || undefined)
            ? current
            : { ...current, search: search.trim() || undefined, page: 1 },
        ),
      300,
    );
    return () => clearTimeout(timer);
  }, [search]);
  async function batch(stage: StageSelection = "LEGACY") {
    if (batchLock.current || !user || !hasRole(user.role, ["ACADEMIC_ADMIN"]))
      return;
    batchLock.current = true;
    setBatchBusy(true);
    setBatchError("");
    setBatchResult(null);
    setLastBatchStage(stage);
    try {
      setBatchResult(
        await runBatchPrediction(token, stage === "LEGACY" ? undefined : stage),
      );
      refresh();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) signOut();
      else setBatchError(predictionError(caught));
    } finally {
      batchLock.current = false;
      setBatchBusy(false);
    }
  }
  return (
    <div className="dash-root warning-root prediction-root">
      <a className="dash-skip-link" href="#predictions-main">
        Skip to prediction analytics
      </a>
      <AppSidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Risk Predictions / Model Performance"
          user={user}
          menuOpen={menuOpen}
          onMenu={() => setMenuOpen((value) => !value)}
          onSignOut={signOut}
        />
        <main id="predictions-main" className="dash-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="activity" />
                Academic analytics
              </p>
              <h1>
                Risk Predictions{" "}
                <span className="prediction-title-note">
                  & Model Performance
                </span>
              </h1>
              <p className="dash-description">
                Review student risk predictions, held-out model performance,
                feature importance and calibrated thresholds.
              </p>
            </div>
            <div className="dash-page-actions">
              <button
                className="dash-button"
                disabled={loading || analyticsLoading || batchBusy}
                onClick={refresh}
              >
                <Icon name="refresh" />
                Refresh
              </button>
              <button
                className="dash-button"
                disabled={!model || analyticsLoading}
                onClick={() => setShowModel(true)}
              >
                Model Details
              </button>
              {user && hasRole(user.role, ["ACADEMIC_ADMIN"]) && (
                <button
                  className="dash-button dash-button-primary"
                  disabled={batchBusy}
                  onClick={() => void batch()}
                >
                  <Icon name="play" />
                  {batchBusy
                    ? "Running batch prediction…"
                    : "Run Legacy Batch Prediction"}
                </button>
              )}
            </div>
          </div>
          <ModelCatalogPanel
            revision={revision}
            onChanged={refresh}
            onBatch={(stage) => void batch(stage)}
            batchBusy={batchBusy}
          />
          <h2>Legacy binary first-semester model</h2>
          <p className="prediction-muted">
            The following performance, feature importance, readiness, and
            student risk aggregates retain the approved binary model's scope.
          </p>
          <div className="prediction-model-ribbon">
            {analyticsLoading ? (
              <span
                className="warning-skeleton prediction-ribbon-skeleton"
                role="status"
                aria-label="Loading model identity"
              />
            ) : model ? (
              <>
                <strong>{model.name}</strong>
                <span>{model.version}</span>
                <span>Dataset: {model.dataset.name}</span>
              </>
            ) : (
              <span className="prediction-muted">
                Current model metadata unavailable
              </span>
            )}
          </div>
          {batchResult && (
            <BatchPredictionResult
              result={batchResult}
              onClose={() => setBatchResult(null)}
            />
          )}{" "}
          {batchError && (
            <div className="dash-banner dash-error" role="alert">
              <p>{batchError}</p>
              <button
                className="dash-button"
                disabled={batchBusy}
                onClick={() => void batch(lastBatchStage)}
              >
                Retry batch prediction
              </button>
            </div>
          )}
          {analyticsError && (
            <div className="dash-banner dash-error" role="alert">
              <p>{analyticsError}</p>
              <button className="dash-button" onClick={refresh}>
                Retry analytics
              </button>
            </div>
          )}
          <ModelKpiStrip
            dashboard={dashboard}
            performance={performance}
            loading={analyticsLoading}
          />
          <div className="prediction-analytics-grid">
            <FeatureImportanceCard
              performance={performance}
              loading={analyticsLoading}
            />
            <PerformanceCard
              performance={performance}
              loading={analyticsLoading}
            />
          </div>
          <div className="prediction-model-grid">
            <ModelMetadataCard model={model} loading={analyticsLoading} />
            <RiskThresholdCard model={model} loading={analyticsLoading} />
          </div>
          <div className="prediction-matrix-intro">
            <div>
              <h2>Student Prediction Records</h2>
              <p className="prediction-muted">
                Records may include multiple predictions per student. Students
                Assessed above counts unique students with a latest legacy
                binary prediction. Records below include all stages.
              </p>
            </div>
            <button
              className="dash-button"
              disabled={loading || !data?.items.length}
              onClick={() => {
                if (data) exportPredictionPage(data.items);
              }}
            >
              Export Current Page
            </button>
          </div>
          <PredictionsFilters
            params={params}
            model={model}
            search={search}
            onSearch={setSearch}
            onChange={change}
            onClear={clear}
            compact={compact}
            onDensity={setCompact}
          />
          <PredictionsTable
            data={data}
            loading={loading}
            error={error}
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
            Model estimates inform academic support decisions. Review warning
            cases in the Early Warnings workspace.
          </p>
        </main>
      </div>
      {selected && (
        <PredictionDetailModal
          key={selected.id}
          row={selected}
          token={token}
          onClose={() => setSelected(null)}
          onUnauthorized={signOut}
        />
      )}{" "}
      {showModel && model && (
        <ModelDetailsModal model={model} onClose={() => setShowModel(false)} />
      )}
    </div>
  );
}
