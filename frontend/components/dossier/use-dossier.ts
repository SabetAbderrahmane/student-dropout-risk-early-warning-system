"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, fetchCurrentUser, fetchStudentProfile } from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import type { User } from "@/types/auth";
import type { StudentProfile } from "@/types/registry";

export function dossierError(error: unknown): string {
  if (!(error instanceof ApiError))
    return error instanceof Error
      ? error.message
      : "Unable to complete this request.";
  const prefix =
    error.status === 403
      ? "Permission denied. "
      : error.status === 404
        ? "This record is unavailable. "
        : "";
  const details = Array.isArray(error.details)
    ? error.details.flatMap((item: unknown) =>
        item &&
        typeof item === "object" &&
        "message" in item &&
        typeof item.message === "string"
          ? [item.message]
          : [],
      )
    : [];
  return `${prefix}${error.message}${details.length ? " " + details.join(" ") : ""}`;
}
export function useDossier(studentId: string) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [writeDenied, setWriteDenied] = useState(false);
  const [revision, setRevision] = useState(0);
  const [recoveryRevision, setRecoveryRevision] = useState(0);
  const lock = useRef(false);
  const identity = useRef(studentId);
  identity.current = studentId;
  const signOut = () => {
    clearAccessToken();
    router.replace("/login");
  };
  function report(caught: unknown) {
    if (caught instanceof ApiError && caught.status === 401) signOut();
    else {
      if (caught instanceof ApiError && caught.status === 403)
        setWriteDenied(true);
      setError(dossierError(caught));
    }
  }
  useEffect(() => {
    const accessToken = getAccessToken();
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setProfile(null);
    setError("");
    setNotice("");
    setUser(null);
    setWriteDenied(false);
    void fetchCurrentUser(accessToken)
      .then(async (current) => {
        if (controller.signal.aborted) return;
        setUser(current);
        setToken(accessToken);
        const data = await fetchStudentProfile(
          accessToken,
          studentId,
          controller.signal,
        );
        if (!controller.signal.aborted) setProfile(data);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) report(caught);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [studentId, router, revision]);
  async function reload() {
    const id = studentId;
    try {
      const data = await fetchStudentProfile(token, id);
      if (identity.current === id) setProfile(data);
      return true;
    } catch (caught) {
      if (identity.current === id) {
        setProfile(null);
        report(caught);
      }
      return false;
    }
  }
  async function mutate(
    work: () => Promise<unknown>,
    success = "Saved. The dossier has been refreshed.",
  ): Promise<string | null> {
    if (lock.current) return "Another operation is in progress.";
    if (writeDenied || !user || user.role === "SYSTEM_ADMIN")
      return "Your account has read-only access.";
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      const refreshed = await reload();
      if (refreshed) setNotice(success);
      else
        setNotice(
          "Saved, but the updated dossier could not be loaded. Refresh to review the latest records.",
        );
      return null;
    } catch (caught) {
      report(caught);
      if (
        caught instanceof ApiError &&
        [403, 404, 409].includes(caught.status)
      ) {
        await reload();
        setRecoveryRevision((value) => value + 1);
      }
      return dossierError(caught);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return {
    user,
    token,
    profile,
    loading,
    error,
    notice,
    busy,
    report,
    signOut,
    mutate,
    recoveryRevision,
    refresh: () => {
      if (!lock.current) setRevision((r) => r + 1);
    },
    canEdit:
      !writeDenied && !loading && !!profile && user?.role === "ACADEMIC_ADMIN",
    canCase:
      !writeDenied &&
      !loading &&
      !!profile &&
      user?.role !== "SYSTEM_ADMIN" &&
      !!user,
  };
}
