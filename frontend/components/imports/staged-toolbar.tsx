import type { StagedRowParams } from "@/types/staged-import";
export function StagedToolbar({
  params,
  search,
  onSearch,
  onFilter,
  onClear,
  disabled,
}: {
  params: StagedRowParams;
  search: string;
  onSearch: (text: string) => void;
  onFilter: (values: Partial<StagedRowParams>) => void;
  onClear: () => void;
  disabled: boolean;
}) {
  return (
    <section className="warning-filters" aria-label="Review row filters">
      <div className="warning-filter-grid import-filter-grid">
        <label>
          <span>Search edited student values</span>
          <input
            type="search"
            maxLength={200}
            placeholder="Search student number or name"
            value={search}
            disabled={disabled}
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
        <label>
          <span>Validation</span>
          <select
            aria-label="Row validation"
            value={params.valid === undefined ? "all" : String(params.valid)}
            disabled={disabled}
            onChange={(event) =>
              onFilter({
                valid:
                  event.target.value === "all"
                    ? undefined
                    : event.target.value === "true",
              })
            }
          >
            <option value="all">All validation states</option>
            <option value="true">Valid rows</option>
            <option value="false">Invalid rows</option>
          </select>
        </label>
        <label>
          <span>Inclusion</span>
          <select
            aria-label="Row inclusion"
            value={
              params.included === undefined ? "all" : String(params.included)
            }
            disabled={disabled}
            onChange={(event) =>
              onFilter({
                included:
                  event.target.value === "all"
                    ? undefined
                    : event.target.value === "true",
              })
            }
          >
            <option value="all">All rows</option>
            <option value="true">Included rows</option>
            <option value="false">Excluded rows</option>
          </select>
        </label>
      </div>
      <div className="warning-filter-meta">
        <span className="import-muted">
          Sorted by physical CSV row number · Validation and inclusion filters
          combine
        </span>
        <button
          className="warning-clear"
          disabled={
            disabled ||
            !(
              params.search ||
              params.valid !== undefined ||
              params.included !== undefined
            )
          }
          onClick={onClear}
        >
          Clear row filters
        </button>
      </div>
    </section>
  );
}
