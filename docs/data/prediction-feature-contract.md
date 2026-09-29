# Prediction feature contract (UCI dataset 697)

This document freezes the Phase 4A prediction inputs before CSV import or model work.
The authoritative source is the UCI Machine Learning Repository dataset **Predict
Students' Dropout and Academic Success**, dataset ID 697, last updated by UCI on
2024-02-26. UCI reports 36 feature variables and one target variable.

Prediction timing is the end of the first semester. The ordered contract therefore
contains **30 inputs**: 21 enrollment inputs, 6 first-semester inputs, and 3
macroeconomic inputs. All 6 second-semester variables and the single target are
excluded. The machine-readable source of truth is
`backend/app/ml/feature_schema.py`.

## Target contract

The UCI `Target` remains an outcome and is never an input. Future modeling code must
encode it exactly as follows:

| UCI value | Binary value | Meaning |
|---|---:|---|
| `Dropout` | 1 | positive class |
| `Graduate` | 0 | non-dropout |
| `Enrolled` | 0 | non-dropout |

## System-only fields

`students.id` (internal UUID), `students.student_number`, `students.name`, and the
legacy/display field `students.gender` are operational metadata, not ML inputs. The
official UCI gender input is stored separately as `students.gender_code`. Record IDs,
timestamps, and foreign keys are also system-only. Future import, preprocessing, and
inference code must select features only from `PREDICTION_FEATURES`; it must never
infer model inputs by enumerating database columns.

## Canonical data dictionary

`Required` means required for a prediction-ready row, not required to create or
update Phase 3 API resources. New database/API fields remain nullable for backward
compatibility.

| Official UCI variable | Normalized application field | Description | Type / kind | Official code mapping | Source stage | Eligibility | Storage | Required | Validation notes |
|---|---|---|---|---|---|---|---|---|---|
| Marital Status | `marital_status_code` | Student marital status | integer / categorical | M1 | ENROLLMENT | INCLUDED | `students.marital_status_code` | yes | exact codes only |
| Application mode | `application_mode_code` | Admission application route | integer / categorical | M2 | ENROLLMENT | INCLUDED | `admission_records.application_mode_code` | yes | exact codes only |
| Application order | `application_order` | Choice order in the application | integer / numeric | n/a | ENROLLMENT | INCLUDED | `admission_records.application_order` | yes | 0 (first choice) through 9 (last choice) |
| Course | `course_code` | Enrolled course | integer / categorical | M3 | ENROLLMENT | INCLUDED | `admission_records.course_code` | yes | exact codes only |
| Daytime/evening attendance | `daytime_evening_attendance` | Attendance schedule | integer / binary | 1 daytime; 0 evening | ENROLLMENT | INCLUDED | `admission_records.daytime_evening_attendance` | yes | only 0 or 1 |
| Previous qualification | `previous_qualification_code` | Qualification held before admission | integer / categorical | M4 | ENROLLMENT | INCLUDED | `admission_records.previous_qualification_code` | yes | exact codes only |
| Previous qualification (grade) | `previous_qualification_grade` | Grade of prior qualification | continuous / numeric | n/a | ENROLLMENT | INCLUDED | `admission_records.previous_qualification_grade` | yes | 0 through 200 |
| Nacionality | `nationality_code` | Nationality (official UCI spelling retained at source boundary) | integer / categorical | M5 | ENROLLMENT | INCLUDED | `students.nationality_code` | yes | exact codes only |
| Mother's qualification | `mother_qualification_code` | Mother's education level | integer / categorical | M6 | ENROLLMENT | INCLUDED | `admission_records.mother_qualification_code` | yes | exact codes only |
| Father's qualification | `father_qualification_code` | Father's education level | integer / categorical | M7 | ENROLLMENT | INCLUDED | `admission_records.father_qualification_code` | yes | exact codes only |
| Mother's occupation | `mother_occupation_code` | Mother's occupation | integer / categorical | M8 | ENROLLMENT | INCLUDED | `admission_records.mother_occupation_code` | yes | exact codes only |
| Father's occupation | `father_occupation_code` | Father's occupation | integer / categorical | M9 | ENROLLMENT | INCLUDED | `admission_records.father_occupation_code` | yes | exact codes only |
| Admission grade | `admission_grade` | Admission grade | continuous / numeric | n/a | ENROLLMENT | INCLUDED | `admission_records.admission_grade` | yes | 0 through 200 |
| Displaced | `displaced` | Student is displaced | integer / binary | 1 yes; 0 no | ENROLLMENT | INCLUDED | `students.displaced` | yes | only 0 or 1 |
| Educational special needs | `educational_special_needs` | Student has educational special needs | integer / binary | 1 yes; 0 no | ENROLLMENT | INCLUDED | `students.educational_special_needs` | yes | only 0 or 1 |
| Debtor | `debtor` | Student is a debtor | integer / binary | 1 yes; 0 no | ENROLLMENT | INCLUDED | `students.debtor` | yes | only 0 or 1 |
| Tuition fees up to date | `tuition_fees_up_to_date` | Tuition fees are current | integer / binary | 1 yes; 0 no | ENROLLMENT | INCLUDED | `students.tuition_fees_up_to_date` | yes | only 0 or 1 |
| Gender | `gender_code` | Official coded gender | integer / binary | 1 male; 0 female | ENROLLMENT | INCLUDED | `students.gender_code` | yes | only 0 or 1; distinct from display `gender` |
| Scholarship holder | `scholarship_holder` | Student holds a scholarship | integer / binary | 1 yes; 0 no | ENROLLMENT | INCLUDED | `students.scholarship_holder` | yes | only 0 or 1 |
| Age at enrollment | `age_at_enrollment` | Age when enrolled | integer / numeric | n/a | ENROLLMENT | INCLUDED | `students.age_at_enrollment` | yes | nonnegative; UCI defines no maximum |
| International | `international_student` | International-student indicator | integer / binary | 1 yes; 0 no | ENROLLMENT | INCLUDED | `students.international_student` | yes | only 0 or 1 |
| Curricular units 1st sem (credited) | `first_semester_credited_units` | Units credited in semester 1 | integer / numeric | n/a | FIRST_SEMESTER | INCLUDED | `first_semester_records.credited_units` | yes | nonnegative count |
| Curricular units 1st sem (enrolled) | `first_semester_enrolled_units` | Units enrolled in semester 1 | integer / numeric | n/a | FIRST_SEMESTER | INCLUDED | `first_semester_records.enrolled_units` | yes | nonnegative count |
| Curricular units 1st sem (evaluations) | `first_semester_evaluations` | Evaluations in semester 1 | integer / numeric | n/a | FIRST_SEMESTER | INCLUDED | `first_semester_records.evaluations` | yes | nonnegative count |
| Curricular units 1st sem (approved) | `first_semester_approved_units` | Units approved in semester 1 | integer / numeric | n/a | FIRST_SEMESTER | INCLUDED | `first_semester_records.approved_units` | yes | nonnegative count |
| Curricular units 1st sem (grade) | `first_semester_average_grade` | Average grade in semester 1 | continuous / numeric | n/a | FIRST_SEMESTER | INCLUDED | `first_semester_records.average_grade` | yes | 0 through 20; UCI labels the type Integer but observed data are decimal, so application type is continuous |
| Curricular units 1st sem (without evaluations) | `first_semester_without_evaluations` | Units without evaluations in semester 1 | integer / numeric | n/a | FIRST_SEMESTER | INCLUDED | `first_semester_records.without_evaluations` | yes | nonnegative count |
| Curricular units 2nd sem (credited) | `second_semester_credited_units` | Units credited in semester 2 | integer / numeric | n/a | SECOND_SEMESTER | EXCLUDED_SECOND_SEMESTER | not stored | no | anti-leakage exclusion |
| Curricular units 2nd sem (enrolled) | `second_semester_enrolled_units` | Units enrolled in semester 2 | integer / numeric | n/a | SECOND_SEMESTER | EXCLUDED_SECOND_SEMESTER | not stored | no | anti-leakage exclusion |
| Curricular units 2nd sem (evaluations) | `second_semester_evaluations` | Evaluations in semester 2 | integer / numeric | n/a | SECOND_SEMESTER | EXCLUDED_SECOND_SEMESTER | not stored | no | anti-leakage exclusion |
| Curricular units 2nd sem (approved) | `second_semester_approved_units` | Units approved in semester 2 | integer / numeric | n/a | SECOND_SEMESTER | EXCLUDED_SECOND_SEMESTER | not stored | no | anti-leakage exclusion |
| Curricular units 2nd sem (grade) | `second_semester_average_grade` | Average grade in semester 2 | continuous / numeric | n/a | SECOND_SEMESTER | EXCLUDED_SECOND_SEMESTER | not stored | no | anti-leakage exclusion |
| Curricular units 2nd sem (without evaluations) | `second_semester_without_evaluations` | Units without evaluations in semester 2 | integer / numeric | n/a | SECOND_SEMESTER | EXCLUDED_SECOND_SEMESTER | not stored | no | anti-leakage exclusion; UCI description mistakenly says first semester |
| Unemployment rate | `unemployment_rate` | Unemployment rate (%) at enrollment context | continuous / numeric | n/a | MACROECONOMIC | INCLUDED | `admission_records.unemployment_rate` | yes | no source-defined range |
| Inflation rate | `inflation_rate` | Inflation rate (%) at enrollment context | continuous / numeric | n/a | MACROECONOMIC | INCLUDED | `admission_records.inflation_rate` | yes | no source-defined range; negative values permitted |
| GDP | `gdp` | GDP value at enrollment context | continuous / numeric | n/a | MACROECONOMIC | INCLUDED | `admission_records.gdp` | yes | no source-defined range; negative values permitted |
| Target | `target` | Final outcome: Dropout, Enrolled, or Graduate | categorical / target | Dropout; Enrolled; Graduate | TARGET | EXCLUDED_TARGET | not stored | no | outcome only; binary mapping defined above |

Macroeconomic fields are stored on `admission_records` because they describe the
economic context at enrollment and do not belong to the student's enduring identity
or first-semester performance. No extra flat ML table is introduced.

## Official categorical mappings

The labels below reproduce the UCI metadata. Codes are stored as integers so the
mapping is reversible.

### M1 — Marital Status

1 single; 2 married; 3 widower; 4 divorced; 5 facto union; 6 legally separated.

### M2 — Application mode

1 1st phase - general contingent; 2 Ordinance No. 612/93; 5 1st phase - special
contingent (Azores Island); 7 holders of other higher courses; 10 Ordinance No.
854-B/99; 15 international student (bachelor); 16 1st phase - special contingent
(Madeira Island); 17 2nd phase - general contingent; 18 3rd phase - general
contingent; 26 Ordinance No. 533-A/99 item b2 (Different Plan); 27 Ordinance No.
533-A/99 item b3 (Other Institution); 39 over 23 years old; 42 transfer; 43 change
of course; 44 technological specialization diploma holders; 51 change of
institution/course; 53 short cycle diploma holders; 57 change of
institution/course (International).

### M3 — Course

33 Biofuel Production Technologies; 171 Animation and Multimedia Design; 8014
Social Service (evening attendance); 9003 Agronomy; 9070 Communication Design; 9085
Veterinary Nursing; 9119 Informatics Engineering; 9130 Equinculture; 9147
Management; 9238 Social Service; 9254 Tourism; 9500 Nursing; 9556 Oral Hygiene; 9670
Advertising and Marketing Management; 9773 Journalism and Communication; 9853
Basic Education; 9991 Management (evening attendance).

### M4 — Previous qualification

1 secondary education; 2 higher education - bachelor's degree; 3 higher education
- degree; 4 higher education - master's; 5 higher education - doctorate; 6
frequency of higher education; 9 12th year not completed; 10 11th year not
completed; 12 other - 11th year; 14 10th year; 15 10th year not completed; 19 basic
education 3rd cycle or equivalent; 38 basic education 2nd cycle or equivalent; 39
technological specialization course; 40 higher education - degree (1st cycle); 42
professional higher technical course; 43 higher education - master (2nd cycle).

### M5 — Nacionality

1 Portuguese; 2 German; 6 Spanish; 11 Italian; 13 Dutch; 14 English; 17 Lithuanian;
21 Angolan; 22 Cape Verdean; 24 Guinean; 25 Mozambican; 26 Santomean; 32 Turkish;
41 Brazilian; 62 Romanian; 100 Moldova (Republic of); 101 Mexican; 103 Ukrainian;
105 Russian; 108 Cuban; 109 Colombian.

### M6 — Mother's qualification

1 secondary education - 12th year or equivalent; 2 bachelor's degree; 3 degree; 4
master's; 5 doctorate; 6 frequency of higher education; 9 12th year not completed;
10 11th year not completed; 11 7th year (old); 12 other - 11th year; 14 10th year;
18 general commerce course; 19 basic education 3rd cycle or equivalent; 22
technical-professional course; 26 7th year; 27 2nd cycle general high school; 29 9th
year not completed; 30 8th year; 34 unknown; 35 cannot read or write; 36 can read
without 4th year; 37 basic education 1st cycle or equivalent; 38 basic education
2nd cycle or equivalent; 39 technological specialization; 40 degree (1st cycle);
41 specialized higher studies; 42 professional higher technical course; 43 master
(2nd cycle); 44 doctorate (3rd cycle).

### M7 — Father's qualification

M6 codes plus: 13 2nd year complementary high school; 20 complementary high school;
25 complementary high school not concluded; 31 general administration and commerce;
33 supplementary accounting and administration. Code 18 is general commerce course
and all other shared codes have the M6 meaning.

### M8 — Mother's occupation

0 student; 1 legislative/executive representatives and managers; 2 intellectual and
scientific specialists; 3 intermediate technicians; 4 administrative staff; 5
personal services/security/sellers; 6 skilled agriculture/fisheries/forestry; 7
industry/construction/crafts; 8 machine operators/assembly; 9 unskilled workers; 10
armed forces; 90 other; 99 blank; 122 health professionals; 123 teachers; 125 ICT
specialists; 131 science/engineering intermediate technicians; 132 health
intermediate technicians; 134 legal/social/sports/cultural intermediate technicians;
141 office/secretarial/data processing; 143 data/accounting/statistical/financial/
registry operators; 144 other administrative support; 151 personal services; 152
sellers; 153 personal care; 171 construction workers except electricians; 173
printing/precision/jewelry/artisans; 175 food/wood/clothing/other crafts; 191 cleaning;
192 unskilled agriculture/fisheries/forestry; 193 unskilled extractive/construction/
manufacturing/transport; 194 meal preparation assistants.

### M9 — Father's occupation

0 student; 1 legislative/executive representatives and managers; 2 intellectual and
scientific specialists; 3 intermediate technicians; 4 administrative staff; 5
personal services/security/sellers; 6 skilled agriculture/fisheries/forestry; 7
industry/construction/crafts; 8 machine operators/assembly; 9 unskilled workers; 10
armed forces; 90 other; 99 blank; 101 armed forces officers; 102 armed forces
sergeants; 103 other armed forces; 112 administrative/commercial directors; 114
hotel/catering/trade/service directors; 121 physical science/math/engineering
specialists; 122 health professionals; 123 teachers; 124 finance/accounting/
administrative/public-relations specialists; 131 science/engineering intermediate
technicians; 132 health intermediate technicians; 134 legal/social/sports/cultural
intermediate technicians; 135 ICT technicians; 141 office/secretarial/data
processing; 143 data/accounting/statistical/financial/registry operators; 144 other
administrative support; 151 personal services; 152 sellers; 153 personal care; 154
protection/security; 161 market-oriented agriculture/animal production; 163
subsistence farmers/fishers/hunters/gatherers; 171 construction except electricians;
172 metallurgy/metalworking; 174 electrical/electronics; 175 food/wood/clothing/other
crafts; 181 fixed plant/machine operators; 182 assembly; 183 vehicle/mobile equipment
drivers; 192 unskilled agriculture/fisheries/forestry; 193 unskilled extractive/
construction/manufacturing/transport; 194 meal preparation assistants; 195 street
vendors and service providers.

## Source ambiguities and decisions

- UCI's official source name is misspelled `Nacionality`; the application normalizes
  it to `nationality_code` while retaining the exact official name in the contract.
- UCI types both semester grade variables as `Integer`, but defines an average on a
  0–20 scale and the official data contains decimals. The application uses a decimal
  numeric type without changing the official source name.
- UCI's description for second-semester “without evaluations” says first semester.
  The variable name and position identify it as second semester, so it is excluded.
- UCI defines no safe universal bounds for unemployment, inflation, or GDP. No
  arbitrary bounds are imposed.
- Phase 3's text fields `admission_method`, `previous_qualification`, and `gender`
  remain for compatibility. Their new `*_code` counterparts are the ML inputs.

## Source

- UCI dataset 697: <https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success>
- DOI: <https://doi.org/10.24432/C5MC89>
