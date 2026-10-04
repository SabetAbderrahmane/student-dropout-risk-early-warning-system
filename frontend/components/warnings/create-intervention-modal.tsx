import type { WarningDetail } from "@/types/warning";
import type { InterventionInput } from "@/types/dashboard";
import { QuickInterventionModal } from "@/components/dashboard/quick-intervention-modal";

export function CreateInterventionModal({
  warning,
  onClose,
  onSubmit,
}: {
  warning: WarningDetail;
  onClose: () => void;
  onSubmit: (payload: InterventionInput) => Promise<string | null>;
}) {
  return (
    <QuickInterventionModal
      title="Create Intervention"
      student={{
        student_id: warning.student_id,
        warning_id: warning.id,
        name: warning.student_name,
        student_number: warning.student_number,
        priority: warning.priority,
        assigned_advisor: warning.assigned_advisor
          ? {
              user_id: warning.assigned_advisor.id,
              full_name: warning.assigned_advisor.full_name,
            }
          : null,
      }}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  );
}
