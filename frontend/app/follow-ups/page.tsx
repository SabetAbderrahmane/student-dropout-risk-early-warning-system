import { Suspense } from "react";
import { FollowUpsWorkspace } from "@/components/follow-ups/follow-ups-workspace";
import "../dashboard/dashboard.css";
import "../warnings/warnings.css";
import "../students/dossier.css";
import "./follow-ups.css";

export default function FollowUpsPage() {
  return (
    <Suspense
      fallback={
        <main className="follow-route-loading" role="status">
          Loading follow-ups workspace…
        </main>
      }
    >
      <FollowUpsWorkspace />
    </Suspense>
  );
}
