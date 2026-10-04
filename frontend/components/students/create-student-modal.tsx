"use client";
import { useState, type FormEvent } from "react";
import { ApiError, createStudent } from "@/lib/api";
import { ActionModal } from "@/components/dashboard/action-modal";

export function CreateStudentModal({
  token,
  onClose,
  onCreated,
  onUnauthorized,
}: {
  token: string;
  onClose: () => void;
  onCreated: (id: string) => void;
  onUnauthorized: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const studentNumber = String(form.get("student_number") ?? "").trim();
    const name = String(form.get("name") ?? "").trim();
    if (!studentNumber || !name) {
      setError("Enter a student ID and name.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const student = await createStudent(token, {
        student_number: studentNumber,
        name,
        gender: String(form.get("gender") ?? "").trim() || null,
      });
      onCreated(student.id);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) onUnauthorized();
      else
        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to create student.",
        );
    } finally {
      setBusy(false);
    }
  }
  return (
    <ActionModal title="Add student" busy={busy} onClose={onClose}>
      <p className="registry-muted">
        Create the student record, then add admission and semester details.
      </p>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <label>
            <span>Student ID</span>
            <input name="student_number" maxLength={50} required />
          </label>
          <label>
            <span>Full name</span>
            <input name="name" maxLength={200} required />
          </label>
          <label>
            <span>Gender (optional)</span>
            <input name="gender" maxLength={30} />
          </label>
        </fieldset>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="dash-modal-actions">
          <button
            className="dash-button"
            type="button"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="dash-button dash-button-primary"
            disabled={busy}
            type="submit"
          >
            {busy ? "Creating…" : "Create student"}
          </button>
        </div>
      </form>
    </ActionModal>
  );
}
