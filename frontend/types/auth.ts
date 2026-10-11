export type UserRole = "SYSTEM_ADMIN" | "ACADEMIC_ADMIN" | "ACADEMIC_ADVISOR";

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  must_change_password: boolean;
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
