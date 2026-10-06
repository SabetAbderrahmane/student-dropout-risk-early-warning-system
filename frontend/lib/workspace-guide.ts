import type { IconName } from "@/components/dashboard/icon";
import type { UserRole } from "@/types/auth";

export type GuideStep = {
  id: string;
  href: string;
  label: string;
  icon: IconName;
  title: string;
  intro: string;
  tasks: string[];
  tip: string;
};
export const WORKSPACE_STEPS: GuideStep[] = [
  {
    id: "overview",
    href: "/dashboard",
    label: "Overview",
    icon: "grid",
    title: "See where support is needed",
    intro:
      "Start your day with the overview. It brings together academic risk, warnings and the support workload.",
    tasks: [
      "Check the high-risk and pending-review totals.",
      "Use Students Requiring Attention to open an individual record.",
      "Check due and overdue follow-ups before planning new work.",
    ],
    tip: "Dashboard totals cover the institution. They are not a personal advisor task count.",
  },
  {
    id: "students",
    href: "/students",
    label: "Students",
    icon: "students",
    title: "Understand the student behind the risk",
    intro:
      "The registry connects academic records with prediction evidence and the student's support history.",
    tasks: [
      "Search by student name or student number.",
      "Filter by risk, warning state or prediction readiness.",
      "Open the full student record to review academic data, warnings, interventions and the history timeline.",
    ],
    tip: "Not Ready means required model inputs are missing. It does not mean the student is high risk.",
  },
  {
    id: "imports",
    href: "/imports",
    label: "Data import",
    icon: "import",
    title: "Review records before importing",
    intro:
      "A CSV is staged for review first. Student records are saved only when you confirm the reviewed import.",
    tasks: [
      "Download the CSV Schema Template and use the official columns.",
      "Stage the file, inspect validation issues, then correct or exclude individual rows.",
      "When the batch is Ready to Commit, check the included rows and confirm the commit. Keep the receipt for your records.",
    ],
    tip: "A staged upload is not a completed import. Only included, valid rows can be committed.",
  },
  {
    id: "predictions",
    href: "/predictions",
    label: "Risk predictions",
    icon: "activity",
    title: "Use model evidence to inform a decision",
    intro:
      "Review model results alongside the student's academic record. The prediction is a signal for support, not a final decision.",
    tasks: [
      "Check the latest risk probability and classification.",
      "Open a prediction to inspect the explanation factors and source snapshot.",
      "Compare previous predictions in the student's dossier to understand changes over time.",
    ],
    tip: "Only students with complete required inputs can be assessed. Generating predictions creates new prediction records.",
  },
  {
    id: "warnings",
    href: "/warnings",
    label: "Warning triage",
    icon: "warning",
    title: "Review each warning individually",
    intro:
      "Warnings turn model signals into an advisor review queue. Every review needs context and a written rationale.",
    tasks: [
      "Filter the queue by priority or Pending Review.",
      "Open the warning and compare the model explanation with the student record.",
      "The assigned advisor confirms or dismisses it with a note. A confirmed warning can lead to an intervention.",
    ],
    tip: "A confirmed warning and an intervention are separate records. Confirming a warning does not automatically create a case.",
  },
  {
    id: "interventions",
    href: "/interventions",
    label: "Interventions",
    icon: "casework",
    title: "Turn a confirmed concern into a support plan",
    intro:
      "Each intervention links a student and a confirmed warning to a named advisor and a practical plan.",
    tasks: [
      "Choose a support type, case owner, priority and target date.",
      "Move the case through the allowed statuses and add notes as support progresses.",
      "Schedule follow-ups, then record the outcome when completing the intervention.",
    ],
    tip: "P1 is urgent, P2 is elevated and P3 is standard. Completed and cancelled cases retain their history.",
  },
  {
    id: "follow-ups",
    href: "/follow-ups",
    label: "Follow-ups",
    icon: "calendar",
    title: "Close the loop with an outcome",
    intro:
      "The queue helps you keep contact commitments and record what happened after each support action.",
    tasks: [
      "Begin with Overdue or Due, then select a record to see the details.",
      "Reschedule when needed, or complete the contact with an outcome and notes.",
      "Schedule another follow-up from the completion form if further support is needed.",
    ],
    tip: "Completing a follow-up does not automatically complete its intervention. Review the case outcome separately.",
  },
];
export function guideSteps(role: UserRole) {
  return WORKSPACE_STEPS.filter(
    (step) => role !== "ACADEMIC_ADVISOR" || step.id !== "imports",
  );
}
export function roleAdvice(role: UserRole, step: GuideStep) {
  if (role === "SYSTEM_ADMIN")
    return "Your system administrator account can inspect academic records. An academic administrator manages imports and records; assigned advisors handle warning reviews.";
  if (role === "ACADEMIC_ADVISOR")
    return step.id === "warnings"
      ? "You can review warnings assigned to you. Ask an academic administrator to assign unowned warnings."
      : step.id === "students" || step.id === "predictions"
        ? "Your academic data and model views are read-only. Ask an academic administrator to correct missing source records."
        : "You can manage cases and follow-ups assigned to you. Institution-wide queue entries may belong to other advisors.";
  return step.id === "warnings"
    ? "You can assign warnings to active advisors. Only the assigned advisor can submit the warning review."
    : "Your academic administrator account can manage student records, run assessments, and coordinate support across advisors.";
}
