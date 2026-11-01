# OptiCampus requirement audit (honest status)
Legend: **PASS** implemented and tested here · **PARTIAL** implemented, not fully tested or incomplete · **FAIL** missing/broken · **NOT TESTED** not verified.
"Tested here" means executed in the build sandbox (SQLite, jsdom, mocked Gemini). Nothing was deployed; PostgreSQL, SMTP, live Gemini, real browsers were not available.

## Reproduced bug: booking submission returned HTTP 500
Root cause (reproduced): the Alembic migration predated the `notifications.kind/link` columns, so a database built with `alembic upgrade head` failed with `table notifications has no column named kind`; the booking row was already committed (separate sessions), leaving a half-saved booking. Also: booking ids were `count+1` (collision risk) and startup used `create_all`, hiding drift; Alembic's `fileConfig` muted all app loggers.
Fix: new migration (verified fresh + stale upgrade paths), startup now runs migrations and aborts on schema drift, one transaction for booking+notifications, UUID ids, logger fix. Tests: `test_fresh_migrated_schema_has_no_drift_from_models`, `test_stale_database_upgrades_to_models`, `test_booking_submission_returns_201_not_500`, `test_booking_ids_do_not_collide`, `test_failed_submission_leaves_no_half_saved_booking`. **PASS**

## Part A - official requirements
| # | Requirement | Status | Evidence / gap |
|---|---|---|---|
| 1 | 189-session timetable, solver-generated, validator-clean | PASS | CP-SAT; official CLI: 0 hard violations, soft 3 (OPTIMAL); `test_validator_and_schedule.py`, `test_solver_unit.py` |
| 2 | 41 midsems, half capacity, stored, exported | PASS | `test_bookings_exams.py`; exams persisted in DB state (`app_kv`) and `exam_runs`; faculty are not part of exam data, so no faculty conflicts apply |
| 3 | EN/Hinglish booking -> editable form -> confirm -> backend validation -> DB | PASS (rules parser) / NOT TESTED (live Gemini) | `test_parser_handles_the_briefs_english_and_hinglish_examples`, UI test "club submits a natural-language request"; manual form works with no AI |
| 4 | Priority order, admin can change, decisions + reasons, history, cancellations, 25 requests intact | PASS | `test_priority_order_admin_only_and_validated`; exam+regular classes fixed on top (decision: displacement rules depend on it); audit trail per booking |
| 5 | Disruptions: minimum movement with evidence, saved proposal, Admin-only apply, reject | PASS | `test_repair_reports_solver_evidence_not_just_a_count` (full model OPTIMAL, objective = bound, time-slot/room-only/unchanged split), `test_rejected_disruption_never_changes_the_timetable...`. Single-class-at-a-time displacement limitation remains |
| 6 | Views by group/faculty/room, course colours + legend, dashboard items | PASS / PARTIAL | views + legend + stable colours tested; "current conflicts" = Validation page; announcements via notifications |
| 7 | Faculty natural-language schedule assistant | PARTIAL | drafts availability changes only (`test_faculty_assistant_drafts...`); no "extra/moved session" requests; alternatives come from the repair preview |
| 8 | Explain decisions from real data | PARTIAL | session placement (`explain`), booking reasons, move reasons. "Why was this room not chosen" only via booking reasons |
| 9 | Dataset import + exports from the running app | PASS | `scripts/generate_exports.py` (validator-gated), admin import/export endpoints with integrity checks |
| 10 | Manual scheduling with identical hard checks | PASS (events) | `test_manual_scheduling_validates_like_automatic`; class placement is not manually editable |

## Part B - constraints: PASS (all H1-H14, S1-S6 via official validator; independent re-check in tests; local soft-score mirror equals validator).
Discrepancy noted: the brief says P9 "ends 17:00"; the dataset/validator treat P9 as starting 17:00 (ends 18:00). The validator was followed.

## Part C - roles/permissions: PASS. Four roles + read-only student; backend-enforced; self-approval blocked (`test_self_approval_blocked...`, `test_admin_cannot_approve_own_request`); admin data CRUD via Data page (JSON editor: functional, not polished).

## Part D - branding/UI
| Item | Status |
|---|---|
| Rename to OptiCampus (UI, title) | PASS (internal ids/DB unchanged) |
| Use supplied logo | PASS (code + test); appearance NOT VISUALLY INSPECTED. Original preserved in `docs/branding/`; web copy at `frontend/src/assets/logo.png`; favicon derived from it |
| Sign in / forgot / reset / request access / change password | PASS (backend + UI tests); email delivery NOT TESTED (no SMTP; dev log path tested) |
| No privileged demo credentials on public pages | PASS (`sign in page: no demo credentials`) |
| Simplified wording/navigation/dashboards | PASS (UI tests assert wording) / NOT VISUALLY INSPECTED |
| Inter font (bundled), lavender palette, consistent radii | PASS in code / NOT VISUALLY INSPECTED |
| Light + dark themes | PARTIAL: WCAG contrast of all token pairs + 12 course colours measured (`scripts/contrast_check.py`, all pass) and a bug fixed; **pages were never viewed** |
| Responsive/mobile | PARTIAL: drawer/agenda/overflow-scroll implemented; behaviour tested in jsdom only |
| FAQ page | PASS |
| Floating Campus Buddy | PASS (behaviour); position/overlap not visually checked |
| Notifications (DB, recipients, dedupe, unread, read) | PASS (`test_notifications_only_reach_intended_recipients_and_dedupe`) |

## Part E - database
| Item | Status |
|---|---|
| Users, roles, bookings, decisions, notifications, disruptions, audit, resets, timetable state persisted | PASS on SQLite incl. restart simulation (`test_state_and_bookings_survive_a_restart`) |
| PostgreSQL | NOT TESTED (psycopg2 installed; migrations are portable but never run on Postgres) |
| Rooms/faculty/groups/courses/sessions as DB tables | PARTIAL: the dataset is loaded from the official JSON at startup; admin edits are persisted (as a JSON snapshot in `app_kv`) and survive restarts; they are not normalised relational tables |
| Dataset initialisation safe, no overwrite on restart, admin reset | PASS (`test_demo_reset_admin_only_and_restores`, idempotent import tests) |
| Faculty unavailability persisted | PASS via applied disruptions in persisted state |

## Part G - testing/deployment
Backend 120+ tests, frontend 40 UI tests, production build: see IMPLEMENTATION_STATUS.md for exact counts. Official validator on both exports: 0 hard violations. Deployment to Render/Vercel: **NOT DONE / NOT TESTED**. Video: **NOT PRODUCED**.

## Latest brief (midsem / faculty assistant / landing / contrast)
| Requirement | Status | Evidence |
|---|---|---|
| "When is my midsem?" / "Exam kab hai?" return real exam details | PASS | `tests/test_midsem_buddy.py` (10 phrasings, DB-equality check, DBMS course filter, tomorrow handling, no group, faculty/club explanations, privacy) |
| Exam publication flow + not-published message | PASS | `test_unpublished_exams_are_hidden...`, UI test; survives restart |
| Exam views by group/course/room | PASS (UI filters) | UI test |
| Faculty AI scheduling assistant (leave, unavailable, move, room problem) | PARTIAL | `tests/test_faculty_assistant.py` (10); no extra-tutorial support |
| AI cannot bypass validator / apply directly / self-approve; stale proposals refused | PASS | same file |
| Landing: new headline/CTAs/footer; separate from the app | PASS | UI tests |
| Dark-mode green contrast, central tokens, WCAG AA | PASS (measured) | `scripts/contrast_check.py`, tone-token test |
| Claymorphism + glassmorphism applied; reduced-motion respected | PARTIAL: implemented, not viewed in a browser |
| Full list of other Part 1-15 items | see `IMPLEMENTATION_STATUS.md` "NOT done" |
