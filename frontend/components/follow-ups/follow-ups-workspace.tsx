"use client";
import { useEffect, useState } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { Icon } from "@/components/dashboard/icon";
import { useFollowUps } from "./use-follow-ups";
import { FollowUpMetrics } from "./follow-up-metrics";
import { FollowUpFilters } from "./follow-up-filters";
import { FollowUpQueue } from "./follow-up-queue";
import { FollowUpDetailPanel } from "./follow-up-detail-panel";
import { ScheduleFollowUpModal } from "./schedule-follow-up-modal";

export function FollowUpsWorkspace() {
  const state = useFollowUps();
  const [menu, setMenu] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const canSchedule =
    state.user?.role === "ACADEMIC_ADMIN" ||
    state.user?.role === "ACADEMIC_ADVISOR";
  useEffect(() => {
    if (state.scheduleContext && canSchedule) setScheduling(true);
  }, [state.scheduleContext, canSchedule]);
  return (
    <div className="dash-root dossier-root follow-root">
      <a className="dash-skip-link" href="#follow-ups-main">
        Skip to follow-ups
      </a>
      <AppSidebar open={menu} onClose={() => setMenu(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Follow-Ups & Outcomes"
          user={state.user}
          menuOpen={menu}
          onMenu={() => setMenu((v) => !v)}
          onSignOut={state.signOut}
        />
        <main id="follow-ups-main" className="dash-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="calendar" /> Academic support / Follow through
              </p>
              <h1>Follow-Ups & Outcomes</h1>
              <p className="dash-description">
                Review scheduled contacts, record outcomes, and coordinate the
                next step in each intervention.
              </p>
            </div>
            <div className="dash-page-actions">
              <button
                className="dash-button"
                disabled={state.busy}
                onClick={state.refresh}
              >
                <Icon name="refresh" /> Refresh workspace
              </button>
              {canSchedule && (
                <button
                  className="dash-button dash-button-primary"
                  disabled={state.busy}
                  onClick={() => setScheduling(true)}
                >
                  Schedule Follow-Up
                </button>
              )}
            </div>
          </div>
          {state.authLoading && <p role="status">Loading your workspace…</p>}
          {state.authError && (
            <div className="dash-banner dash-error" role="alert">
              <p>{state.authError}</p>
              <button className="dash-button" onClick={state.refresh}>
                Retry session
              </button>
            </div>
          )}
          {(state.notice || state.mutationError) && (
            <div
              className={`dash-banner ${state.mutationError ? "dash-error" : "dash-success"}`}
              role={state.mutationError ? "alert" : "status"}
            >
              <p>{state.mutationError || state.notice}</p>
              <button className="dash-button" onClick={state.clearNotice}>
                Dismiss
              </button>
            </div>
          )}
          <FollowUpMetrics
            token={state.token}
            revision={state.revision}
            report={state.report}
            onRetry={state.refresh}
          />
          <FollowUpFilters
            user={state.user}
            params={state.params}
            busy={state.busy}
            onChange={state.change}
            onClear={state.clear}
          />
          <div className="follow-split">
            <FollowUpQueue
              data={state.list.data}
              loading={state.list.loading}
              error={state.list.error}
              selectedId={state.selectedId}
              busy={state.busy}
              onSelect={state.select}
              onRetry={state.refresh}
              onPage={state.onPage}
              onSize={(page_size) => state.change({ page_size })}
            />
            {state.selectedId && state.user ? (
              <FollowUpDetailPanel
                key={state.selectedId}
                id={state.selectedId}
                token={state.token}
                user={state.user}
                revision={state.revision}
                busy={state.busy}
                mutate={state.mutate}
                report={state.report}
                onRetry={state.refresh}
                onSelect={state.select}
                onClose={() => state.select(null)}
              />
            ) : (
              <aside
                id="selected-follow-up"
                className="follow-detail follow-detail-placeholder"
              >
                <p className="dash-eyebrow">Outcome workspace</p>
                <h2>Select a follow-up</h2>
                <p>
                  Open a record from the queue to review its intervention,
                  reschedule a contact, or record a completed outcome.
                </p>
              </aside>
            )}
          </div>
        </main>
      </div>
      {scheduling && state.user && canSchedule && (
        <ScheduleFollowUpModal
          token={state.token}
          user={state.user}
          initialId={state.scheduleContext}
          revision={state.revision}
          busy={state.busy}
          mutate={state.mutate}
          report={state.report}
          onRetry={state.refresh}
          onClose={() => setScheduling(false)}
        />
      )}
    </div>
  );
}
