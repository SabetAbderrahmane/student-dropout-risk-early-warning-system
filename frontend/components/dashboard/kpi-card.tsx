import type { ReactNode } from "react";
import { Icon, type IconName } from "./icon";

export function KpiCard({
  title,
  value,
  icon,
  children,
  danger = false,
}: {
  title: string;
  value: number;
  icon: IconName;
  children: ReactNode;
  danger?: boolean;
}) {
  return (
    <article
      className={`dash-card dash-kpi ${danger ? "dash-kpi-danger" : ""}`}
    >
      <div className="dash-kpi-heading">
        <h2>{title}</h2>
        <span className="dash-kpi-icon">
          <Icon name={icon} />
        </span>
      </div>
      <strong className="dash-kpi-value">{value.toLocaleString("en")}</strong>
      <div className="dash-kpi-detail">{children}</div>
    </article>
  );
}
