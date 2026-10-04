import { ActionModal } from "@/components/dashboard/action-modal";
import type { CurrentModel } from "@/types/prediction";
import { ModelMetadataCard, RiskThresholdCard } from "./model-metadata-card";
export function ModelDetailsModal({
  model,
  onClose,
}: {
  model: CurrentModel;
  onClose: () => void;
}) {
  return (
    <ActionModal
      title="Model Details"
      className="prediction-model-modal"
      busy={false}
      onClose={onClose}
    >
      <ModelMetadataCard model={model} loading={false} />
      <RiskThresholdCard model={model} loading={false} />
    </ActionModal>
  );
}
