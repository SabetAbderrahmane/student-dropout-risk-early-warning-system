import { API_BASE_URL } from "@/lib/constants";
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
  ModelPerformance,
} from "@/types/registry";
import type {
  DashboardOverview,
  ReviewWarningInput,
  InterventionInput,
  InterventionReceipt,
  BatchPredictionResponse,
} from "@/types/dashboard";
import type { ApiErrorBody, TokenResponse, User } from "@/types/auth";
import type { ImportErrorPage, ImportJob, ImportJobPage } from "@/types/import";
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
  ) {
    super(message);
    this.name = "ApiError";
  }
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
  throw new ApiError(
    body?.error?.message ?? "The request could not be completed.",
    response.status,
    body?.error?.code ?? "REQUEST_FAILED",
  );
}

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return parseResponse<TokenResponse>(response);
}

export async function fetchCurrentUser(token: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
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
    await fetch(`${API_BASE_URL}/student-registry?${query}`, {
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
    await fetch(
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
): Promise<ModelPerformance> {
  return parseResponse<ModelPerformance>(
    await fetch(`${API_BASE_URL}/models/current/performance`, {
      headers: bearerHeaders(token),
      cache: "no-store",
    }),
  );
}

export async function fetchDashboardOverview(
  token: string,
  signal?: AbortSignal,
): Promise<DashboardOverview> {
  return parseResponse<DashboardOverview>(
    await fetch(`${API_BASE_URL}/dashboard/overview`, {
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
    await fetch(
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
    await fetch(`${API_BASE_URL}/warnings?${query}`, {
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
    await fetch(`${API_BASE_URL}/warnings/${encodeURIComponent(warningId)}`, {
      headers: bearerHeaders(token),
      cache: "no-store",
      signal,
    }),
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
    await fetch(
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
    await fetch(`${API_BASE_URL}/interventions`, {
      method: "POST",
      headers: bearerHeaders(token, true),
      body: JSON.stringify(payload),
    }),
  );
}

export async function runBatchPrediction(
  token: string,
): Promise<BatchPredictionResponse> {
  return parseResponse<BatchPredictionResponse>(
    await fetch(`${API_BASE_URL}/predictions/batch`, {
      method: "POST",
      headers: bearerHeaders(token),
    }),
  );
}

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
  const response = await fetch(`${API_BASE_URL}/students?${params}`, {
    headers: bearerHeaders(token),
  });
  return parseResponse<StudentPage>(response);
}

export async function fetchStudent(
  token: string,
  studentId: string,
): Promise<Student> {
  const response = await fetch(`${API_BASE_URL}/students/${studentId}`, {
    headers: bearerHeaders(token),
  });
  return parseResponse<Student>(response);
}

export async function createStudent(
  token: string,
  payload: StudentInput,
): Promise<Student> {
  const response = await fetch(`${API_BASE_URL}/students`, {
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
  const response = await fetch(`${API_BASE_URL}/students/${studentId}`, {
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
  const response = await fetch(`${API_BASE_URL}/students/${studentId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  });
  if (!response.ok) await parseResponse<never>(response);
}

export async function fetchAdmission(
  token: string,
  studentId: string,
): Promise<AdmissionRecord> {
  const response = await fetch(
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
  const response = await fetch(
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
  const response = await fetch(
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
  const response = await fetch(
    `${API_BASE_URL}/students/${studentId}/semester-1`,
    {
      method: "PUT",
      headers: bearerHeaders(token, true),
      body: JSON.stringify(payload),
    },
  );
  return parseResponse<FirstSemesterRecord>(response);
}

export async function fetchImports(
  token: string,
  page: number,
  pageSize: number,
): Promise<ImportJobPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await fetch(`${API_BASE_URL}/imports?${params}`, {
    headers: bearerHeaders(token),
  });
  return parseResponse<ImportJobPage>(response);
}

export async function fetchImportErrors(
  token: string,
  importId: string,
  page: number,
  pageSize: number,
): Promise<ImportErrorPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await fetch(
    `${API_BASE_URL}/imports/${importId}/errors?${params}`,
    {
      headers: bearerHeaders(token),
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
  const response = await fetch(`${API_BASE_URL}/imports/csv`, {
    method: "POST",
    headers: bearerHeaders(token),
    body,
  });
  return parseResponse<ImportJob>(response);
}

export async function downloadImportTemplate(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/imports/template`, {
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
