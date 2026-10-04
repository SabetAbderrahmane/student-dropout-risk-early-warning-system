import type { User } from "@/types/auth";
import { readable } from "@/lib/dashboard";
import { Icon } from "@/components/dashboard/icon";

export function AppHeader({
  user,
  menuOpen,
  onMenu,
  onSignOut,
  title = "Overview",
}: {
  user: User | null;
  menuOpen: boolean;
  onMenu: () => void;
  onSignOut: () => void;
  title?: string;
}) {
  return (
    <header className="dash-header">
      <div className="dash-header-context">
        <button
          className="dash-icon-button dash-menu"
          onClick={onMenu}
          aria-label="Toggle navigation"
          aria-controls="dashboard-navigation"
          aria-expanded={menuOpen}
        >
          <Icon name="menu" />
        </button>
        <span>
          Workspace <span className="dash-breadcrumb">/</span>{" "}
          <strong>{title}</strong>
        </span>
      </div>
      <div className="dash-account">
        {user && (
          <>
            <div className="dash-avatar" aria-hidden="true">
              {user.full_name
                .split(" ")
                .filter(Boolean)
                .slice(0, 2)
                .map((word) => word[0])
                .join("")}
            </div>
            <div className="dash-identity">
              <strong>{user.full_name}</strong>
              <small>{readable(user.role)}</small>
            </div>
          </>
        )}
        <button
          className="dash-icon-button"
          onClick={onSignOut}
          aria-label="Sign out"
          title="Sign out"
        >
          <Icon name="logout" />
        </button>
      </div>
    </header>
  );
}
