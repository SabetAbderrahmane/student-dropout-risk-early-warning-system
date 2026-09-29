"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  deleteStudent,
  fetchAdmission,
  fetchCurrentUser,
  fetchFirstSemester,
  fetchStudent,
  saveAdmission,
  saveFirstSemester,
  updateStudent,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import type { User } from "@/types/auth";
import type {
  AdmissionInput,
  AdmissionRecord,
  FirstSemesterInput,
  FirstSemesterRecord,
  Student,
} from "@/types/student";

const EMPTY_ADMISSION: AdmissionInput = {
  admission_method: "",
  admission_grade: 0,
  previous_qualification: "",
  previous_qualification_grade: 0,
};

const EMPTY_SEMESTER: FirstSemesterInput = {
  credited_units: 0,
  enrolled_units: 0,
  evaluations: 0,
  approved_units: 0,
  average_grade: 0,
};

export function StudentDetail({ studentId }: { studentId: string }) {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [student, setStudent] = useState<Student | null>(null);
  const [admission, setAdmission] = useState<AdmissionRecord | null>(null);
  const [semester, setSemester] = useState<FirstSemesterRecord | null>(null);
  const [admissionForm, setAdmissionForm] = useState<AdmissionInput>(EMPTY_ADMISSION);
  const [semesterForm, setSemesterForm] = useState<FirstSemesterInput>(EMPTY_SEMESTER);
  const [studentNumber, setStudentNumber] = useState("");
  const [name, setName] = useState("");
  const [gender, setGender] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const accessToken = getAccessToken();
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    setToken(accessToken);

    async function load() {
      try {
        const [currentUser, studentData] = await Promise.all([
          fetchCurrentUser(accessToken as string),
          fetchStudent(accessToken as string, studentId),
        ]);
        setUser(currentUser);
        setStudent(studentData);
        setStudentNumber(studentData.student_number);
        setName(studentData.name);
        setGender(studentData.gender ?? "");

        try {
          const record = await fetchAdmission(accessToken as string, studentId);
          setAdmission(record);
          setAdmissionForm(record);
        } catch (caught) {
          if (!(caught instanceof ApiError && caught.code === "ADMISSION_RECORD_NOT_FOUND")) {
            throw caught;
          }
        }
        try {
          const record = await fetchFirstSemester(accessToken as string, studentId);
          setSemester(record);
          setSemesterForm(record);
        } catch (caught) {
          if (!(caught instanceof ApiError && caught.code === "SEMESTER_RECORD_NOT_FOUND")) {
            throw caught;
          }
        }
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
          return;
        }
        setError(caught instanceof ApiError ? caught.message : "Unable to load student details.");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [router, studentId]);

  function beginRequest() {
    setError("");
    setMessage("");
  }

  async function handleStudentUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    beginRequest();
    try {
      const updated = await updateStudent(token, studentId, {
        student_number: studentNumber,
        name,
        gender: gender || null,
      });
      setStudent(updated);
      setMessage("Student information saved.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to update student.");
    }
  }

  async function handleAdmission(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    beginRequest();
    try {
      const saved = await saveAdmission(token, studentId, admissionForm);
      setAdmission(saved);
      setAdmissionForm(saved);
      setMessage("Admission record saved.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to save admission record.");
    }
  }

  async function handleSemester(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    beginRequest();
    try {
      const saved = await saveFirstSemester(token, studentId, semesterForm);
      setSemester(saved);
      setSemesterForm(saved);
      setMessage("First-semester record saved.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to save semester record.");
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this student and their related academic records?")) return;
    beginRequest();
    try {
      await deleteStudent(token, studentId);
      router.push("/students");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to delete student.");
    }
  }

  if (loading) return <main className="workspace-shell"><p className="muted">Loading student…</p></main>;
  if (!student) return <main className="workspace-shell"><Link href="/students">← Students</Link><p className="form-error">{error || "Student unavailable."}</p></main>;

  const canEdit = user?.role === "ACADEMIC_ADMIN";

  return (
    <main className="workspace-shell">
      <Link className="back-link" href="/students">← Students</Link>
      <header className="workspace-header">
        <div>
          <div className="eyebrow">{student.student_number}</div>
          <h1>{student.name}</h1>
          <p className="muted">{canEdit ? "Academic administrator · Editable" : "Read-only academic view"}</p>
        </div>
        {canEdit ? <button className="danger-button" onClick={handleDelete}>Delete student</button> : null}
      </header>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {message ? <p className="success-message" role="status">{message}</p> : null}

      <section className="panel">
        <h2>Student information</h2>
        {canEdit ? (
          <form className="form-grid" onSubmit={handleStudentUpdate}>
            <TextField label="Student number" value={studentNumber} setValue={setStudentNumber} required />
            <TextField label="Name" value={name} setValue={setName} required />
            <TextField label="Gender" value={gender} setValue={setGender} />
            <button className="primary-button" type="submit">Save student</button>
          </form>
        ) : (
          <dl className="detail-grid">
            <Detail label="Student number" value={student.student_number} />
            <Detail label="Name" value={student.name} />
            <Detail label="Gender" value={student.gender ?? "Not recorded"} />
          </dl>
        )}
      </section>

      <section className="panel">
        <h2>Admission record</h2>
        {canEdit ? (
          <form className="form-grid" onSubmit={handleAdmission}>
            <TextField label="Admission method" value={admissionForm.admission_method} setValue={(value) => setAdmissionForm({ ...admissionForm, admission_method: value })} required />
            <NumberField label="Admission grade" value={admissionForm.admission_grade} setValue={(value) => setAdmissionForm({ ...admissionForm, admission_grade: value })} />
            <TextField label="Previous qualification" value={admissionForm.previous_qualification} setValue={(value) => setAdmissionForm({ ...admissionForm, previous_qualification: value })} required />
            <NumberField label="Previous qualification grade" value={admissionForm.previous_qualification_grade} setValue={(value) => setAdmissionForm({ ...admissionForm, previous_qualification_grade: value })} />
            <button className="primary-button" type="submit">Save admission</button>
          </form>
        ) : admission ? (
          <dl className="detail-grid">
            <Detail label="Admission method" value={admission.admission_method} />
            <Detail label="Admission grade" value={String(admission.admission_grade)} />
            <Detail label="Previous qualification" value={admission.previous_qualification} />
            <Detail label="Previous grade" value={String(admission.previous_qualification_grade)} />
          </dl>
        ) : <p className="empty-state">No admission record.</p>}
      </section>

      <section className="panel">
        <h2>First-semester record</h2>
        {canEdit ? (
          <form className="form-grid" onSubmit={handleSemester}>
            <NumberField label="Credited units" value={semesterForm.credited_units} setValue={(value) => setSemesterForm({ ...semesterForm, credited_units: value })} integer />
            <NumberField label="Enrolled units" value={semesterForm.enrolled_units} setValue={(value) => setSemesterForm({ ...semesterForm, enrolled_units: value })} integer />
            <NumberField label="Evaluations" value={semesterForm.evaluations} setValue={(value) => setSemesterForm({ ...semesterForm, evaluations: value })} integer />
            <NumberField label="Approved units" value={semesterForm.approved_units} setValue={(value) => setSemesterForm({ ...semesterForm, approved_units: value })} integer />
            <NumberField label="Average grade" value={semesterForm.average_grade} setValue={(value) => setSemesterForm({ ...semesterForm, average_grade: value })} />
            <button className="primary-button" type="submit">Save semester record</button>
          </form>
        ) : semester ? (
          <dl className="detail-grid">
            <Detail label="Credited units" value={String(semester.credited_units)} />
            <Detail label="Enrolled units" value={String(semester.enrolled_units)} />
            <Detail label="Evaluations" value={String(semester.evaluations)} />
            <Detail label="Approved units" value={String(semester.approved_units)} />
            <Detail label="Average grade" value={String(semester.average_grade)} />
          </dl>
        ) : <p className="empty-state">No first-semester record.</p>}
      </section>
    </main>
  );
}

function TextField({ label, value, setValue, required = false }: { label: string; value: string; setValue: (value: string) => void; required?: boolean }) {
  return <label>{label}<input value={value} onChange={(event) => setValue(event.target.value)} required={required} /></label>;
}

function NumberField({ label, value, setValue, integer = false }: { label: string; value: number; setValue: (value: number) => void; integer?: boolean }) {
  return <label>{label}<input type="number" min="0" step={integer ? "1" : "0.01"} value={value} onChange={(event) => setValue(Number(event.target.value))} required /></label>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}
