import Link from "next/link";
import { ThemeControl } from "@/components/theme/theme-control";

export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero-card">
        <div className="home-theme-row">
          <ThemeControl />
        </div>
        <div className="eyebrow">Academic risk and student support</div>
        <h1>Student Dropout Risk Early Warning System</h1>
        <p className="lead">
          Review student academic records, assess enrollment and first-semester
          risk, and coordinate advisor-led support with a recorded case history.
        </p>
        <div className="status-row" aria-label="Application services">
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
