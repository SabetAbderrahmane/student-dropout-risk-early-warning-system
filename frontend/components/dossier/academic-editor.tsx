import { ActionModal } from "@/components/dashboard/action-modal";
import { updateStudent, saveAdmission, saveFirstSemester } from "@/lib/api";
import { readable } from "@/lib/dashboard";
import type { StudentProfile } from "@/types/registry";
import { DossierForm, type DossierField } from "./dossier-form";

export type AcademicSection = "student" | "admission" | "semester_one";
const studentNumbers = [
  "marital_status_code",
  "nationality_code",
  "displaced",
  "educational_special_needs",
  "debtor",
  "tuition_fees_up_to_date",
  "gender_code",
  "scholarship_holder",
  "age_at_enrollment",
  "international_student",
];
const admissionNumbers = [
  "application_mode_code",
  "application_order",
  "course_code",
  "daytime_evening_attendance",
  "previous_qualification_code",
  "mother_qualification_code",
  "father_qualification_code",
  "mother_occupation_code",
  "father_occupation_code",
  "unemployment_rate",
  "inflation_rate",
  "gdp",
];
export function AcademicEditor({
  section,
  profile,
  token,
  busy,
  onClose,
  mutate,
}: {
  section: AcademicSection;
  profile: StudentProfile;
  token: string;
  busy: boolean;
  onClose: () => void;
  mutate: (work: () => Promise<unknown>) => Promise<string | null>;
}) {
  const text = (key: string, optional = false): DossierField => ({
    key,
    label: readable(key),
    optional,
  });
  const number = (key: string, optional = false): DossierField => ({
    ...text(key, optional),
    type: "number",
  });
  const fields =
    section === "student"
      ? [
          text("student_number"),
          text("name"),
          text("gender", true),
          ...studentNumbers.map((key) => number(key, true)),
        ]
      : section === "admission"
        ? [
            text("admission_method"),
            number("admission_grade"),
            text("previous_qualification"),
            number("previous_qualification_grade"),
            ...admissionNumbers.map((key) => number(key, true)),
          ]
        : [
            ...[
              "credited_units",
              "enrolled_units",
              "evaluations",
              "approved_units",
              "average_grade",
            ].map((key) => number(key)),
            number("without_evaluations", true),
          ];
  const record: Record<string, unknown> = { ...profile[section] };
  const initial = Object.fromEntries(
    fields.map((field) => [
      field.key,
      record[field.key] == null ? "" : String(record[field.key]),
    ]),
  );
  const optionalNumbers = (keys: string[], values: Record<string, string>) =>
    Object.fromEntries(
      keys.map((key) => [
        key,
        values[key] === "" || values[key] === undefined
          ? null
          : Number(values[key]),
      ]),
    );
  return (
    <ActionModal
      title={`Edit ${section === "semester_one" ? "First-Semester Record" : readable(section)}`}
      busy={busy}
      onClose={onClose}
      className="dossier-modal"
    >
      <p className="dossier-muted">
        Enter recorded source values. Empty optional fields remain unrecorded.
        Numeric codes are validated by the backend.
      </p>
      <DossierForm
        fields={fields}
        initial={initial}
        onCancel={onClose}
        onSubmit={async (values) => {
          const id = profile.student.id;
          const result = await mutate(() =>
            section === "student"
              ? updateStudent(token, id, {
                  student_number: values.student_number,
                  name: values.name,
                  gender: values.gender || null,
                  ...optionalNumbers(studentNumbers, values),
                })
              : section === "admission"
                ? saveAdmission(token, id, {
                    admission_method: values.admission_method,
                    admission_grade: Number(values.admission_grade),
                    previous_qualification: values.previous_qualification,
                    previous_qualification_grade: Number(
                      values.previous_qualification_grade,
                    ),
                    ...optionalNumbers(admissionNumbers, values),
                  })
                : saveFirstSemester(token, id, {
                    credited_units: Number(values.credited_units),
                    enrolled_units: Number(values.enrolled_units),
                    evaluations: Number(values.evaluations),
                    approved_units: Number(values.approved_units),
                    average_grade: Number(values.average_grade),
                    ...optionalNumbers(["without_evaluations"], values),
                  }),
          );
          if (!result) onClose();
          return result;
        }}
      />
    </ActionModal>
  );
}
