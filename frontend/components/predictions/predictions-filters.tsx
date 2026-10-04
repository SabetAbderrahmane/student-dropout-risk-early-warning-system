import type { CurrentModel, PredictionParams } from "@/types/prediction";
import { readable } from "@/lib/dashboard";
export const PREDICTION_INITIAL: PredictionParams = {
  page: 1,
  page_size: 25,
  sort: "predicted_at",
  order: "desc",
};
const SORTS: Array<{
  label: string;
  sort: PredictionParams["sort"];
  order: PredictionParams["order"];
}> = [
  { label: "Newest prediction", sort: "predicted_at", order: "desc" },
  { label: "Oldest prediction", sort: "predicted_at", order: "asc" },
  { label: "Highest probability", sort: "probability", order: "desc" },
  { label: "Lowest probability", sort: "probability", order: "asc" },
  { label: "Student ID", sort: "student_number", order: "asc" },
  { label: "Risk level", sort: "risk_level", order: "desc" },
  { label: "Model version", sort: "model_version", order: "asc" },
];
export function PredictionsFilters({
  params,
  model,
  search,
  onSearch,
  onChange,
  onClear,
  compact,
  onDensity,
}: {
  params: PredictionParams;
  model: CurrentModel | null;
  search: string;
  onSearch: (value: string) => void;
  onChange: (values: Partial<PredictionParams>) => void;
  onClear: () => void;
  compact: boolean;
  onDensity: (value: boolean) => void;
}) {
  const hasFilters =
    !!params.search || !!params.risk_level || !!params.model_version;
  return (
    <section
      className="warning-filters prediction-filters"
      aria-label="Prediction filters"
    >
      <div className="warning-filter-grid prediction-filter-grid">
        <label>
          <span>Search students</span>
          <input
            type="search"
            maxLength={200}
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search by student name or student ID"
          />
        </label>
        <label>
          <span>Risk level</span>
          <select
            aria-label="Risk level"
            value={params.risk_level ?? ""}
            onChange={(event) =>
              onChange({
                risk_level: (["HIGH", "MEDIUM", "LOW"] as const).find(
                  (value) => value === event.target.value,
                ),
              })
            }
          >
            <option value="">All risk levels</option>
            {["HIGH", "MEDIUM", "LOW"].map((value) => (
              <option key={value} value={value}>
                {readable(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Model version</span>
          <select
            aria-label="Model version"
            value={params.model_version ?? ""}
            onChange={(event) =>
              onChange({ model_version: event.target.value || undefined })
            }
          >
            <option value="">All model versions</option>
            {model && (
              <option value={model.version}>Current: {model.version}</option>
            )}
            {params.model_version &&
              params.model_version !== model?.version && (
                <option value={params.model_version}>
                  Selected: {params.model_version}
                </option>
              )}
          </select>
        </label>
      </div>
      <div className="warning-filter-meta">
        <div className="warning-chips">
          <span className="warning-label">Active filters</span>
          {params.search && (
            <button className="warning-chip" onClick={() => onSearch("")}>
              Search: {params.search} ×
            </button>
          )}
          {params.risk_level && (
            <button
              className="warning-chip"
              onClick={() => onChange({ risk_level: undefined })}
            >
              {readable(params.risk_level)} risk ×
            </button>
          )}
          {params.model_version && (
            <button
              className="warning-chip"
              onClick={() => onChange({ model_version: undefined })}
            >
              Model: {params.model_version} ×
            </button>
          )}
          {hasFilters ? (
            <button className="warning-clear" onClick={onClear}>
              Clear all
            </button>
          ) : (
            <span className="prediction-muted">None applied</span>
          )}
        </div>
        <div className="warning-table-options">
          <label>
            Sort by
            <select
              aria-label="Sort predictions"
              value={`${params.sort}:${params.order}`}
              onChange={(event) => {
                const value = SORTS.find(
                  (item) => `${item.sort}:${item.order}` === event.target.value,
                );
                if (value) onChange({ sort: value.sort, order: value.order });
              }}
            >
              {SORTS.map((item) => (
                <option key={item.label} value={`${item.sort}:${item.order}`}>
                  {item.label}
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
