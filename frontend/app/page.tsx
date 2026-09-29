import Link from "next/link";

export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero-card">
        <div className="eyebrow">Phase 1 &amp; 2 foundation</div>
        <h1>Student Dropout Risk Early Warning System</h1>
        <p className="lead">
          The secure foundation and student academic domain are ready. Predictions, warnings,
          interventions, and dashboards remain intentionally deferred to later phases.
        </p>
        <div className="status-row" aria-label="Foundation services">
          <span>Next.js</span>
          <span>FastAPI</span>
          <span>PostgreSQL</span>
          <span>JWT + RBAC</span>
          <span>Student records</span>
        </div>
        <Link className="primary-link" href="/login">
          Sign in
        </Link>
      </section>
    </main>
  );
}
