import type { ExplanationFactor } from "@/types/warning";
import { readable } from "@/lib/dashboard";

export function ExplanationFactors({
  factors,
}: {
  factors: ExplanationFactor[];
}) {
  const max = Math.max(
    0,
    ...factors.map((factor) => Math.abs(factor.contribution)),
  );
  const format = new Intl.NumberFormat("en", { maximumFractionDigits: 4 });
  return (
    <section>
      <h3>Model Explanation Factors</h3>
      <p className="warning-muted">
        Bars compare the absolute contribution of factors within this
        prediction. Values show raw signed contributions.
      </p>
      {factors.length === 0 ? (
        <p className="warning-muted">
          No explanation factors are available for this prediction.
        </p>
      ) : (
        <ul className="warning-explanations">
          {factors.map((factor, index) => (
            <li key={`${factor.feature}-${index}`}>
              <div>
                <strong>{factor.label || readable(factor.feature)}</strong>
                <span>
                  Value {format.format(factor.value)} · Contribution{" "}
                  <b>
                    {factor.contribution > 0 ? "+" : ""}
                    {format.format(factor.contribution)}
                  </b>
                </span>
              </div>
              <div
                className={`warning-contribution ${factor.contribution < 0 ? "is-negative" : ""}`}
                aria-hidden="true"
              >
                <span
                  style={{
                    width: `${max ? (Math.abs(factor.contribution) / max) * 100 : 0}%`,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
