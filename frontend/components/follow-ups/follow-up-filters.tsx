"use client";
import { useEffect, useState } from "react";
import { dateRangeInstant, localDate } from "@/lib/follow-ups";
import { readable } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import type { FollowUpParams, FollowUpEffectiveStatus } from "@/types/casework";

const tabs: { value: FollowUpEffectiveStatus | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "OVERDUE", label: "Overdue" },
  { value: "DUE", label: "Due" },
  { value: "SCHEDULED", label: "Scheduled / Upcoming" },
  { value: "COMPLETED", label: "Completed" },
  { value: "CANCELLED", label: "Cancelled" },
];
export function FollowUpFilters({
  user,
  params,
  busy,
  onChange,
  onClear,
}: {
  user: User | null;
  params: FollowUpParams;
  busy: boolean;
  onChange: (values: Partial<FollowUpParams>) => void;
  onClear: () => void;
}) {
  const [search, setSearch] = useState(params.search ?? "");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [dateError, setDateError] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!busy && (search.trim() || undefined) !== params.search)
        onChange({ search: search.trim() || undefined });
    }, 300);
    return () => clearTimeout(timer);
  }, [search, params.search, busy]);
  function clear() {
    setSearch("");
    setFrom("");
    setTo("");
    setDateError("");
    onClear();
  }
  return (
    <section className="follow-filter-panel" aria-label="Follow-up filters">
      <div className="follow-tabs" aria-label="Follow-up status">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            className={tab.value === "OVERDUE" ? "follow-overdue-tab" : ""}
            disabled={busy}
            aria-pressed={(params.status ?? "") === tab.value}
            onClick={() => onChange({ status: tab.value || undefined })}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <fieldset disabled={busy} className="follow-filter-fields">
        <label className="follow-search">
          Search
          <input
            maxLength={200}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Student name, number, or follow-up purpose"
          />
        </label>
        <label>
          Assignee
          <select
            value={params.assigned_to ? "mine" : "all"}
            disabled={!user}
            onChange={(e) =>
              onChange({
                assigned_to: e.target.value === "mine" ? user?.id : undefined,
              })
            }
          >
            <option value="all">All advisors</option>
            <option value="mine">Assigned to Me</option>
          </select>
        </label>
        <label>
          Sort by
          <select
            value={params.sort}
            onChange={(e) =>
              onChange({ sort: e.target.value as FollowUpParams["sort"] })
            }
          >
            {[
              "scheduled_for",
              "created_at",
              "updated_at",
              "student_number",
            ].map((value) => (
              <option key={value} value={value}>
                {readable(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Order
          <select
            value={params.order}
            onChange={(e) =>
              onChange({ order: e.target.value as "asc" | "desc" })
            }
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </label>
      </fieldset>
      <form
        className="follow-date-filter"
        onSubmit={(e) => {
          e.preventDefault();
          if (from && to && from > to) {
            setDateError("The end date must be on or after the start date.");
            return;
          }
          setDateError("");
          onChange({
            from: dateRangeInstant(from),
            to: dateRangeInstant(to, true),
          });
        }}
      >
        <fieldset disabled={busy}>
          <label>
            From date
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <label>
            To date
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
          <button className="dash-button">Apply dates</button>
          <button
            className="dash-button"
            type="button"
            onClick={() => {
              const start = new Date();
              start.setHours(0, 0, 0, 0);
              const end = new Date(start);
              end.setDate(end.getDate() + 7);
              end.setMilliseconds(-1);
              setFrom(localDate(start));
              setTo(localDate(end));
              setDateError("");
              onChange({
                from: start.toISOString(),
                to: end.toISOString(),
                status: "SCHEDULED",
              });
            }}
          >
            Upcoming 7 Days
          </button>
          <button className="dash-button" type="button" onClick={clear}>
            Clear filters
          </button>
        </fieldset>
        {dateError && (
          <p className="follow-field-error" role="alert">
            {dateError}
          </p>
        )}
      </form>
      {(params.from ||
        params.to ||
        params.student_id ||
        params.intervention_id) && (
        <p className="follow-filter-context">
          {params.from || params.to
            ? `Date range: ${params.from ? localDate(new Date(params.from)) : "any start"} – ${params.to ? localDate(new Date(params.to)) : "any end"} (your local time). `
            : ""}
          {params.student_id ? `Student context: ${params.student_id}. ` : ""}
          {params.intervention_id
            ? `Intervention context: ${params.intervention_id}.`
            : ""}
        </p>
      )}
    </section>
  );
}
