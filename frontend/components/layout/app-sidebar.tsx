"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { Icon } from "@/components/dashboard/icon";
import { useGuide } from "@/components/guide/guide-provider";
import { WORKSPACE_STEPS } from "@/lib/workspace-guide";

export function AppSidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const ref = useRef<HTMLElement>(null);
  const { user, openHelp } = useGuide();
  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement;
    const previousOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    ref.current?.querySelector<HTMLElement>("a")?.focus();
    return () => {
      document.documentElement.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected)
        previousFocus.focus();
    };
  }, [open]);
  const groups = [
    { label: "Records & insights", items: WORKSPACE_STEPS.slice(0, 4) },
    { label: "Student support", items: WORKSPACE_STEPS.slice(4) },
  ];
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
        aria-label="Workspace navigation"
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
          if (open && event.key === "Tab") {
            const controls = ref.current?.querySelectorAll<HTMLElement>(
              "a,button:not([disabled])",
            );
            const first = controls?.[0],
              last = controls?.[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <Link href="/dashboard" className="dash-brand" onClick={onClose}>
          <span className="dash-brand-mark">
            <Icon name="shield" />
          </span>
          <span>
            <strong>Academic Early Warning</strong>
            <small>Student support workspace</small>
          </span>
        </Link>
        <button className="dash-mobile-close dash-button" onClick={onClose}>
          <Icon name="close" /> Close navigation
        </button>
        <nav aria-label="Main navigation">
          {groups.map((group) => (
            <div key={group.label} className="dash-nav-group">
              <p className="dash-nav-label">{group.label}</p>
              {group.items
                .filter(
                  (item) =>
                    user?.role !== "ACADEMIC_ADVISOR" || item.id !== "imports",
                )
                .map((item) => (
                  <Link
                    key={item.id}
                    href={item.href}
                    aria-current={
                      pathname === item.href ||
                      (item.href !== "/dashboard" &&
                        pathname.startsWith(item.href + "/"))
                        ? "page"
                        : undefined
                    }
                    onClick={onClose}
                  >
                    <span className="dash-nav-icon">
                      <Icon name={item.icon} />
                    </span>
                    {item.label}
                  </Link>
                ))}
            </div>
          ))}
        </nav>
        <div className="dash-sidebar-footer">
          <button
            className="dash-guide-entry"
            disabled={!user}
            onClick={() => {
              onClose();
              openHelp();
            }}
          >
            <span className="dash-guide-symbol">
              <Icon name="book" />
            </span>
            <span>
              <strong>Find your way around</strong>
              <small>Tour & quick help</small>
            </span>
            <Icon name="chevron" />
          </button>
          <p>Evidence informs. Advisors decide.</p>
        </div>
      </aside>
    </>
  );
}
