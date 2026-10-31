# CIT dataset guide (verified against `cit_public.json`, dataset_id `cit-public-v1`)
Source of truth: the official starter pack, preserved at `source_files/CrunchWeek_StarterPack__1_.zip`, extracted to
`source_files/extracted/CrunchWeek_StarterPack/` (`README.md`, `validator.py`, `data/cit_public.json`, `data/csv/*.csv`,
`examples/*`). Machine-readable report: `docs/dataset_inspection.json` (regenerate: `python scripts/inspect_dataset.py`).
CSVs carry exactly the same records/IDs as the JSON; only the JSON is imported (no duplicates).

| Entity | Count | Key fields | Relationships |
|---|---|---|---|
| rooms | 27 | id, type, capacity, features, accessible, allowed_uses | type in 10 values; labs allow `lab`, SH/OAT never take classes |
| room_unavailability | 2 | room_id, day, periods | LH-4 all THU; CR-103 FRI P6-9 |
| faculty | 40 | id, max_hours_per_day (4 for all), unavailable[], preferences[] (only `avoid`) | F26 needs accessible |
| student_groups | 14 | id, year, size, needs_accessible | ME-2 needs accessible |
| courses | 62 | id, lecture_hours, tutorial_hours, lab_blocks | reference only |
| sessions | 189 (153 lecture, 9 tutorial, 27 lab) | id, course_id, kind, groups[], faculty_id, size, duration (1 or 3), room_types[], needs_accessible, basket_slot, fixed_slot | 20 need accessible rooms; baskets OEB-1..3 (3 sessions each); no fixed slots in this data |
| booking_requests | 25 (24 active + BR-04 cancelled) | id, submitted_at, role, requested_category, attendance, duration_periods, windows[], room_types[], needs[], requested_room, mandatory_for_groups[], series_id, raw_text | roles: admin 5, club 15, faculty 2, dept coordinator 3 |
| cancellations | 1 | request_id | BR-04 |
| exams | 41 | id, course_ids[], groups[], size, duration_hours (all 2) | one multi-course basket exam |

Enumerations: kinds `lecture|tutorial|lab`; features `ac, computers, pa_system, power_benches, projector, stage` (+ `accessible` as a
need); priority order `exam > regular_session > institute_event > guest_lecture > department_event > club_event`; role caps
admin->institute_event, faculty->guest_lecture, dept coordinator->department_event, club->club_event.

Time model: MON-FRI, P1-P9 teaching (P5|lunch|P6), P10-P13 event-only; labs start P2/P6; exam week MON-SAT, AM 09:30-11:30, PM 14:00-16:00,
exam seats = capacity // 2.

## Discrepancies and quirks (documented, not hidden)
- BR-14 requests room `LHC-5`, which does not exist (treated as a wish).
- BR-17's window WED P13-P14 runs past P13, the last event period.
- BR-15 is a club asking for `institute_event`; the cap makes it `club_event`.
- The validator does not check `allowed_uses` for sessions, exam `duration_hours`, or room closures for exams; the app enforces the
  first and third as stricter rules.
- `README` says exams are optional in `schedule_after.json`; the app still includes them.
