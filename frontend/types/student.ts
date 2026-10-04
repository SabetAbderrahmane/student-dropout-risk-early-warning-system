export interface StudentPredictionFields {
  marital_status_code: number | null;
  nationality_code: number | null;
  displaced: number | null;
  educational_special_needs: number | null;
  debtor: number | null;
  tuition_fees_up_to_date: number | null;
  gender_code: number | null;
  scholarship_holder: number | null;
  age_at_enrollment: number | null;
  international_student: number | null;
}

export interface Student extends StudentPredictionFields {
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

export interface StudentInput extends Partial<StudentPredictionFields> {
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
  application_mode_code?: number | null;
  application_order?: number | null;
  course_code?: number | null;
  daytime_evening_attendance?: number | null;
  previous_qualification_code?: number | null;
  mother_qualification_code?: number | null;
  father_qualification_code?: number | null;
  mother_occupation_code?: number | null;
  father_occupation_code?: number | null;
  unemployment_rate?: number | null;
  inflation_rate?: number | null;
  gdp?: number | null;
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
  without_evaluations?: number | null;
  created_at: string;
  updated_at: string;
}

export type FirstSemesterInput = Omit<
  FirstSemesterRecord,
  "id" | "student_id" | "created_at" | "updated_at"
>;
