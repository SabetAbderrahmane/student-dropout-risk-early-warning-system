"use client";

import { AssessmentStatus } from "@/components/predictions/assessment-status";
import { stageLabel } from "@/types/outcome";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, fetchCurrentUser, fetchStudentRegistry } from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { hasRole } from "@/lib/permissions";
import { percent, readable, timestamp } from "@/lib/dashboard";
import type { User } from "@/types/auth";
import type {
  RegistryPage,
  RegistryRow,
  RegistrySort,
  StudentRegistryParams,
} from "@/types/registry";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { Icon } from "@/components/dashboard/icon";
import { CreateStudentModal } from "./create-student-modal";
import { StudentProfileDrawer } from "./student-profile-drawer";

const INITIAL: StudentRegistryParams = {
  page: 1,
  page_size: 25,
  sort: "student_number",
  order: "asc",
};
const FILTERS = [
  {key: "assessment_state", label: "Assessment state", options: ["CURRENT", "REASSESSMENT_REQUIRED", "NOT_ASSESSED"]},
  {key: "prediction_stage", label: "Prediction stage", options: ["ENROLLMENT", "FIRST_SEMESTER"]},
  {key: "stage_readiness", label: "Selected stage inputs", options: ["READY", "NOT_READY"]},
  {
    key: "current_risk",
    label: "Current risk",
    options: ["LOW", "MEDIUM", "HIGH", "NONE"],
  },
  {
    key: "warning_state",
    label: "Warning state",
    options: ["PENDING_REVIEW", "CONFIRMED", "DISMISSED", "NONE"],
  },
  {
    key: "intervention_state",
    label: "Intervention state",
    options: [
      "PLANNED",
      "IN_PROGRESS",
      "ACTION_REQUIRED",
      "COMPLETED",
      "CANCELLED",
    ],
  },
  {
    key: "prediction_readiness",
    label: "Input readiness",
    options: ["READY", "NOT_READY"],
  },
] as const;

export function RegistryBadge({ value }: { value: string }) {
  return (
    <span className={`registry-badge state-${value.toLowerCase()}`}>
      {readable(value)}
    </span>
  );
}

export function StudentList() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [params, setParams] = useState<StudentRegistryParams>(INITIAL);
  const [searchInput, setSearchInput] = useState("");
  const [data, setData] = useState<RegistryPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [compact, setCompact] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState<RegistryRow | null>(null);
  function signOut() {
    clearAccessToken();
    router.replace("/login");
  }

  useEffect(() => {
    let active = true;
    const accessToken = getAccessToken();
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    fetchCurrentUser(accessToken)
      .then((currentUser) => {
        if (active) {
          setUser(currentUser);
          setToken(accessToken);
        }
      })
      .catch((caught: unknown) => {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        } else {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load your account.",
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [router, retry]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    fetchStudentRegistry(token, params, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        } else
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load the student registry.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, params, retry, router]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setParams((current) =>
        current.search === (searchInput.trim() || undefined)
          ? current
          : { ...current, search: searchInput.trim() || undefined, page: 1 },
      );
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  function sortBy(sort: RegistrySort) {
    setParams((current) => ({
      ...current,
      page: 1,
      sort,
      order: current.sort === sort && current.order === "asc" ? "desc" : "asc",
    }));
  }
  function sortHeading(label: string, sort: RegistrySort) {
    return (
      <th
        scope="col"
        aria-sort={
          params.sort === sort
            ? params.order === "asc"
              ? "ascending"
              : "descending"
            : "none"
        }
      >
        <button onClick={() => sortBy(sort)}>
          {label}
          <span aria-hidden="true">
            {params.sort === sort ? (params.order === "asc" ? "↑" : "↓") : "↕"}
          </span>
        </button>
      </th>
    );
  }
  const activeFilters = FILTERS.filter((filter) => params[filter.key]);
  const hasFilters = !!params.search || activeFilters.length > 0;
  const canCreate = !!user && hasRole(user.role, ["ACADEMIC_ADMIN"]);
  const canImport =
    !!user && hasRole(user.role, ["SYSTEM_ADMIN", "ACADEMIC_ADMIN"]);
  const first =
    data && data.total > 0 && data.items.length > 0
      ? (data.page - 1) * data.page_size + 1
      : 0;

  return (
    <div className="dash-root registry-root">
      <a className="dash-skip-link" href="#registry-main">
        Skip to student registry
      </a>
      <AppSidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="dash-workspace">
        <AppHeader
          title="Students / System Registry"
          user={user}
          menuOpen={menuOpen}
          onMenu={() => setMenuOpen((value) => !value)}
          onSignOut={signOut}
        />
        <main id="registry-main" className="dash-main">
          <div className="dash-title-row">
            <div>
              <p className="dash-eyebrow">
                <Icon name="students" /> Student information workspace
              </p>
              <h1>
                Students{" "}
                <span className="registry-title-note">/ System Registry</span>
              </h1>
              <p className="dash-description">
                Explore academic records, assess risk, and coordinate student
                support.
              </p>
            </div>
            <div className="dash-page-actions">
              <button
                className="dash-button"
                disabled={loading}
                onClick={() => setRetry((value) => value + 1)}
              >
                <Icon name="refresh" />
                Refresh
              </button>
              {canImport && (
                <Link className="dash-button" href="/imports">
                  <Icon name="import" />
                  Import CSV
                </Link>
              )}
              {canCreate && (
                <button
                  className="dash-button dash-button-primary"
                  onClick={() => setShowCreate(true)}
                >
                  + Add student
                </button>
              )}
            </div>
          </div>
          <section className="registry-toolbar" aria-label="Registry filters">
            <div className="registry-filter-grid">
              <label className="registry-search">
                <span>Search students</span>
                <input
                  type="search"
                  maxLength={200}
                  placeholder="Search by student name or student ID"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                />
              </label>
              {FILTERS.map((filter) => (
                <label key={filter.key}>
                  <span>{filter.label}</span>
                  <select
                    aria-label={filter.label}
                    value={params[filter.key] ?? ""}
                    disabled={filter.key === "stage_readiness" && !params.prediction_stage}
                    onChange={(event) => {
                      const value = filter.options.find(
                        (option) => option === event.target.value,
                      );
                      setParams((current) => ({
                        ...current,
                        page: 1,
                        [filter.key]: value,
                        ...(filter.key === "prediction_stage" && !value ? { stage_readiness: undefined } : {}),
                      }));
                    }}
                  >
                    <option value="">All {filter.label.toLowerCase()}</option>
                    {filter.options.map((value) => (
                      <option key={value} value={value}>
                        {readable(value)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className="registry-filter-meta">
              <div className="registry-chips">
                <span className="registry-label">Active filters</span>
                {params.search && (
                  <button
                    className="registry-chip"
                    onClick={() => {
                      setSearchInput("");
                      setParams((current) => ({
                        ...current,
                        page: 1,
                        search: undefined,
                      }));
                    }}
                  >
                    Search: {params.search} ×
                  </button>
                )}
                {activeFilters.map((filter) => (
                  <button
                    key={filter.key}
                    className="registry-chip"
                    aria-label={`Remove ${filter.label} filter`}
                    onClick={() =>
                      setParams((current) => ({
                        ...current,
                        page: 1,
                        [filter.key]: undefined,
                      }))
                    }
                  >
                    {filter.label}: {readable(params[filter.key]!)} ×
                  </button>
                ))}
                {hasFilters ? (
                  <button
                    className="registry-clear"
                    onClick={() => {
                      setSearchInput("");
                      setParams((current) => ({
                        ...INITIAL,
                        page_size: current.page_size,
                        sort: current.sort,
                        order: current.order,
                      }));
                    }}
                  >
                    Clear all
                  </button>
                ) : (
                  <span className="registry-muted">None applied</span>
                )}
              </div>
              <div
                className="registry-density"
                role="group"
                aria-label="Table density"
              >
                {[false, true].map((value) => (
                  <button
                    key={String(value)}
                    aria-pressed={compact === value}
                    onClick={() => setCompact(value)}
                  >
                    {value ? "Compact" : "Default"}
                  </button>
                ))}
              </div>
            </div>
          </section>
          <section
            className={`registry-table-card ${compact ? "is-compact" : ""}`}
            aria-label="Student registry"
            aria-busy={loading}
          >
            <div className="registry-table-heading">
              <h2>
                Student records{" "}
                {data && (
                  <span className="registry-count">
                    {data.total.toLocaleString()}
                  </span>
                )}
              </h2>
              <label className="registry-sort">
                Sort records{" "}
                <select
                  aria-label="Sort records"
                  value={params.sort}
                  onChange={(event) => {
                    const sort = (
                      [
                        "student_number",
                        "name",
                        "risk_probability",
                        "updated_at",
                      ] as const
                    ).find((value) => value === event.target.value);
                    if (sort)
                      setParams((current) => ({ ...current, page: 1, sort }));
                  }}
                >
                  <option value="student_number">Student ID</option>
                  <option value="name">Student name</option>
                  <option value="risk_probability">Current risk</option>
                  <option value="updated_at">Record updated</option>
                </select>
                <button
                  className="registry-order"
                  aria-label={`Sort ${params.order === "asc" ? "descending" : "ascending"}`}
                  onClick={() =>
                    setParams((current) => ({
                      ...current,
                      page: 1,
                      order: current.order === "asc" ? "desc" : "asc",
                    }))
                  }
                >
                  {params.order === "asc" ? "↑ Asc" : "↓ Desc"}
                </button>
              </label>
            </div>
            {error && (
              <div className="registry-status" role="alert">
                <strong>Unable to load the registry</strong>
                <p>{error}</p>
                <button
                  className="dash-button"
                  onClick={() => setRetry((value) => value + 1)}
                >
                  Retry
                </button>
              </div>
            )}
            {loading && (
              <div className="registry-status" role="status">
                <Icon name="refresh" />
                <p>Loading student records…</p>
              </div>
            )}
            {!loading && !error && data?.items.length === 0 && (
              <div className="registry-status">
                <Icon name="students" />
                <strong>No students found</strong>
                <p>
                  {hasFilters
                    ? "Try adjusting your search or clearing the filters."
                    : "Add a student or import academic records to get started."}
                </p>
                {hasFilters && (
                  <button
                    className="dash-button"
                    onClick={() => {
                      setSearchInput("");
                      setParams(INITIAL);
                    }}
                  >
                    Clear filters
                  </button>
                )}
                {data.total > 0 && (
                  <button
                    className="dash-button"
                    onClick={() =>
                      setParams((current) => ({ ...current, page: 1 }))
                    }
                  >
                    Return to first page
                  </button>
                )}
              </div>
            )}
            {!loading && !error && !!data?.items.length && (
              <div
                className="registry-table-scroll"
                tabIndex={0}
                role="region"
                aria-label="Student records, scroll for more columns"
              >
                <table className="registry-table">
                  <thead>
                    <tr>
                      {sortHeading("Student ID", "student_number")}
                      {sortHeading("Student name", "name")}
                      <th scope="col">Course / Admission</th>
                      <th scope="col">Semester 1</th>
                      <th scope="col">Readiness</th>
                      {sortHeading("Current risk", "risk_probability")}
                      <th scope="col">Warning</th>
                      <th scope="col">Intervention</th>
                      <th scope="col">Case owner</th>
                      <th scope="col">Last activity</th>
                      <th scope="col">Profile</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <tr key={row.student_id}>
                        <td className="registry-mono">{row.student_number}</td>
                        <td>
                          <button
                            className="registry-student"
                            onClick={() => setSelected(row)}
                          >
                            <span
                              className="registry-avatar"
                              aria-hidden="true"
                            >
                              {row.name
                                .split(/\s+/)
                                .filter(Boolean)
                                .slice(0, 2)
                                .map((word) => word[0])
                                .join("")}
                            </span>
                            <strong>{row.name}</strong>
                          </button>
                        </td>
                        <td>
                          <strong>{row.course?.label ?? "Not recorded"}</strong>
                          <small>
                            {row.admission
                              ? `${row.admission.method} · ${row.admission.admission_grade.toFixed(1)}`
                              : "No admission record"}
                          </small>
                        </td>
                        <td>
                          {row.semester_one ? (
                            <>
                              <strong>
                                {row.semester_one.average_grade.toFixed(1)}{" "}
                                <span className="registry-muted">
                                  avg. grade
                                </span>
                              </strong>
                              <small>
                                {row.semester_one.approved_units}/
                                {row.semester_one.enrolled_units} units approved
                                {row.semester_one.approval_rate !== null
                                  ? ` · ${percent(row.semester_one.approval_rate)}`
                                  : ""}
                              </small>
                            </>
                          ) : (
                            <span className="registry-muted">Not recorded</span>
                          )}
                        </td>
                        <td>
                          <RegistryBadge value={row.prediction_readiness} />
                          <small>Enrollment: {row.enrollment_ready ? "Ready" : "Not ready"} · Semester: {row.first_semester_ready ? "Ready" : "Not ready"}</small>
                        </td>
                        <td>
                          <AssessmentStatus assessment={row} compact />
                          {row.operational_prediction ? (
                            <>
                              <div className="registry-risk">
                                <strong>
                                  {percent(row.operational_prediction.probability)}
                                </strong>
                                <RegistryBadge
                                  value={row.operational_prediction.risk_level}
                                />
                              </div>
                              <meter
                                min={0}
                                max={1}
                                value={row.operational_prediction.probability}
                                aria-label={`${row.name} risk probability`}
                              />
                              <small>{stageLabel(row.operational_prediction.prediction_stage)} · {row.operational_prediction.model_target_type === "BINARY_DROPOUT" ? "Legacy binary" : "Three-class outcome"}</small>
                            </>
                          ) : (
                            <span className="registry-muted">No current prediction</span>
                          )}
                        </td>
                        <td>
                          <RegistryBadge value={row.warning?.state ?? "NONE"} />
                          {row.warning && (
                            <small>{readable(row.warning.priority)}</small>
                          )}
                        </td>
                        <td>
                          {row.intervention ? (
                            <RegistryBadge value={row.intervention.status} />
                          ) : (
                            <span className="registry-muted">None</span>
                          )}
                        </td>
                        <td>
                          {row.case_owner?.full_name ?? (
                            <span className="registry-muted">Unassigned</span>
                          )}
                        </td>
                        <td>
                          <small>{timestamp(row.last_activity_at)}</small>
                        </td>
                        <td>
                          <button
                            className="registry-profile-button"
                            onClick={() => setSelected(row)}
                            aria-label={`View profile for ${row.name}`}
                          >
                            View profile <span aria-hidden="true">↗</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {data && !loading && !error && (
              <div className="registry-pagination">
                <span>
                  {first.toLocaleString()}–
                  {(first ? first + data.items.length - 1 : 0).toLocaleString()}{" "}
                  of <strong>{data.total.toLocaleString()}</strong> students
                </span>
                <div>
                  <label>
                    Rows per page{" "}
                    <select
                      value={data.page_size}
                      onChange={(event) => {
                        const size = Number(event.target.value);
                        if (size === 25 || size === 50 || size === 100)
                          setParams((current) => ({
                            ...current,
                            page: 1,
                            page_size: size,
                          }));
                      }}
                    >
                      {[25, 50, 100].map((value) => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                  <span>
                    Page {data.page} of {data.total_pages}
                  </span>
                  <button
                    className="dash-button"
                    disabled={data.page <= 1}
                    onClick={() =>
                      setParams((current) => ({
                        ...current,
                        page: data.page - 1,
                      }))
                    }
                  >
                    Previous
                  </button>
                  <button
                    className="dash-button"
                    disabled={data.page >= data.total_pages}
                    onClick={() =>
                      setParams((current) => ({
                        ...current,
                        page: data.page + 1,
                      }))
                    }
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </section>
          <p className="registry-footnote">
            <Icon name="shield" /> Risk estimates inform support decisions.
            Academic staff make the final judgment.
          </p>
        </main>
      </div>
      {showCreate && canCreate && (
        <CreateStudentModal
          token={token}
          onClose={() => setShowCreate(false)}
          onUnauthorized={signOut}
          onCreated={(id) => router.push(`/students/${encodeURIComponent(id)}`)}
        />
      )}
      {selected && (
        <StudentProfileDrawer
          token={token}
          student={selected}
          onClose={() => setSelected(null)}
          onUnauthorized={signOut}
        />
      )}
    </div>
  );
}
