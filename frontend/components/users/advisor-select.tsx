"use client";
import { useEffect, useId, useState } from "react";
import { accountError, fetchAdvisors } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { AdvisorEntry } from "@/types/user-administration";

export function AdvisorSelect({
  value,
  onChange,
  optional = false,
  label = "Assigned advisor",
  id,
}: {
  value: string;
  onChange: (value: string) => void;
  optional?: boolean;
  label?: string;
  id?: string;
}) {
  const generated = useId();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdvisorEntry[]>([]);
  const [selected, setSelected] = useState<AdvisorEntry | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (search.trim() === query) return;
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
      setItems([]);
    }, 250);
    return () => clearTimeout(timer);
  }, [search, query]);
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    const controller = new AbortController();
    setBusy(true);
    setError("");
    void fetchAdvisors(token, page, query, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setItems((previous) =>
          page === 1
            ? result.items
            : [
                ...previous,
                ...result.items.filter(
                  (item) => !previous.some((old) => old.id === item.id),
                ),
              ],
        );
        setMore(page < result.total_pages);
        const current = result.items.find((item) => item.id === value);
        if (current) setSelected(current);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(accountError(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [page, query, retry, value]);
  return (
    <span style={{ display: "grid", gap: 8 }}>
      <input
        type="search"
        aria-label={`Search ${label.toLowerCase()}`}
        placeholder="Search active advisors by name"
        maxLength={200}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <select
        id={id ?? generated}
        aria-label={label}
        required={!optional}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setSelected(items.find((item) => item.id === e.target.value) ?? null);
        }}
      >
        <option value="">
          {optional ? "Unassigned" : "Choose an active advisor…"}
        </option>
        {value && !items.some((item) => item.id === value) && (
          <option value={value}>
            {selected?.id === value
              ? selected.full_name
              : "Current assignment (outside these results)"}
          </option>
        )}
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.full_name}
          </option>
        ))}
      </select>
      {busy && <small role="status">Loading active advisors…</small>}
      {!busy && !items.length && !error && (
        <small>No active advisors match this search.</small>
      )}
      {error && (
        <span role="alert">
          {error}{" "}
          <button
            type="button"
            className="dash-button"
            onClick={() => setRetry((v) => v + 1)}
          >
            Retry
          </button>
        </span>
      )}
      {more && (
        <button
          type="button"
          className="dash-button"
          disabled={busy}
          onClick={() => setPage((v) => v + 1)}
        >
          Load more advisors
        </button>
      )}
    </span>
  );
}
