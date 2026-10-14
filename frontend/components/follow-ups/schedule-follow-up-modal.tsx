"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ActionModal } from "@/components/dashboard/action-modal";
import { CaseworkPagination } from "@/components/casework/pagination";
import { fetchInterventions, fetchInterventionDetail } from "@/lib/api";
import { canScheduleFollowUp, type FollowUpMutation } from "@/lib/follow-ups";
import { readable } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import { useFollowUpResource } from "./use-follow-up-resource";
import { FollowUpForm } from "./follow-up-form";

export function ScheduleFollowUpModal({
  token,
  user,
  busy,
  revision,
  initialId,
  mutate,
  report,
  onRetry,
  onClose,
}: {
  token: string;
  user: User;
  busy: boolean;
  revision: number;
  initialId?: string;
  mutate: FollowUpMutation;
  report: (caught: unknown) => string;
  onRetry: () => void;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(initialId ?? null);
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(input.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [input]);
  const list = useFollowUpResource(
    selected ? "" : `${token}:${user.id}:${user.role}:${page}:${search}`,
    revision,
    (signal) =>
      fetchInterventions(
        token,
        {
          page,
          page_size: 10,
          ...(search ? { search } : {}),
          ...(user.role === "ACADEMIC_ADVISOR" ? { assigned_to: user.id } : {}),
          sort: "updated_at",
          order: "desc",
        },
        signal,
      ),
    report,
  );
  const detail = useFollowUpResource(
    selected ? `${token}:${selected}` : "",
    revision,
    (signal) => fetchInterventionDetail(token, selected!, signal),
    report,
  );
  return (
    <ActionModal
      title="Schedule Follow-Up"
      busy={busy}
      onClose={onClose}
      className="follow-schedule-modal"
    >
      {!selected ? (
        <>
          <p className="follow-muted">
            Choose an existing intervention
            {user.role === "ACADEMIC_ADVISOR" ? " assigned to you" : ""}.
            Completed and cancelled cases cannot receive follow-ups.
          </p>
          <label className="follow-picker-search">
            Search interventions
            <input
              maxLength={200}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Student name, number, or intervention title"
            />
          </label>
          {list.loading && <p role="status">Loading interventions…</p>}
          {list.error && (
            <div role="alert">
              <p>{list.error}</p>
              <button className="dash-button" onClick={onRetry}>
                Retry interventions
              </button>
            </div>
          )}
          {!list.loading &&
            !list.error &&
            list.data &&
            !list.data.items.length && (
              <p>
                No interventions match this search. Create an intervention from
                a confirmed warning in Screen 7 first.
              </p>
            )}
          <div className="follow-intervention-picker">
            {list.data?.items.map((item) => (
              <button
                key={item.id}
                disabled={
                  list.loading ||
                  !!list.error ||
                  !canScheduleFollowUp(user, item)
                }
                onClick={() => setSelected(item.id)}
              >
                <strong>{item.title}</strong>
                <span>
                  {item.student.name} · {item.student.student_number}
                </span>
                <small>
                  {item.assigned_advisor.full_name} · {readable(item.status)}
                </small>
              </button>
            ))}
          </div>
          {list.data && !list.loading && (
            <fieldset
              className="follow-pagination-wrap"
              disabled={!!list.error}
            >
              <CaseworkPagination
                data={list.data}
                noun="interventions"
                onPage={setPage}
              />
            </fieldset>
          )}
        </>
      ) : (
        <>
          <button
            className="dash-button"
            disabled={busy}
            onClick={() => setSelected(null)}
          >
            Choose another intervention
          </button>
          {detail.loading && <p role="status">Loading intervention context…</p>}
          {detail.error && (
            <div className="follow-load-error" role="alert">
              <p>{detail.error}</p>
              <button className="dash-button" onClick={onRetry}>
                Retry intervention
              </button>
            </div>
          )}
          {detail.data && (
            <>
              <div className="follow-schedule-context">
                <strong>{detail.data.title}</strong>
                <Link
                  href={`/students/${encodeURIComponent(detail.data.student.id)}`}
                >
                  {detail.data.student.name} ·{" "}
                  {detail.data.student.student_number}
                </Link>
                <span>
                  {detail.data.assigned_advisor.full_name} ·{" "}
                  {readable(detail.data.status)}
                </span>
              </div>
              {!canScheduleFollowUp(user, detail.data) && (
                <p role="alert">
                  This intervention is not eligible for scheduling by your
                  account. Choose another intervention.
                </p>
              )}
              {canScheduleFollowUp(user, detail.data) && (
                <FollowUpForm
                  key={selected}
                  mode="schedule"
                  token={token}
                  user={user}
                  disabled={detail.loading || !!detail.error}
                  interventionId={selected}
                  parentRevision={detail.data.revision}
                  advisorId={detail.data.assigned_advisor.id}
                  mutate={mutate}
                  onDone={onClose}
                  onCancel={() => setSelected(null)}
                />
              )}
            </>
          )}
        </>
      )}
    </ActionModal>
  );
}
