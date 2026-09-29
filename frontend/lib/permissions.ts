import type { UserRole } from "@/types/auth";

export function hasRole(currentRole: UserRole, allowedRoles: readonly UserRole[]): boolean {
  return allowedRoles.includes(currentRole);
}

