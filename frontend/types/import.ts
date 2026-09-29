export type ImportStatus = "UPLOADED" | "VALIDATING" | "IMPORTED" | "FAILED";

export interface ImportJob {
  id: string;
  uploaded_by: string;
  filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  status: ImportStatus;
  created_at: string;
  completed_at: string | null;
}

export interface ImportJobPage {
  items: ImportJob[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ImportValidationError {
  id: string;
  import_job_id: string;
  row_number: number;
  field_name: string | null;
  error_code: string;
  error_message: string;
  created_at: string;
}

export interface ImportErrorPage {
  items: ImportValidationError[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
