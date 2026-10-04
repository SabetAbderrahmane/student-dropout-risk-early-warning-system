import type { User } from "@/types/auth";
import type { WarningParams, WarningSort } from "@/types/warning";
import { readable } from "@/lib/dashboard";

export const WARNING_INITIAL: WarningParams = {
  page: 1,
  page_size: 25,
  sort: "priority",
  order: "asc",
};
const FILTERS = [
  {
    key: "priority",
    label: "Priority",
    all: "All priorities",
    options: ["P1_URGENT", "P2_ELEVATED", "P3_STANDARD"],
  },
  {
    key: "review_state",
    label: "Review state",
    all: "All states",
    options: ["PENDING_REVIEW", "CONFIRMED", "DISMISSED"],
  },
  {
    key: "risk_level",
    label: "Risk level",
    all: "All risk levels",
    options: ["HIGH", "MEDIUM", "LOW"],
  },
] as const;
const SORTS: Array<{
  label: string;
  sort: WarningSort;
  order: "asc" | "desc";
}> = [
  { label: "Priority", sort: "priority", order: "asc" },
  { label: "Newest warning", sort: "created_at", order: "desc" },
  { label: "Oldest warning", sort: "created_at", order: "asc" },
  { label: "Highest risk probability", sort: "probability", order: "desc" },
  { label: "Lowest risk probability", sort: "probability", order: "asc" },
  { label: "Risk level", sort: "risk_level", order: "desc" },
  { label: "Review state", sort: "review_state", order: "asc" },
  { label: "Student ID", sort: "student_number", order: "asc" },
];
export function WarningFilters({
  user,
  params,
  searchInput,
  onSearch,
  onChange,
  onClear,
  compact,
  onDensity,
}: {
  user: User | null;
  params: WarningParams;
  searchInput: string;
  onSearch: (value: string) => void;
  onChange: (values: Partial<WarningParams>) => void;
  onClear: () => void;
  compact: boolean;
  onDensity: (value: boolean) => void;
}) {
  const active = FILTERS.filter((filter) => params[filter.key]);
  const hasFilters =
    !!params.search || !!params.assigned_to || active.length > 0;
  return (
    <section className="warning-filters" aria-label="Warning queue filters">
      <div
        className={`warning-filter-grid ${user?.role === "ACADEMIC_ADVISOR" ? "with-assignment" : ""}`}
      >
        <label className="warning-search">
          <span>Search students</span>
          <input
            type="search"
            maxLength={200}
            value={searchInput}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search by student name or student ID"
          />
        </label>
        {FILTERS.map((filter) => (
          <label key={filter.key}>
            <span>{filter.label}</span>
            <select
              aria-label={filter.label}
              value={params[filter.key] ?? ""}
              onChange={(event) =>
                onChange({
                  [filter.key]: filter.options.find(
                    (value) => value === event.target.value,
                  ),
                })
              }
            >
              <option value="">{filter.all}</option>
              {filter.options.map((value) => (
                <option key={value} value={value}>
                  {readable(value)}
                </option>
              ))}
            </select>
          </label>
        ))}
        {user?.role === "ACADEMIC_ADVISOR" && (
          <label>
            <span>Assignment</span>
            <select
              aria-label="Assignment"
              value={params.assigned_to ? "mine" : "all"}
              onChange={(event) =>
                onChange({
                  assigned_to:
                    event.target.value === "mine" ? user.id : undefined,
                })
              }
            >
              <option value="all">All visible warnings</option>
              <option value="mine">My assigned warnings</option>
            </select>
          </label>
        )}
      </div>
      <div className="warning-filter-meta">
        <div className="warning-chips">
          <span className="warning-label">Active filters</span>
          {params.search && (
            <button className="warning-chip" onClick={() => onSearch("")}>
              Search: {params.search} ×
            </button>
          )}
          {active.map((filter) => (
            <button
              key={filter.key}
              className="warning-chip"
              aria-label={`Remove ${filter.label} filter`}
              onClick={() => onChange({ [filter.key]: undefined })}
            >
              {readable(params[filter.key]!)} ×
            </button>
          ))}
          {params.assigned_to && (
            <button
              className="warning-chip"
              onClick={() => onChange({ assigned_to: undefined })}
            >
              My assigned warnings ×
            </button>
          )}
          {hasFilters ? (
            <button className="warning-clear" onClick={onClear}>
              Clear all
            </button>
          ) : (
            <span className="warning-muted">None applied</span>
          )}
        </div>
        <div className="warning-table-options">
          <label>
            Sort by
            <select
              aria-label="Sort warnings"
              value={`${params.sort}:${params.order}`}
              onChange={(event) => {
                const selected = SORTS.find(
                  (value) =>
                    `${value.sort}:${value.order}` === event.target.value,
                );
                if (selected)
                  onChange({ sort: selected.sort, order: selected.order });
              }}
            >
              {SORTS.map((value) => (
                <option
                  key={value.label}
                  value={`${value.sort}:${value.order}`}
                >
                  {value.label}
                </option>
              ))}
            </select>
          </label>
          <div
            className="warning-density"
            role="group"
            aria-label="Table density"
          >
            {[false, true].map((value) => (
              <button
                key={String(value)}
                aria-pressed={compact === value}
                onClick={() => onDensity(value)}
              >
                {value ? "Compact" : "Default"}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
