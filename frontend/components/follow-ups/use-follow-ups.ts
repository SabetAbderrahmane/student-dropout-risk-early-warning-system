"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, fetchCurrentUser, fetchFollowUps } from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { followUpFailure, type FollowUpMutation } from "@/lib/follow-ups";
import type { User } from "@/types/auth";
import type { FollowUpParams } from "@/types/casework";
import { useFollowUpResource } from "./use-follow-up-resource";

export const FOLLOW_UP_INITIAL: FollowUpParams = {
  page: 1,
  page_size: 10,
  sort: "scheduled_for",
  order: "asc",
};
export function useFollowUps() {
  const router = useRouter();
  const query = useSearchParams();
  const studentContext = query.get("student_id") || undefined;
  const interventionContext = query.get("intervention_id") || undefined;
  const requestedId = query.get("follow_up_id");
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [authRetry, setAuthRetry] = useState(0);
  const [params, setParams] = useState<FollowUpParams>({
    ...FOLLOW_UP_INITIAL,
    student_id: studentContext,
    intervention_id: interventionContext,
  });
  const [selectedId, setSelectedId] = useState<string | null>(requestedId);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [mutationError, setMutationError] = useState("");
  const lock = useRef(false);
  const signOut = useCallback(() => {
    clearAccessToken();
    router.replace("/login");
  }, [router]);
  const report = useCallback(
    (caught: unknown) => {
      if (caught instanceof ApiError && caught.status === 401) signOut();
      return followUpFailure(caught).message;
    },
    [signOut],
  );
  useEffect(() => {
    const access = getAccessToken();
    let active = true;
    if (!access) {
      router.replace("/login");
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    fetchCurrentUser(access)
      .then((current) => {
        if (active) {
          setUser(current);
          setToken(access);
        }
      })
      .catch((caught) => {
        if (active) setAuthError(report(caught));
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router, report, authRetry]);
  useEffect(() => {
    setParams((current) => ({
      ...current,
      student_id: studentContext,
      intervention_id: interventionContext,
      page: 1,
    }));
  }, [studentContext, interventionContext]);
  useEffect(() => {
    setSelectedId(requestedId);
  }, [requestedId]);
  const key = token ? `${token}:${JSON.stringify(params)}` : "";
  const list = useFollowUpResource(
    key,
    revision,
    (signal) => fetchFollowUps(token, params, signal),
    report,
  );
  useEffect(() => {
    if (list.data?.total_pages && list.data.page > list.data.total_pages)
      setParams((p) => ({ ...p, page: list.data!.total_pages }));
  }, [list.data]);
  function select(id: string | null) {
    if (lock.current) return;
    setSelectedId(id);
    const nextQuery = new URLSearchParams(query.toString());
    if (id) nextQuery.set("follow_up_id", id);
    else nextQuery.delete("follow_up_id");
    router.replace(`/follow-ups${nextQuery.size ? `?${nextQuery}` : ""}`, {
      scroll: false,
    });
  }
  const mutate: FollowUpMutation = async (work) => {
    if (lock.current)
      return {
        message: "Another follow-up action is in progress.",
        fields: {},
      };
    if (!user || user.role === "SYSTEM_ADMIN")
      return { message: "Your account has read-only access.", fields: {} };
    lock.current = true;
    setBusy(true);
    setNotice("");
    setMutationError("");
    try {
      await work();
      setNotice(
        "Follow-up saved. The queue, totals, and selected record are refreshing.",
      );
      setRevision((r) => r + 1);
      return null;
    } catch (caught) {
      const failure = followUpFailure(caught);
      report(caught);
      setMutationError(failure.message);
      if (caught instanceof ApiError && [403, 404, 409].includes(caught.status))
        setRevision((r) => r + 1);
      return failure;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  function change(values: Partial<FollowUpParams>) {
    if (!lock.current)
      setParams((current) => ({ ...current, ...values, page: 1 }));
  }
  function clear() {
    if (lock.current) return;
    setParams(FOLLOW_UP_INITIAL);
    const nextQuery = new URLSearchParams(query.toString());
    nextQuery.delete("student_id");
    nextQuery.delete("intervention_id");
    router.replace(`/follow-ups${nextQuery.size ? `?${nextQuery}` : ""}`, {
      scroll: false,
    });
  }
  return {
    user,
    token,
    params,
    list,
    selectedId,
    select,
    revision,
    busy,
    notice,
    mutationError,
    authLoading,
    authError,
    report,
    signOut,
    mutate,
    change,
    clear,
    clearNotice: () => {
      setNotice("");
      setMutationError("");
    },
    refresh: () => {
      if (!lock.current) {
        if (!token) setAuthRetry((r) => r + 1);
        else setRevision((r) => r + 1);
      }
    },
    onPage: (page: number) => {
      if (!lock.current) setParams((p) => ({ ...p, page }));
    },
    scheduleContext:
      query.get("schedule") === "1" ? interventionContext : undefined,
  };
}
