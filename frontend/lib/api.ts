import { API_BASE_URL } from "@/lib/constants";
import type { ApiErrorBody, TokenResponse, User } from "@/types/auth";

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
    body?.error.message ?? "The request could not be completed.",
    response.status,
    body?.error.code ?? "REQUEST_FAILED",
  );
}

export async function login(username: string, password: string): Promise<TokenResponse> {
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

