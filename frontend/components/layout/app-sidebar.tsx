import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { Icon } from "@/components/dashboard/icon";

export function AppSidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement;
    ref.current?.querySelector<HTMLElement>("a")?.focus();
    return () => {
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, [open]);
  return (
    <>
      {open && (
        <button
          className="dash-nav-backdrop"
          aria-label="Dismiss navigation overlay"
          onClick={onClose}
        />
      )}
      <aside
        ref={ref}
        id="dashboard-navigation"
        className={`dash-sidebar ${open ? "is-open" : ""}`}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
      >
        <Link href="/dashboard" className="dash-brand" onClick={onClose}>
          <span className="dash-brand-mark">
            <Icon name="shield" />
          </span>
          <span>
            <strong>Academic Early Warning</strong>
            <small>Student retention decision support</small>
          </span>
        </Link>
        <button className="dash-mobile-close dash-button" onClick={onClose}>
          <Icon name="close" />
          Close navigation
        </button>
        <nav aria-label="Main navigation">
          <p className="dash-nav-label">Core system</p>
          <Link
            href="/dashboard"
            aria-current={pathname === "/dashboard" ? "page" : undefined}
            onClick={onClose}
          >
            <Icon name="grid" />
            Overview / Dashboard
          </Link>
          <Link
            href="/students"
            aria-current={pathname.startsWith("/students") ? "page" : undefined}
            onClick={onClose}
          >
            <Icon name="students" />
            Students
          </Link>
          <Link
            href="/imports"
            aria-current={pathname.startsWith("/imports") ? "page" : undefined}
            onClick={onClose}
          >
            <Icon name="import" />
            Data Import
          </Link>
          {[
            "Risk Predictions",
            "Early Warnings",
            "Interventions",
            "Follow-Ups",
          ].map((label) =>
            label === "Early Warnings" || label === "Risk Predictions" ? (
              <Link
                key={label}
                href={label === "Early Warnings" ? "/warnings" : "/predictions"}
                aria-current={
                  pathname.startsWith(
                    label === "Early Warnings" ? "/warnings" : "/predictions",
                  )
                    ? "page"
                    : undefined
                }
                onClick={onClose}
              >
                <Icon
                  name={label === "Early Warnings" ? "warning" : "activity"}
                />
                {label}
              </Link>
            ) : (
              <span key={label} className="dash-future" aria-disabled="true">
                <Icon name="activity" />
                {label}
                <small>Later</small>
              </span>
            ),
          )}
          <p className="dash-nav-label dash-nav-divider">Administration</p>
          {[
            "Users",
            "Roles & Permissions",
            "System Configuration",
            "Audit Logs",
          ].map((label) => (
            <span key={label} className="dash-future" aria-disabled="true">
              <Icon name="settings" />
              {label}
              <small>Later</small>
            </span>
          ))}
        </nav>
        <div className="dash-sidebar-footer">
          <Icon name="shield" />
          <span>
            Academic risk workspace
            <small>Evidence informs. Advisors decide.</small>
          </span>
        </div>
      </aside>
    </>
  );
}
