"use client";

import Link from "next/link";
import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  downloadImportTemplate,
  fetchCurrentUser,
  fetchImportErrors,
  fetchImports,
  uploadStudentCsv,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import type { User } from "@/types/auth";
import type { ImportErrorPage, ImportJob, ImportJobPage } from "@/types/import";

const EMPTY_JOBS: ImportJobPage = {
  items: [],
  page: 1,
  page_size: 25,
  total: 0,
  total_pages: 0,
};
const EMPTY_ERRORS: ImportErrorPage = {
  items: [],
  page: 1,
  page_size: 25,
  total: 0,
  total_pages: 0,
};

export function ImportManager() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [jobs, setJobs] = useState(EMPTY_JOBS);
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportJob | null>(null);
  const [selected, setSelected] = useState<ImportJob | null>(null);
  const [errors, setErrors] = useState(EMPTY_ERRORS);
  const [errorPage, setErrorPage] = useState(1);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const loadJobs = useCallback(
    async (accessToken: string, targetPage: number) => {
      setLoading(true);
      try {
        setJobs(await fetchImports(accessToken, targetPage, 25));
      } catch (caught) {
        setMessage(
          caught instanceof ApiError
            ? caught.message
            : "Unable to load imports.",
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const accessToken = getAccessToken();
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    setToken(accessToken);
    fetchCurrentUser(accessToken)
      .then((currentUser) => {
        if (currentUser.role === "ACADEMIC_ADVISOR") {
          router.replace("/students");
          return;
        }
        setUser(currentUser);
        return loadJobs(accessToken, page);
      })
      .catch(() => {
        clearAccessToken();
        router.replace("/login");
      });
  }, [loadJobs, page, router]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setMessage("");
    try {
      const imported = await uploadStudentCsv(token, file);
      setResult(imported);
      setFile(null);
      setPage(1);
      await loadJobs(token, 1);
    } catch (caught) {
      setMessage(
        caught instanceof ApiError ? caught.message : "Unable to import CSV.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function viewErrors(job: ImportJob, targetPage = 1) {
    setSelected(job);
    setErrorPage(targetPage);
    setMessage("");
    try {
      setErrors(await fetchImportErrors(token, job.id, targetPage, 25));
    } catch (caught) {
      setMessage(
        caught instanceof ApiError ? caught.message : "Unable to load errors.",
      );
    }
  }

  const canUpload = user?.role === "ACADEMIC_ADMIN";

  return (
    <main className="workspace-shell">
      <Link href="/students">← Back to students</Link>
      <header className="workspace-header">
        <div>
          <div className="eyebrow">Data onboarding</div>
          <h1>CSV imports</h1>
          <p className="muted">
            Download the 34-column template and review row-level validation.
          </p>
        </div>
        <button
          className="secondary-button compact"
          onClick={() =>
            downloadImportTemplate(token).catch(() =>
              setMessage("Unable to download template."),
            )
          }
        >
          Download template
        </button>
      </header>

      {canUpload ? (
        <section className="panel">
          <h2>Import students</h2>
          <form className="upload-row" onSubmit={handleUpload}>
            <input
              aria-label="CSV file"
              accept=".csv,text/csv"
              type="file"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setFile(event.target.files?.[0] ?? null)
              }
              required
            />
            <button
              className="primary-button compact"
              disabled={!file || uploading}
              type="submit"
            >
              {uploading ? "Importing…" : "Upload CSV"}
            </button>
          </form>
        </section>
      ) : null}

      {message ? (
        <p className="form-error" role="alert">
          {message}
        </p>
      ) : null}
      {result ? (
        <section className="panel success-message">
          <strong>Import complete.</strong> {result.valid_rows} valid and{" "}
          {result.invalid_rows} invalid out of {result.total_rows} rows.
        </section>
      ) : null}

      <section className="panel">
        <h2>Import history</h2>
        {loading ? <p className="muted">Loading imports…</p> : null}
        {!loading && jobs.items.length === 0 ? (
          <p className="empty-state">No imports yet.</p>
        ) : null}
        {jobs.items.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Status</th>
                  <th>Rows</th>
                  <th>Valid</th>
                  <th>Invalid</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobs.items.map((job) => (
                  <tr key={job.id}>
                    <td>{job.filename}</td>
                    <td>{job.status}</td>
                    <td>{job.total_rows}</td>
                    <td>{job.valid_rows}</td>
                    <td>{job.invalid_rows}</td>
                    <td>
                      <button
                        className="secondary-button compact"
                        onClick={() => viewErrors(job)}
                      >
                        View errors
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <div className="pagination-row">
          <span>
            {jobs.total} total · Page {jobs.page} of{" "}
            {Math.max(jobs.total_pages, 1)}
          </span>
          <div>
            <button
              className="secondary-button compact"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <button
              className="secondary-button compact"
              disabled={!jobs.total_pages || page >= jobs.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {selected ? (
        <section className="panel">
          <h2>Validation errors · {selected.filename}</h2>
          {errors.items.length === 0 ? (
            <p className="empty-state">This import has no validation errors.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Field</th>
                    <th>Code</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {errors.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.row_number}</td>
                      <td>{item.field_name ?? "—"}</td>
                      <td>{item.error_code}</td>
                      <td>{item.error_message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination-row">
            <span>
              {errors.total} errors · Page {errors.page} of{" "}
              {Math.max(errors.total_pages, 1)}
            </span>
            <div>
              <button
                className="secondary-button compact"
                disabled={errorPage <= 1}
                onClick={() => viewErrors(selected, errorPage - 1)}
              >
                Previous
              </button>
              <button
                className="secondary-button compact"
                disabled={
                  !errors.total_pages || errorPage >= errors.total_pages
                }
                onClick={() => viewErrors(selected, errorPage + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}
