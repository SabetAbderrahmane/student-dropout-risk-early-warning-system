# Phase 7 casework decisions

- An intervention is created only through an authenticated human request after its linked warning is `CONFIRMED`. Several interventions may reference one confirmed warning.
- An Academic Advisor may create a case only from a warning assigned to them, and may initially assign that case only to themselves. Academic Admin may assign any active Academic Advisor.
- Intervention status moves `PLANNED → IN_PROGRESS → ACTION_REQUIRED`; `ACTION_REQUIRED → IN_PROGRESS` is allowed. Completion and cancellation use dedicated endpoints. Both are terminal; retrying either returns `INVALID_INTERVENTION_TRANSITION`.
- Follow-ups persist only `SCHEDULED`, `COMPLETED`, or `CANCELLED`. Effective status uses **UTC calendar days**: a scheduled item before 00:00 UTC today is `OVERDUE`; from 00:00 UTC today until 00:00 UTC tomorrow it is `DUE`; at or after 00:00 UTC tomorrow it is `SCHEDULED`. Completed and cancelled items keep their stored status regardless of date. This is derived during reads and requires no scheduler.
- Completing a follow-up with `next_follow_up_at` writes a new scheduled row in the same transaction. The completed row remains completed. The new row inherits the intervention, student, advisor, method, and purpose. The `INTERVENTION_COMPLETED` follow-up outcome is recorded as an outcome only; intervention completion requires its own explicit request and metadata.
- Cancellation requires a reason. Intervention cancellation stores it in `completion_notes`; follow-up cancellation stores it in `notes`.
