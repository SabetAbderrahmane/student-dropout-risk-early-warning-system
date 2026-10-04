"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  fetchCurrentUser,
  fetchStagedImports,
  fetchStagedImport,
  fetchStagedRows,
  uploadStagedCsv,
  correctStagedRow,
  commitStagedImport,
  cancelStagedImport,
  exportStagedCsv,
  downloadImportTemplate,
} from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { isMutableBatch, stagedError } from "@/lib/staged-imports";
import type { User } from "@/types/auth";
import type {
  StagedBatch,
  StagedBatchPage,
  StagedBatchParams,
  StagedRow,
  StagedRowPage,
  StagedRowParams,
  StagedCorrectionRequest,
} from "@/types/staged-import";

const INITIAL_ROWS: StagedRowParams = { page: 1, page_size: 25 };
export interface RowSession {
  row: StagedRow;
  batchVersion: number;
  blocked: boolean;
}
export function useStagedReview() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [authRetry, setAuthRetry] = useState(0);
  const [authLoading, setAuthLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [writeDenied, setWriteDenied] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [list, setList] = useState<StagedBatchPage | null>(null);
  const [listParams, setListParams] = useState<StagedBatchParams>({
    page: 1,
    page_size: 25,
  });
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [listRevision, setListRevision] = useState(0);
  const [selectedId, setSelectedId] = useState("");
  const [batch, setBatch] = useState<StagedBatch | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState("");
  const [rows, setRows] = useState<StagedRowPage | null>(null);
  const [rowParams, setRowParams] = useState<StagedRowParams>(INITIAL_ROWS);
  const [search, setSearch] = useState("");
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState("");
  const [reviewRevision, setReviewRevision] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState("");
  const lock = useRef(false);
  const [editor, setEditor] = useState<RowSession | null>(null);
  const canRead = !!user && user.role !== "ACADEMIC_ADVISOR" && !accessDenied;
  const canWrite = canRead && user?.role === "ACADEMIC_ADMIN" && !writeDenied;
  const coherent =
    !!batch &&
    !!rows &&
    !batchLoading &&
    !rowsLoading &&
    rows.batch_version === batch.version;
  const mutable = !!batch && isMutableBatch(batch);
  function signOut() {
    clearAccessToken();
    router.replace("/login");
  }
  function report(caught: unknown, read = false) {
    if (caught instanceof ApiError && caught.status === 401) {
      signOut();
      return;
    }
    if (caught instanceof ApiError && caught.status === 403) {
      setWriteDenied(true);
      if (read) setAccessDenied(true);
    }
    setError(stagedError(caught));
  }
  useEffect(() => {
    let active = true;
    const accessToken = getAccessToken();
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    setAuthLoading(true);
    fetchCurrentUser(accessToken)
      .then((current) => {
        if (!active) return;
        setUser(current);
        if (current.role !== "ACADEMIC_ADVISOR") {
          setToken(accessToken);
          setSelectedId(
            new URLSearchParams(window.location.search).get("batch") ?? "",
          );
        }
      })
      .catch((caught: unknown) => {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          clearAccessToken();
          router.replace("/login");
        } else setError(stagedError(caught));
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router, authRetry]);
  useEffect(() => {
    if (!token || accessDenied) return;
    const controller = new AbortController();
    setListLoading(true);
    setListError("");
    setList(null);
    fetchStagedImports(token, listParams, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setList(data);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          report(caught, true);
          setListError(stagedError(caught));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setListLoading(false);
      });
    return () => controller.abort();
  }, [token, listParams, listRevision, accessDenied]);
  useEffect(() => {
    if (!token || !selectedId || accessDenied) return;
    const controller = new AbortController();
    setBatchLoading(true);
    setBatchError("");
    setBatch(null);
    fetchStagedImport(token, selectedId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setBatch(data);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          report(caught, true);
          setBatchError(stagedError(caught));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBatchLoading(false);
      });
    return () => controller.abort();
  }, [token, selectedId, reviewRevision, accessDenied]);
  useEffect(() => {
    if (!token || !selectedId || accessDenied) return;
    const controller = new AbortController();
    setRowsLoading(true);
    setRowsError("");
    setRows(null);
    fetchStagedRows(token, selectedId, rowParams, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setRows(data);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          report(caught, true);
          setRowsError(stagedError(caught));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setRowsLoading(false);
      });
    return () => controller.abort();
  }, [token, selectedId, rowParams, reviewRevision, accessDenied]);
  useEffect(() => {
    const timer = setTimeout(
      () =>
        setRowParams((current) =>
          current.search === (search || undefined)
            ? current
            : { ...current, search: search || undefined, page: 1 },
        ),
      300,
    );
    return () => clearTimeout(timer);
  }, [search]);
  function refresh() {
    if (lock.current) return;
    setError("");
    if (!token) setAuthRetry((value) => value + 1);
    else {
      setListRevision((value) => value + 1);
      setReviewRevision((value) => value + 1);
    }
  }
  function choose(id: string) {
    setSelectedId(id);
    setBatch(null);
    setRows(null);
    setEditor(null);
    setSearch("");
    setRowParams(INITIAL_ROWS);
    setError("");
    setNotice("");
    router.replace(
      id ? `/imports?batch=${encodeURIComponent(id)}` : "/imports",
      { scroll: false },
    );
  }
  function select(id: string) {
    if (!lock.current) choose(id);
  }
  function filter(values: Partial<StagedRowParams>) {
    if (!lock.current)
      setRowParams((current) => ({ ...current, ...values, page: 1 }));
  }
  function clearFilters() {
    if (lock.current) return;
    setSearch("");
    setRowParams((current) => ({
      ...INITIAL_ROWS,
      page_size: current.page_size,
    }));
  }
  async function reloadReview(id = selectedId) {
    setRows(null);
    setRowsLoading(true);
    setBatchLoading(true);
    setRowsError("");
    setBatchError("");
    const results = await Promise.allSettled([
      fetchStagedImport(token, id),
      fetchStagedRows(token, id, rowParams),
    ]);
    const [metadata, page] = results;
    if (metadata.status === "fulfilled") setBatch(metadata.value);
    else {
      report(metadata.reason, true);
      setBatchError(stagedError(metadata.reason));
      setBatch(null);
    }
    if (page.status === "fulfilled") setRows(page.value);
    else {
      report(page.reason, true);
      setRowsError(stagedError(page.reason));
    }
    setRowsLoading(false);
    setBatchLoading(false);
  }
  async function action(key: string, work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(key);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (caught) {
      report(caught);
      if (
        selectedId &&
        key !== "upload" &&
        key !== "template" &&
        key !== "export"
      ) {
        if (caught instanceof ApiError && [404, 409].includes(caught.status))
          setEditor((current) =>
            current ? { ...current, blocked: true } : null,
          );
        if (!(caught instanceof ApiError && caught.status === 401))
          await reloadReview();
      }
    } finally {
      lock.current = false;
      setBusy("");
    }
  }
  async function upload() {
    if (!canWrite || !file) return;
    await action("upload", async () => {
      const created = await uploadStagedCsv(token, file);
      choose(created.id);
      setBatch(created);
      setFile(null);
      setListParams((current) => ({ ...current, page: 1, status: undefined }));
      setListRevision((value) => value + 1);
      setNotice(
        "CSV staged for review. No student records have been persisted.",
      );
    });
  }
  async function correct(
    row: StagedRow,
    version: number,
    changes: Omit<
      StagedCorrectionRequest,
      "expected_batch_version" | "expected_row_version"
    >,
    key = "edit",
  ) {
    if (!canWrite || !batch || !mutable || !coherent) return;
    await action(key, async () => {
      const result = await correctStagedRow(token, batch.id, row.id, {
        expected_batch_version: version,
        expected_row_version: row.version,
        ...changes,
      });
      setBatch(result.batch);
      setEditor(null);
      setNotice(
        "Changes saved and revalidated by the backend. The current row page has been reloaded.",
      );
      await reloadReview(batch.id);
      setListRevision((value) => value + 1);
    });
  }
  async function commit() {
    if (
      !canWrite ||
      !batch ||
      !coherent ||
      batch.status !== "READY_TO_COMMIT" ||
      !batch.included_rows
    )
      return;
    await action("commit", async () => {
      const result = await commitStagedImport(token, batch.id, {
        expected_batch_version: batch.version,
      });
      setBatch(result);
      setEditor(null);
      await reloadReview(batch.id);
      setListRevision((value) => value + 1);
      setNotice(
        "Import committed. The receipt below records the students persisted by the backend.",
      );
    });
  }
  async function cancel() {
    if (!canWrite || !batch || !mutable || !coherent) return;
    await action("cancel", async () => {
      const result = await cancelStagedImport(token, batch.id, {
        expected_batch_version: batch.version,
      });
      setBatch(result);
      setEditor(null);
      await reloadReview(batch.id);
      setListRevision((value) => value + 1);
      setNotice(
        "Batch cancelled. The pending import will not create student records.",
      );
    });
  }
  function openRow(row: StagedRow) {
    if (!busy && batch)
      setEditor({ row, batchVersion: batch.version, blocked: false });
  }
  return {
    user,
    token,
    authLoading,
    canRead,
    canWrite,
    error,
    notice,
    report,
    signOut,
    refresh,
    list,
    listParams,
    setListParams,
    listLoading,
    listError,
    selectedId,
    select,
    batch,
    batchLoading,
    batchError,
    rows,
    rowParams,
    filter,
    search,
    setSearch,
    rowsLoading,
    rowsError,
    clearFilters,
    setRowParams,
    coherent,
    mutable,
    file,
    setFile,
    busy,
    upload,
    correct,
    commit,
    cancel,
    editor,
    setEditor,
    openRow,
    downloadTemplate: () =>
      action("template", () => downloadImportTemplate(token)),
    exportCsv: () =>
      batch
        ? action("export", () => exportStagedCsv(token, batch.id))
        : Promise.resolve(),
  };
}
