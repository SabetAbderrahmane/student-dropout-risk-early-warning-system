import type { ImportJob } from "./import";

export type StagedImportStatus =
  "REVIEW_REQUIRED" | "READY_TO_COMMIT" | "COMMITTED" | "CANCELLED";
export interface StagedIssue {
  row_number: number;
  field_name: string | null;
  error_code: string;
  error_message: string;
}
export interface StagedRow {
  id: string;
  batch_id: string;
  row_number: number;
  version: number;
  original_values: Record<string, string>;
  edited_values: Record<string, string>;
  included: boolean;
  is_valid: boolean;
  issues: StagedIssue[];
}
export interface StagedBatch {
  id: string;
  uploaded_by: string;
  filename: string;
  status: StagedImportStatus;
  version: number;
  total_rows: number;
  included_rows: number;
  excluded_rows: number;
  valid_rows: number;
  invalid_rows: number;
  valid_included_rows: number;
  invalid_included_rows: number;
  validation_issue_count: number;
  included_issue_count: number;
  last_commit_error: string | null;
  import_job_id: string | null;
  import_job: ImportJob | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
}
export interface PageMetadata {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
export interface StagedBatchPage extends PageMetadata {
  items: StagedBatch[];
}
export interface StagedRowPage extends PageMetadata {
  items: StagedRow[];
  batch_version: number;
}
export interface StagedBatchParams {
  page: number;
  page_size: number;
  status?: StagedImportStatus;
}
export interface StagedRowParams {
  page: number;
  page_size: number;
  search?: string;
  included?: boolean;
  valid?: boolean;
}
export interface StagedVersionRequest {
  expected_batch_version: number;
}
export interface StagedCorrectionRequest extends StagedVersionRequest {
  expected_row_version: number;
  values?: Record<string, string>;
  included?: boolean;
}
export interface StagedCorrectionResponse {
  batch: StagedBatch;
  row: StagedRow;
}
export interface StagedAction {
  id: string;
  batch_id: string;
  row_id: string | null;
  actor_id: string;
  action: string;
  batch_version: number;
  changes: Record<string, unknown>;
  created_at: string;
}
export interface StagedActionPage extends PageMetadata {
  items: StagedAction[];
}
