import { StudentDossier } from "@/components/dossier/student-dossier";
import "../../dashboard/dashboard.css";
import "../../warnings/warnings.css";
import "../dossier.css";

export default async function StudentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <StudentDossier key={id} studentId={id} />;
}
