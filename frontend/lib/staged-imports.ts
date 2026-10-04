import { ApiError } from "./api";
import type { StagedBatch, StagedImportStatus } from "@/types/staged-import";
export const STAGED_STATUSES: StagedImportStatus[] = [
  "REVIEW_REQUIRED",
  "READY_TO_COMMIT",
  "COMMITTED",
  "CANCELLED",
];
export const isMutableBatch = (batch: StagedBatch) =>
  batch.status === "REVIEW_REQUIRED" || batch.status === "READY_TO_COMMIT";
export function stagedError(caught: unknown): string {
  if (!(caught instanceof ApiError))
    return caught instanceof Error
      ? caught.message
      : "The request could not be completed. Please retry.";
  let message = caught.message;
  if (caught.status === 403) message = `Permission denied. ${message}`;
  if (caught.status === 404)
    message = `This batch or row is no longer available. ${message}`;
  if (caught.status === 413)
    message = `The CSV exceeds the backend upload limit of 5 MiB. ${message}`;
  if (caught.status === 409)
    message = `${message} Latest batch and rows will be reloaded. No edit will be automatically replayed.`;
  if (caught.details && typeof caught.details === "object") {
    if (
      "invalid_included_rows" in caught.details &&
      typeof caught.details.invalid_included_rows === "number"
    )
      message += ` Invalid included rows: ${caught.details.invalid_included_rows}.`;
    if (
      "version" in caught.details &&
      typeof caught.details.version === "number"
    )
      message += ` Batch revision: ${caught.details.version}.`;
  }
  if (Array.isArray(caught.details)) {
    const messages = caught.details.flatMap((value: unknown) =>
      value &&
      typeof value === "object" &&
      "message" in value &&
      typeof value.message === "string"
        ? [value.message]
        : [],
    );
    if (messages.length) message += ` ${messages.join(" ")}`;
  }
  return message;
}
