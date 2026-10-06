import Link from "next/link";
import { Icon } from "./icon";
import type { DashboardOverview } from "@/types/dashboard";

export function NextActions({ data }: { data: DashboardOverview }) {
  const items = [
    {
      href: "/warnings",
      icon: "warning" as const,
      label: "Review warnings",
      value: data.warnings.pending_review,
      note: "awaiting advisor review",
    },
    {
      href: "/interventions",
      icon: "casework" as const,
      label: "Coordinate support",
      value: data.interventions.action_required,
      note: "cases need action",
    },
    {
      href: "/follow-ups",
      icon: "calendar" as const,
      label: "Follow through",
      value: data.follow_ups.overdue + data.follow_ups.due_today,
      note: "due or overdue contacts",
    },
  ];
  return (
    <section className="workspace-next" aria-label="Where to start">
      <div className="workspace-next-heading">
        <strong>Where to start</strong>
        <span>Institution-wide priorities</span>
      </div>
      <div className="workspace-next-links">
        {items.map((item) => (
          <Link href={item.href} key={item.href}>
            <span className="workspace-next-icon">
              <Icon name={item.icon} />
            </span>
            <span>
              <strong>{item.label}</strong>
              <small>
                <b>{item.value.toLocaleString()}</b> {item.note}
              </small>
            </span>
            <Icon name="arrow" />
          </Link>
        ))}
      </div>
    </section>
  );
}
