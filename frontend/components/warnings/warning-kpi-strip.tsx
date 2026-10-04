import type { DashboardOverview } from "@/types/dashboard";
import type { WarningParams } from "@/types/warning";
import { Icon, type IconName } from "@/components/dashboard/icon";

export function WarningKpiStrip({
  overview,
  highRisk,
  loading,
  params,
  onFilter,
}: {
  overview: DashboardOverview | null;
  highRisk: number | null;
  loading: boolean;
  params: WarningParams;
  onFilter: (filter: Partial<WarningParams>) => void;
}) {
  const cards: Array<{
    title: string;
    value: number | undefined | null;
    description: string;
    icon: IconName;
    active: boolean;
    filter: Partial<WarningParams>;
    tone: string;
  }> = [
    {
      title: "Awaiting Advisor Review",
      value: overview?.warnings.pending_review,
      description: "Warnings awaiting an individual decision",
      icon: "activity",
      active: params.review_state === "PENDING_REVIEW",
      filter: {
        review_state:
          params.review_state === "PENDING_REVIEW"
            ? undefined
            : "PENDING_REVIEW",
      },
      tone: "pending",
    },
    {
      title: "High-Risk Warnings",
      value: highRisk,
      description: "All warning records classified as high risk",
      icon: "warning",
      active: params.risk_level === "HIGH",
      filter: { risk_level: params.risk_level === "HIGH" ? undefined : "HIGH" },
      tone: "high",
    },
    {
      title: "Confirmed Warnings",
      value: overview?.warnings.confirmed,
      description: "Warnings confirmed through advisor review",
      icon: "check",
      active: params.review_state === "CONFIRMED",
      filter: {
        review_state:
          params.review_state === "CONFIRMED" ? undefined : "CONFIRMED",
      },
      tone: "confirmed",
    },
    {
      title: "Dismissed Warnings",
      value: overview?.warnings.dismissed,
      description: "Warnings dismissed through advisor review",
      icon: "shield",
      active: params.review_state === "DISMISSED",
      filter: {
        review_state:
          params.review_state === "DISMISSED" ? undefined : "DISMISSED",
      },
      tone: "dismissed",
    },
  ];
  return (
    <section
      className="warning-kpis"
      aria-label="Institution-wide warning metrics"
      aria-busy={loading}
    >
      {cards.map((card) => (
        <button
          key={card.title}
          className={`warning-kpi tone-${card.tone}`}
          aria-pressed={card.active}
          onClick={() => onFilter(card.filter)}
        >
          <span className="warning-kpi-heading">
            {card.title}
            <span className="warning-kpi-icon">
              <Icon name={card.icon} />
            </span>
          </span>
          {loading ? (
            <span
              className="warning-skeleton warning-kpi-skeleton"
              aria-label="Loading count"
            />
          ) : (
            <strong className="warning-kpi-value">
              {card.value == null ? "—" : card.value.toLocaleString()}
            </strong>
          )}
          <span className="warning-kpi-description">{card.description}</span>
        </button>
      ))}
    </section>
  );
}
