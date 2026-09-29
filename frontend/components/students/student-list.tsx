"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createStudent,
  fetchCurrentUser,
  fetchStudents,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import type { User } from "@/types/auth";
import type { StudentPage } from "@/types/student";

const EMPTY_PAGE: StudentPage = {
  items: [],
  page: 1,
  page_size: 25,
  total: 0,
  total_pages: 0,
};

export function StudentList() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [data, setData] = useState<StudentPage>(EMPTY_PAGE);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [studentNumber, setStudentNumber] = useState("");
  const [name, setName] = useState("");
  const [gender, setGender] = useState("");

  const load = useCallback(
    async (accessToken: string, targetPage: number, query: string) => {
      setLoading(true);
      setError("");
      try {
        setData(await fetchStudents(accessToken, targetPage, 25, query));
      } catch (caught) {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Unable to load students.",
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
        setUser(currentUser);
        return load(accessToken, page, search);
      })
      .catch(() => {
        clearAccessToken();
        router.replace("/login");
      });
  }, [load, page, router, search]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const student = await createStudent(token, {
        student_number: studentNumber,
        name,
        gender: gender || null,
      });
      router.push(`/students/${student.id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Unable to create student.",
      );
    }
  }

  const canEdit = user?.role === "ACADEMIC_ADMIN";

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <div>
          <div className="eyebrow">Student domain</div>
          <h1>Students</h1>
          <p className="muted">
            {user
              ? `${user.full_name} · ${user.role.replaceAll("_", " ")}`
              : "Loading account…"}
          </p>
        </div>
        <div className="header-actions">
          {user?.role !== "ACADEMIC_ADVISOR" ? (
            <Link className="secondary-button compact" href="/imports">
              CSV imports
            </Link>
          ) : null}
          {canEdit ? (
            <button
              className="primary-button compact"
              onClick={() => setShowCreate(!showCreate)}
            >
              {showCreate ? "Close form" : "Add student"}
            </button>
          ) : null}
          <button
            className="secondary-button compact"
            onClick={() => {
              clearAccessToken();
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </header>

      {showCreate && canEdit ? (
        <section className="panel">
          <h2>Create student</h2>
          <form className="form-grid" onSubmit={handleCreate}>
            <label>
              Student number
              <input
                value={studentNumber}
                onChange={(e) => setStudentNumber(e.target.value)}
                required
              />
            </label>
            <label>
              Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
            <label>
              Gender
              <input
                value={gender}
                onChange={(e) => setGender(e.target.value)}
              />
            </label>
            <button className="primary-button" type="submit">
              Create student
            </button>
          </form>
        </section>
      ) : null}

      <section className="panel">
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setSearch(searchInput);
          }}
        >
          <input
            aria-label="Search by student number or name"
            placeholder="Search by student number or name"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <button className="primary-button compact" type="submit">
            Search
          </button>
        </form>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        {loading ? <p className="muted">Loading students…</p> : null}
        {!loading && data.items.length === 0 ? (
          <p className="empty-state">No students found.</p>
        ) : null}
        {data.items.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student number</th>
                  <th>Name</th>
                  <th>Gender</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((student) => (
                  <tr key={student.id}>
                    <td>{student.student_number}</td>
                    <td>{student.name}</td>
                    <td>{student.gender ?? "—"}</td>
                    <td>
                      <Link href={`/students/${student.id}`}>View details</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <div className="pagination-row">
          <span>
            {data.total} total · Page {data.page} of{" "}
            {Math.max(data.total_pages, 1)}
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
              disabled={data.total_pages === 0 || page >= data.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
