import type { PageMetadata } from "@/types/staged-import";
export function StagedPagination({
  data,
  label,
  onPage,
  onSize,
  disabled = false,
}: {
  data: PageMetadata;
  label: string;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
  disabled?: boolean;
}) {
  return (
    <footer className="import-pagination">
      <span>
        <strong>{data.total.toLocaleString()}</strong> {label.toLowerCase()} ·
        Page {data.page} of {data.total_pages}
      </span>
      <div>
        <label>
          {label} per page
          <select
            aria-label={`${label} per page`}
            disabled={disabled}
            value={data.page_size}
            onChange={(event) => onSize(Number(event.target.value))}
          >
            {[25, 50, 100].map((size) => (
              <option key={size}>{size}</option>
            ))}
          </select>
        </label>
        <button
          className="dash-button"
          aria-label={`${label} previous page`}
          disabled={disabled || data.page <= 1}
          onClick={() => onPage(data.page - 1)}
        >
          Previous
        </button>
        <button
          className="dash-button"
          aria-label={`${label} next page`}
          disabled={
            disabled || !data.total_pages || data.page >= data.total_pages
          }
          onClick={() => onPage(data.page + 1)}
        >
          Next
        </button>
      </div>
    </footer>
  );
}
