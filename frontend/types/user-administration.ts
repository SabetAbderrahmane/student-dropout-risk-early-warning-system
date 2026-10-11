import type { User, UserRole } from "./auth";
export interface UserPage {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  counts: {
    total: number;
    active: number;
    academic_admins: number;
    advisors: number;
  };
}
export interface UserInput {
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  initial_password: string;
}
export interface UserParams {
  page: number;
  page_size: number;
  search?: string;
  role?: UserRole;
  is_active?: boolean;
}
export interface AdvisorEntry {
  id: string;
  full_name: string;
}
export interface AdvisorPage {
  items: AdvisorEntry[];
  page: number;
  total_pages: number;
  total: number;
}
