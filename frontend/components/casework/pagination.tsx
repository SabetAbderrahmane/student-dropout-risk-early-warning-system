import type { CaseworkPage } from "@/types/casework";
export function CaseworkPagination({
  data,
  noun,
  onPage,
  onSize,
}: {
  data: CaseworkPage<unknown>;
  noun: string;
  onPage: (page: number) => void;
  onSize?: (size: number) => void;
}) {
  const first = data.items.length ? (data.page - 1) * data.page_size + 1 : 0;
  return (
    <footer className="warning-pagination">
      <span>
        {first}–{first ? first + data.items.length - 1 : 0} of{" "}
        <strong>{data.total.toLocaleString()}</strong> {noun}
      </span>
      <div>
        {onSize && (
          <label>
            Rows per page
            <select
              value={data.page_size}
              onChange={(e) => onSize(Number(e.target.value))}
            >
              {[10, 25, 50, 100].map((size) => (
                <option key={size}>{size}</option>
              ))}
            </select>
          </label>
        )}
        <span>
          Page {data.total_pages ? data.page : 0} of {data.total_pages}
        </span>
        <button
          className="dash-button"
          disabled={data.page <= 1}
          onClick={() => onPage(data.page - 1)}
        >
          Previous
        </button>
        <button
          className="dash-button"
          disabled={data.page >= data.total_pages}
          onClick={() => onPage(data.page + 1)}
        >
          Next
        </button>
      </div>
    </footer>
  );
}
