import { API_BASE_URL } from "@/lib/constants";
import { getAccessToken } from "@/lib/auth";
import type {
  ModelCatalog,
  ModelCatalogEntry,
  PredictionStage,
} from "@/types/outcome";
import type {
  InterventionDetail,
  InterventionUpdate,
  InterventionNote,
  InterventionOutcome,
  FollowUpDetail,
  FollowUpInput,
  FollowUpCompletion,
  InterventionPage,
  InterventionParams,
  FollowUpPage,
  FollowUpParams,
} from "@/types/casework";
import type {
  WarningParams,
  WarningPage,
  WarningDetail,
  StudentPredictionPage,
} from "@/types/warning";
import type {
  RegistryPage,
  StudentRegistryParams,
  StudentProfile,
} from "@/types/registry";
import type {
  PredictionParams,
  PredictionPage,
  PredictionDetail,
  CurrentModel,
  ModelPerformance,
} from "@/types/prediction";
import type {
  DashboardOverview,
  ReviewWarningInput,
  InterventionInput,
  InterventionReceipt,
  BatchPredictionResponse,
} from "@/types/dashboard";
import type { ApiErrorBody, TokenResponse, User } from "@/types/auth";
import type {
  UserPage,
  UserInput,
  UserParams,
  AdvisorPage,
} from "@/types/user-administration";
import type { ImportErrorPage, ImportJob, ImportJobPage } from "@/types/import";
import type {
  StagedBatch,
  StagedBatchPage,
  StagedBatchParams,
  StagedRowPage,
  StagedRowParams,
  StagedCorrectionRequest,
  StagedCorrectionResponse,
  StagedVersionRequest,
  StagedActionPage,
} from "@/types/staged-import";
import type {
  AdmissionInput,
  AdmissionRecord,
  FirstSemesterInput,
  FirstSemesterRecord,
  Student,
  StudentInput,
  StudentPage,
} from "@/types/student";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const requestTokens = new WeakMap<Response, string>();

async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(input, init);
  const authorization = new Headers(init?.headers).get("Authorization");
  if (authorization?.startsWith("Bearer "))
    requestTokens.set(response, authorization.slice(7));
  return response;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }

  let body: ApiErrorBody | undefined;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    // A controlled fallback is used if a proxy returns a non-JSON error.
  }
  // Delayed failures from an older session must not clear a replacement token.
  if (
    typeof window !== "undefined" &&
    requestTokens.get(response) === getAccessToken() &&
    window.location.pathname !== "/login"
  ) {
    if (response.status === 401 || body?.error?.code === "USER_INACTIVE") {
      window.dispatchEvent(
        new CustomEvent("academic-auth-error", { detail: "sign-in" }),
      );
    } else if (body?.error?.code === "PASSWORD_CHANGE_REQUIRED") {
      window.dispatchEvent(
        new CustomEvent("academic-auth-error", { detail: "change-password" }),
      );
    }
  }
  throw new ApiError(
    body?.error?.message ?? "The request could not be completed.",
    response.status,
    body?.error?.code ?? "REQUEST_FAILED",
    body?.error?.details,
  );
}

async function dossierRequest<T>(
  token: string,
  path: string,
  method = "GET",
  payload?: object,
  signal?: AbortSignal,
): Promise<T> {
  return parseResponse<T>(
    await apiFetch(`${API_BASE_URL}${path}`, {
      method,
      headers: bearerHeaders(token, payload !== undefined),
      ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
      cache: "no-store",
      signal,
    }),
  );
}
export const fetchUsers = (
  token: string,
  params: UserParams,
  signal?: AbortSignal,
) =>
  dossierRequest<UserPage>(
    token,
    `/users?${stagedQuery(params)}`,
    "GET",
    undefined,
    signal,
  );
export const createUser = (token: string, payload: UserInput) =>
  dossierRequest<User>(token, "/users", "POST", payload);
export const updateUser = (
  token: string,
  id: string,
  payload: Partial<Omit<UserInput, "initial_password">>,
) =>
  dossierRequest<User>(
    token,
    `/users/${encodeURIComponent(id)}`,
    "PATCH",
    payload,
  );
export const setUserActive = (token: string, id: string, active: boolean) =>
  dossierRequest<User>(
    token,
    `/users/${encodeURIComponent(id)}/${active ? "activate" : "deactivate"}`,
    "POST",
  );
export const resetUserPassword = (
  token: string,
  id: string,
  temporary_password: string,
) =>
  dossierRequest<User>(
    token,
    `/users/${encodeURIComponent(id)}/reset-password`,
    "POST",
    { temporary_password },
  );
export const changePassword = (
  token: string,
  current_password: string,
  new_password: string,
) =>
  dossierRequest<TokenResponse>(token, "/auth/change-password", "POST", {
    current_password,
    new_password,
  });
export const fetchAdvisors = (
  token: string,
  page: number,
  search: string,
  signal?: AbortSignal,
) =>
  dossierRequest<AdvisorPage>(
    token,
    `/users/advisors?${stagedQuery({ page, page_size: 100, search })}`,
    "GET",
    undefined,
    signal,
  );

export function accountError(caught: unknown): string {
  if (!(caught instanceof ApiError))
    return "Unable to reach the service. Please try again.";
  if (Array.isArray(caught.details))
    return [
      caught.message,
      ...caught.details.map(
        (item: { field?: string; message?: string }) =>
          `${item.field ?? "Field"}: ${item.message ?? "Invalid value"}`,
      ),
    ].join(" ");
  if (
    caught.code === "ADVISOR_HAS_ACTIVE_ASSIGNMENTS" &&
    caught.details &&
    typeof caught.details === "object"
  )
    return `${caught.message} ${Object.entries(caught.details)
      .map(([key, count]) => `${key.replaceAll("_", " ")}: ${count}`)
      .join(", ")}.`;
  return caught.message;
}
export const predictStudent = (
  token: string,
  id: string,
  stage?: PredictionStage,
) =>
  dossierRequest<PredictionDetail>(
    token,
    `/students/${encodeURIComponent(id)}/predictions${stage ? `?prediction_stage=${stage}` : ""}`,
    "POST",
  );
export const assignStudentWarning = (
  token: string,
  id: string,
  assigned_to: string | null,
) =>
  dossierRequest<WarningDetail>(
    token,
    `/warnings/${encodeURIComponent(id)}/assignment`,
    "PATCH",
    { assigned_to },
  );
export const fetchInterventionDetail = (
  token: string,
  id: string,
  signal?: AbortSignal,
) =>
  dossierRequest<InterventionDetail>(
    token,
    `/interventions/${encodeURIComponent(id)}`,
    "GET",
    undefined,
    signal,
  );
export const fetchInterventions = (
  token: string,
  params: InterventionParams,
  signal?: AbortSignal,
) =>
  dossierRequest<InterventionPage>(
    token,
    `/interventions?${stagedQuery(params)}`,
    "GET",
    undefined,
    signal,
  );
export const fetchFollowUps = (
  token: string,
  params: FollowUpParams,
  signal?: AbortSignal,
) =>
  dossierRequest<FollowUpPage>(
    token,
    `/follow-ups?${stagedQuery(params)}`,
    "GET",
    undefined,
    signal,
  );
export const fetchInterventionFollowUps = (
  token: string,
  id: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
) =>
  dossierRequest<FollowUpPage>(
    token,
    `/interventions/${encodeURIComponent(id)}/follow-ups?${stagedQuery({ page, page_size: pageSize })}`,
    "GET",
    undefined,
    signal,
  );
export const updateIntervention = (
  token: string,
  id: string,
  payload: InterventionUpdate,
) =>
  dossierRequest<InterventionDetail>(
    token,
    `/interventions/${encodeURIComponent(id)}`,
    "PATCH",
    payload,
  );
export const addInterventionNote = (token: string, id: string, note: string) =>
  dossierRequest<InterventionNote>(
    token,
    `/interventions/${encodeURIComponent(id)}/notes`,
    "POST",
    { note },
  );
export const completeIntervention = (
  token: string,
  id: string,
  outcome: InterventionOutcome,
  completion_notes: string,
) =>
  dossierRequest<InterventionDetail>(
    token,
    `/interventions/${encodeURIComponent(id)}/complete`,
    "POST",
    { outcome, completion_notes },
  );
export const cancelIntervention = (token: string, id: string, reason: string) =>
  dossierRequest<InterventionDetail>(
    token,
    `/interventions/${encodeURIComponent(id)}/cancel`,
    "POST",
    { reason },
  );
export const createCaseFollowUp = (
  token: string,
  id: string,
  payload: FollowUpInput,
) =>
  dossierRequest<FollowUpDetail>(
    token,
    `/interventions/${encodeURIComponent(id)}/follow-ups`,
    "POST",
    payload,
  );
export const fetchFollowUpDetail = (
  token: string,
  id: string,
  signal?: AbortSignal,
) =>
  dossierRequest<FollowUpDetail>(
    token,
    `/follow-ups/${encodeURIComponent(id)}`,
    "GET",
    undefined,
    signal,
  );
export const updateCaseFollowUp = (
  token: string,
  id: string,
  payload: Partial<FollowUpInput>,
) =>
  dossierRequest<FollowUpDetail>(
    token,
    `/follow-ups/${encodeURIComponent(id)}`,
    "PATCH",
    payload,
  );
export const completeCaseFollowUp = (
  token: string,
  id: string,
  payload: FollowUpCompletion,
) =>
  dossierRequest<FollowUpDetail>(
    token,
    `/follow-ups/${encodeURIComponent(id)}/complete`,
    "POST",
    payload,
  );
export const cancelCaseFollowUp = (token: string, id: string, reason: string) =>
  dossierRequest<FollowUpDetail>(
    token,
    `/follow-ups/${encodeURIComponent(id)}/cancel`,
    "POST",
    { reason },
  );

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const response = await apiFetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return parseResponse<TokenResponse>(response);
}

export async function fetchCurrentUser(token: string): Promise<User> {
  const response = await apiFetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return parseResponse<User>(response);
}

function bearerHeaders(token: string, includeJson = false): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    ...(includeJson ? { "Content-Type": "application/json" } : {}),
  };
}

export async function fetchStudentRegistry(
  token: string,
  params: StudentRegistryParams,
  signal?: AbortSignal,
): Promise<RegistryPage> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && String(value).trim() !== "")
      query.set(key, String(value).trim());
  }
  return parseResponse<RegistryPage>(
    await apiFetch(`${API_BASE_URL}/student-registry?${query}`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}

export async function fetchStudentProfile(
  token: string,
  studentId: string,
  signal?: AbortSignal,
): Promise<StudentProfile> {
  return parseResponse<StudentProfile>(
    await apiFetch(
      `${API_BASE_URL}/students/${encodeURIComponent(studentId)}/profile`,
      {
        headers: bearerHeaders(token),
        cache: "no-store",
        signal,
      },
    ),
  );
}

export async function fetchCurrentModelPerformance(
  token: string,
  signal?: AbortSignal,
): Promise<ModelPerformance> {
  return parseResponse<ModelPerformance>(
    await apiFetch(`${API_BASE_URL}/models/current/performance`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}

export async function fetchCurrentModel(
  token: string,
  signal?: AbortSignal,
): Promise<CurrentModel> {
  return parseResponse<CurrentModel>(
    await apiFetch(`${API_BASE_URL}/models/current`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}
export async function fetchPredictions(
  token: string,
  params: PredictionParams,
  signal?: AbortSignal,
): Promise<PredictionPage> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && String(value).trim())
      query.set(key, String(value).trim());
  }
  return parseResponse<PredictionPage>(
    await apiFetch(`${API_BASE_URL}/predictions?${query}`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}
export async function fetchPrediction(
  token: string,
  predictionId: string,
  signal?: AbortSignal,
): Promise<PredictionDetail> {
  return parseResponse<PredictionDetail>(
    await apiFetch(
      `${API_BASE_URL}/predictions/${encodeURIComponent(predictionId)}`,
      { headers: bearerHeaders(token), cache: "no-store", signal },
    ),
  );
}

export async function fetchDashboardOverview(
  token: string,
  signal?: AbortSignal,
  predictionScope: "OPERATIONAL_CURRENT" | "LEGACY_BINARY_FIRST_SEMESTER" = "OPERATIONAL_CURRENT",
): Promise<DashboardOverview> {
  return parseResponse<DashboardOverview>(
    await apiFetch(`${API_BASE_URL}/dashboard/overview?prediction_scope=${predictionScope}`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}

export async function reviewWarning(
  token: string,
  warningId: string,
  payload: ReviewWarningInput,
): Promise<WarningDetail> {
  return parseResponse<WarningDetail>(
    await apiFetch(
      `${API_BASE_URL}/warnings/${encodeURIComponent(warningId)}/reviews`,
      {
        method: "POST",
        headers: bearerHeaders(token, true),
        body: JSON.stringify(payload),
      },
    ),
  );
}

export async function fetchWarnings(
  token: string,
  params: WarningParams,
  signal?: AbortSignal,
): Promise<WarningPage> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && String(value).trim())
      query.set(key, String(value).trim());
  }
  return parseResponse<WarningPage>(
    await apiFetch(`${API_BASE_URL}/warnings?${query}`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}

export async function fetchWarning(
  token: string,
  warningId: string,
  signal?: AbortSignal,
): Promise<WarningDetail> {
  return parseResponse<WarningDetail>(
    await apiFetch(
      `${API_BASE_URL}/warnings/${encodeURIComponent(warningId)}`,
      {
        headers: bearerHeaders(token),
        cache: "no-store",
        signal,
      },
    ),
  );
}

export async function fetchStudentPredictions(
  token: string,
  studentId: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<StudentPredictionPage> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return parseResponse<StudentPredictionPage>(
    await apiFetch(
      `${API_BASE_URL}/students/${encodeURIComponent(studentId)}/predictions?${query}`,
      {
        headers: bearerHeaders(token),
        cache: "no-store",
        signal,
      },
    ),
  );
}

export async function createIntervention(
  token: string,
  payload: InterventionInput,
): Promise<InterventionReceipt> {
  return parseResponse<InterventionReceipt>(
    await apiFetch(`${API_BASE_URL}/interventions`, {
      method: "POST",
      headers: bearerHeaders(token, true),
      body: JSON.stringify(payload),
    }),
  );
}

export async function runBatchPrediction(
  token: string,
  stage?: PredictionStage,
): Promise<BatchPredictionResponse> {
  return parseResponse<BatchPredictionResponse>(
    await apiFetch(
      `${API_BASE_URL}/predictions/batch${stage ? `?prediction_stage=${stage}` : ""}`,
      {
        method: "POST",
        headers: bearerHeaders(token),
      },
    ),
  );
}

export const fetchModelCatalog = (token: string, signal?: AbortSignal) =>
  dossierRequest<ModelCatalog>(token, "/models", "GET", undefined, signal);
export const validateStageModel = (
  token: string,
  version: string,
  student_id: string,
) =>
  dossierRequest<ModelCatalogEntry>(
    token,
    `/models/${encodeURIComponent(version)}/validate`,
    "POST",
    { student_id },
  );
export const activateStageModel = (token: string, version: string) =>
  dossierRequest<ModelCatalogEntry>(
    token,
    `/models/${encodeURIComponent(version)}/activate`,
    "POST",
  );

export async function fetchStudents(
  token: string,
  page: number,
  pageSize: number,
  search: string,
): Promise<StudentPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (search.trim()) params.set("search", search.trim());
  const response = await apiFetch(`${API_BASE_URL}/students?${params}`, {
    headers: bearerHeaders(token),
  });
  return parseResponse<StudentPage>(response);
}

export async function fetchStudent(
  token: string,
  studentId: string,
): Promise<Student> {
  const response = await apiFetch(`${API_BASE_URL}/students/${studentId}`, {
    headers: bearerHeaders(token),
  });
  return parseResponse<Student>(response);
}

export async function createStudent(
  token: string,
  payload: StudentInput,
): Promise<Student> {
  const response = await apiFetch(`${API_BASE_URL}/students`, {
    method: "POST",
    headers: bearerHeaders(token, true),
    body: JSON.stringify(payload),
  });
  return parseResponse<Student>(response);
}

export async function updateStudent(
  token: string,
  studentId: string,
  payload: Partial<StudentInput>,
): Promise<Student> {
  const response = await apiFetch(`${API_BASE_URL}/students/${studentId}`, {
    method: "PATCH",
    headers: bearerHeaders(token, true),
    body: JSON.stringify(payload),
  });
  return parseResponse<Student>(response);
}

export async function deleteStudent(
  token: string,
  studentId: string,
): Promise<void> {
  const response = await apiFetch(`${API_BASE_URL}/students/${studentId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  });
  if (!response.ok) await parseResponse<never>(response);
}

export async function fetchAdmission(
  token: string,
  studentId: string,
): Promise<AdmissionRecord> {
  const response = await apiFetch(
    `${API_BASE_URL}/students/${studentId}/admission`,
    {
      headers: bearerHeaders(token),
    },
  );
  return parseResponse<AdmissionRecord>(response);
}

export async function saveAdmission(
  token: string,
  studentId: string,
  payload: AdmissionInput,
): Promise<AdmissionRecord> {
  const response = await apiFetch(
    `${API_BASE_URL}/students/${studentId}/admission`,
    {
      method: "PUT",
      headers: bearerHeaders(token, true),
      body: JSON.stringify(payload),
    },
  );
  return parseResponse<AdmissionRecord>(response);
}

export async function fetchFirstSemester(
  token: string,
  studentId: string,
): Promise<FirstSemesterRecord> {
  const response = await apiFetch(
    `${API_BASE_URL}/students/${studentId}/semester-1`,
    {
      headers: bearerHeaders(token),
    },
  );
  return parseResponse<FirstSemesterRecord>(response);
}

export async function saveFirstSemester(
  token: string,
  studentId: string,
  payload: FirstSemesterInput,
): Promise<FirstSemesterRecord> {
  const response = await apiFetch(
    `${API_BASE_URL}/students/${studentId}/semester-1`,
    {
      method: "PUT",
      headers: bearerHeaders(token, true),
      body: JSON.stringify(payload),
    },
  );
  return parseResponse<FirstSemesterRecord>(response);
}

function stagedQuery(params: object): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params))
    if (value !== undefined) query.set(key, String(value));
  return query.toString();
}
export async function fetchStagedImports(
  token: string,
  params: StagedBatchParams,
  signal?: AbortSignal,
): Promise<StagedBatchPage> {
  return parseResponse<StagedBatchPage>(
    await apiFetch(`${API_BASE_URL}/imports/staged?${stagedQuery(params)}`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}
export async function fetchStagedImport(
  token: string,
  batchId: string,
  signal?: AbortSignal,
): Promise<StagedBatch> {
  return parseResponse<StagedBatch>(
    await apiFetch(
      `${API_BASE_URL}/imports/staged/${encodeURIComponent(batchId)}`,
      { headers: bearerHeaders(token), cache: "no-store", signal },
    ),
  );
}
export async function fetchStagedRows(
  token: string,
  batchId: string,
  params: StagedRowParams,
  signal?: AbortSignal,
): Promise<StagedRowPage> {
  return parseResponse<StagedRowPage>(
    await apiFetch(
      `${API_BASE_URL}/imports/staged/${encodeURIComponent(batchId)}/rows?${stagedQuery(params)}`,
      { headers: bearerHeaders(token), cache: "no-store", signal },
    ),
  );
}
export async function uploadStagedCsv(
  token: string,
  file: File,
): Promise<StagedBatch> {
  const body = new FormData();
  body.append("file", file);
  return parseResponse<StagedBatch>(
    await apiFetch(`${API_BASE_URL}/imports/staged/csv`, {
      method: "POST",
      headers: bearerHeaders(token),
      body,
    }),
  );
}
export async function correctStagedRow(
  token: string,
  batchId: string,
  rowId: string,
  request: StagedCorrectionRequest,
): Promise<StagedCorrectionResponse> {
  return parseResponse<StagedCorrectionResponse>(
    await apiFetch(
      `${API_BASE_URL}/imports/staged/${encodeURIComponent(batchId)}/rows/${encodeURIComponent(rowId)}`,
      {
        method: "PATCH",
        headers: bearerHeaders(token, true),
        body: JSON.stringify(request),
      },
    ),
  );
}
async function stagedBatchAction(
  token: string,
  batchId: string,
  action: "commit" | "cancel",
  request: StagedVersionRequest,
): Promise<StagedBatch> {
  return parseResponse<StagedBatch>(
    await apiFetch(
      `${API_BASE_URL}/imports/staged/${encodeURIComponent(batchId)}/${action}`,
      {
        method: "POST",
        headers: bearerHeaders(token, true),
        body: JSON.stringify(request),
      },
    ),
  );
}
export function commitStagedImport(
  token: string,
  batchId: string,
  request: StagedVersionRequest,
) {
  return stagedBatchAction(token, batchId, "commit", request);
}
export function cancelStagedImport(
  token: string,
  batchId: string,
  request: StagedVersionRequest,
) {
  return stagedBatchAction(token, batchId, "cancel", request);
}
export async function fetchStagedActions(
  token: string,
  batchId: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<StagedActionPage> {
  return parseResponse<StagedActionPage>(
    await apiFetch(
      `${API_BASE_URL}/imports/staged/${encodeURIComponent(batchId)}/actions?page=${page}&page_size=${pageSize}`,
      { headers: bearerHeaders(token), cache: "no-store", signal },
    ),
  );
}
export async function exportStagedCsv(
  token: string,
  batchId: string,
): Promise<void> {
  const response = await apiFetch(
    `${API_BASE_URL}/imports/staged/${encodeURIComponent(batchId)}/export`,
    { headers: bearerHeaders(token), cache: "no-store" },
  );
  if (!response.ok) await parseResponse<never>(response);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `staged-import-${batchId}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function fetchImports(
  token: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<ImportJobPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await apiFetch(`${API_BASE_URL}/imports?${params}`, {
    headers: bearerHeaders(token),
    cache: "no-store",
    signal,
  });
  return parseResponse<ImportJobPage>(response);
}

export async function fetchImportErrors(
  token: string,
  importId: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<ImportErrorPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await apiFetch(
    `${API_BASE_URL}/imports/${importId}/errors?${params}`,
    {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    },
  );
  return parseResponse<ImportErrorPage>(response);
}

export async function uploadStudentCsv(
  token: string,
  file: File,
): Promise<ImportJob> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiFetch(`${API_BASE_URL}/imports/csv`, {
    method: "POST",
    headers: bearerHeaders(token),
    body,
  });
  return parseResponse<ImportJob>(response);
}

export async function downloadImportTemplate(token: string): Promise<void> {
  const response = await apiFetch(`${API_BASE_URL}/imports/template`, {
    headers: bearerHeaders(token),
  });
  if (!response.ok) await parseResponse<never>(response);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "student-import-template.csv";
  link.click();
  URL.revokeObjectURL(url);
}
