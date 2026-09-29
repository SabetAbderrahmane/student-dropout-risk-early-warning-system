export interface Student {
  id: string;
  student_number: string;
  name: string;
  gender: string | null;
  created_at: string;
  updated_at: string;
}

export interface StudentPage {
  items: Student[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface StudentInput {
  student_number: string;
  name: string;
  gender: string | null;
}

export interface AdmissionRecord {
  id: string;
  student_id: string;
  admission_method: string;
  admission_grade: number;
  previous_qualification: string;
  previous_qualification_grade: number;
  created_at: string;
  updated_at: string;
}

export type AdmissionInput = Omit<
  AdmissionRecord,
  "id" | "student_id" | "created_at" | "updated_at"
>;
export interface FirstSemesterRecord {
  id: string;
  student_id: string;
  credited_units: number;
  enrolled_units: number;
  evaluations: number;
  approved_units: number;
  average_grade: number;
  created_at: string;
  updated_at: string;
}

export type FirstSemesterInput = Omit<
  FirstSemesterRecord,
  "id" | "student_id" | "created_at" | "updated_at"
>;
