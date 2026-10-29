<!-- Decomposed via Settings/_workflows/implementation-planning.md; owner-approved 2026-10-29. -->

# Roadmap — Post-award student maintenance (Scholars file + My Bursary)

## Context
65 BrightPath students are funded and paid every month (all `status='awarded'`, all Vircle-activated,
sub-state `on_track`; 0 semester results, 0 thank-yous, 615 payment-run items — checked live 2026-10-29).
The application-stage screens do not serve them: the student `/profile` is identity only, the
`/scholarship/in-programme` "My progress" page is linked from nowhere, and the admin cockpit is crowded
with application work while post-award sits in one panel at the bottom. Worse, every in-programme
gate (`in_programme._require_in_programme`, `maintenance._require_maintenance`, `payments._is_on_hold`,
`pool.derive_progress_state`) only accepts `active`/`maintenance`, so **none of the 65 can record a
result, be put on hold, or see a hub today**.

Goal: one "student file" from award acceptance to closure — a Student hub ("My Bursary") and an admin
Scholars list + maintenance file — with every threshold, email and letter wording in the platform's
settings and templates, not in code.

## Owner rulings (2026-10-29)
- Contract: show **platform-signed agreements only**; otherwise a neutral "No contract on file".
- Mentors: **records only** (admin-kept list, assignments, logged meetings). Mentor login later.
- Population: **from award acceptance to closure.** Predicate = `awarded` with `vircle_activated_at`
  set, OR `active`/`maintenance`. Closed students keep read-only access. (Counts 65 today.)
- **On hold stops money**: an on-hold student is left out of Vircle payment runs, whatever their status.
- **Automatic results reminders**: friendly reminder before due date; flagged "not submitted" after a
  grace period; admin can then issue a formal 14-day request letter (contract cl. 5).
- Baked-in defaults (say if you disagree): sponsor progress band stays as is (separate from admin
  standing); letter wording is authored freely per organisation (may quote a clause number).

## Information architecture
**Student — `/scholarship/bursary` "My Bursary"** (evolves `/scholarship/in-programme`, which redirects).
Linked from `AppHeader` (only when in maintenance) and a link-only card on `/scholarship/application`
(keeps that route's ~275 kB budget). Lazy tabs: Overview · Results · Funds · Contract · Letters ·
Announcements · Mentoring · Surveys · Growth. Later tabs appear only when their module is switched on.
`/profile` stays identity only.

**Admin — `/admin/scholars` "Scholars"** (programme nav group, after Applications; `/admin/students` is
already taken). Columns: name, gift, sub-state, latest CGPA, standing chip, results due/overdue, mentor,
last activity; FilterPill filters; badge = flagged count. **File `/admin/scholars/[id]`** (keyed by
application id): header (identity, gift, sub-state control, standing chip, "View application" → cockpit)
and tabs Overview · Results · Money · Contract · Letters · Mentoring · Surveys · Activity. The cockpit's
`PostAwardPanels.tsx` shrinks to a summary + "Open maintenance file"; sub-state + closure controls move.

## Data model (new tables: RLS + service_role policy, applied by hand via Supabase MCP)
| Model | Purpose | Sprint |
|---|---|---|
| `maintenance_scope.py` `in_maintenance_q()` / `is_in_maintenance()` | ONE predicate, reuses `closure.POST_AWARD_STATUSES`; replaces the 4 gates + web filter | 1 |
| `ScholarshipApplication` + `maintenance_substate_changed_at/_by_email` | who/when for sub-state | 1 |
| `StudentActivity` | CRM log: note/call/meeting/email/system; event codes (substate_changed, result_submitted, result_reviewed, letter_issued, mentor_assigned, session_logged, payment_released, closed); internal flag | 1 |
| `SemesterResult` + `review_status/reviewed_by/at/review_note/term_index`; slip via doc type `semester_result` | results with review | 4 |
| `ResultsExpectation` | per term: due_on, satisfied_by, reminded_at | 4 |
| `StudentEmailTemplate` + `StudentEmailLog` | DB-authored student emails (reuses `email_templates.py`, `TemplateEditor.tsx`) | 6 |
| `LetterTemplate` / `Letter` | discipline, suspension, termination, close-out, general; PDF in private bucket; emailed; acknowledged; response_due_on | 6 |
| `Mentor` / `MentorAssignment` / `MentoringSession` | records-only mentoring; nullable user link for later login | 7 |
| `Announcement` / `AnnouncementRead` | audience all/gift; optional email; read receipts | 8 |
| `Survey` / `SurveyQuestion` / `SurveyResponse` | later | 9 |
| `DevelopmentModule` / `ModuleProgress` | later | 10 |

## Where settings live (nothing hard-coded)
- **`courses/org_config_registry.py`, new `maintenance` group** (Organisation → Settings → Configuration):
  `maintenance_min_cgpa` 3.00 (from the contract), `maintenance_failing_cgpa` 2.00,
  `results_terms_per_year` 2, `results_due_days_after_term` 45, `results_reminder_lead_days` 14,
  `results_reminder_every_days` 7, `results_overdue_grace_days` 14, `letter_response_days` 14.
  Needs a small decimal unit in the registry (whole numbers only today).
- **Contract guard**: test + settings warning when `maintenance_min_cgpa` differs from the active
  contract template's progress standard. The client-side `≤ 2.0` in the in-programme page goes.
- **Email + letter wording**: new Organisation → Settings → **Student communications** tab
  (`StudentEmailTemplate` kinds: results_due, results_overdue, result_queried, letter_issued,
  announcement, mentor_assigned, survey_open, file_closed — the hard-coded closed email at
  `emails/student_reminders.py:246` moves here). All sends stay metered by `emails/shared._meter_email`.
- **Kill switches only in env**: `STUDENT_MAINTENANCE_ENABLED`, `MAINTENANCE_REMINDERS_ENABLED`.
- **Cron**: new jobs in `CronRunView.JOBS` + `cron_health.EXPECTED_CADENCE` (+ `test_system_health.py`),
  so the health light watches them.

## Sprints (each: Stitch first for new screens → owner OK; Opus builder, lead verifies; tests;
en/ms/ta; CHANGELOG + decisions.md; owner "yes" before every push; ≤ 2 deploys per feature)

1. **Foundation — predicate, on-hold stops money, activity log** (backend, ~20 files, migration).
   Replace the 4 gates; on-hold `awarded` student excluded from payment eligibility
   (`payments.eligibility`); `set_substate` stamps who/when + writes activity; `activity.log_event()`
   hooked into closure + payment completion. **Adversarial review (money + eligibility).**
   Accept: predicate = 65 live (dry-run SQL before deploy); on-hold awarded student drops out of a test run.
2. **Admin Scholars list + file shell** (~30 files). Endpoints `admin/scholarship/scholars/`,
   `.../scholars/<id>/overview/`, `.../activity/` (GET, POST note/call/meeting), org-fenced; nav entry +
   `navigation.test.ts`; Overview + Activity (timeline + composer, modelled on the requests comment thread);
   cockpit link. Accept: org_admin/admin see it, reviewer refused, notes persist, system events show.
3. **Student "My Bursary" hub shell** (~25 files). `/scholarship/bursary` Overview + Results (existing
   typed form moved), redirect, AppHeader link, application-page card, `scholarship/bursary/summary/`;
   move sub-state + closure controls from cockpit to the file. Accept: bundle-budget unchanged on
   `/scholarship/application`; on-hold/closed notices kept.
4. **Results and standing** (~35 files, may split 4a backend / 4b UI; migration).
   Slip upload; `standing.py` derives performing / underperforming / failing / not submitted / no result
   yet from settings + `ResultsExpectation`; admin Results tab (slip viewer, accept/query, history);
   registry keys; crons `results-due-reminders` + `results-overdue-flag` (daily). **Adversarial review.**
   Accept: changing `maintenance_min_cgpa` changes chips with no deploy; reminders idempotent + metered.
5. **Money summary + contract** (~20 files). Admin Money tab: paid to date, remaining, last 3 releases,
   spending by category (spending block needs `spending` permission; finance sees payments only), links to
   `/admin/payments` + `/admin/spending`. Contract tab (admin + student): signed PDF by signed URL, else
   "No contract on file" (works with the signing flag off). Student Funds tab on `SpendingCard`.
   **Adversarial review.** Accept: totals match the Payments page for 3 sampled students.
6. **Student email templates + letters** (~38 files, migration). Template family + Student
   communications tab; S4 reminders + closed email moved in; letters with PDF, email, acknowledge,
   typed confirm for discipline/termination; each letter logs activity. **Adversarial review.**
7. **Mentors (records)** (~30 files, migration). Registry `/admin/organisation/mentors`; assign + log
   sessions on the file; student Mentoring tab (read-only); filter by "wants a mentor".
8. **Announcements** (~25 files, migration). Authoring `/admin/programme/announcements`; student tab,
   unread count; optional email (cron `announcement-emails`, hourly).
9. *Later* — **Surveys** (builder, schedule, student form, outcomes tab).
10. *Later* — **Development modules** (content library + progress).
11. *Later* — **Mentor login**.

Order: 1 → (2 ∥ 3) → 4 → 6; 5, 7, 8 need only 2+3. First real value to the owner: Sprint 2.

## Critical files
- `halatuju_api/apps/scholarship/{maintenance.py, in_programme.py, payments.py, pool.py, closure.py,
  models/applications.py, models/review.py, views_admin/lifecycle.py, emails/student_reminders.py,
  cron_health.py, views.py (CronRunView)}`
- `halatuju_api/apps/courses/org_config_registry.py`, `courses/staff_permissions.py`
- `halatuju-web/src/lib/navigation.ts`, `app/scholarship/in-programme/page.tsx`,
  `app/admin/scholarship/[id]/view/PostAwardPanels.tsx`, `components/AppHeader.tsx`,
  `components/emails/TemplateEditor.tsx`, `components/admin/PanelTabs.tsx`

## First step after approval
Write this roadmap to `docs/plans/2026-10-29-student-maintenance-roadmap.md` + a decisions.md entry
(the rulings above), then sprint-start Sprint 1 in a worktree off origin/main.

## Verification (per sprint)
- `pytest` full suite + `npx jest` + `npm run bundle-budget` + `next build`; `wat_lint --project .`
- Read-only SQL dry-run on live data before deploy (predicate count, standing distribution, on-hold
  exclusion) — the live-data dry-run lesson.
- Local run (`manage.py runserver` + `npm run dev`): log in as org_admin, open `/admin/scholars`, a file,
  add a note; log in as a test student (#16) and open `/scholarship/bursary`.
- After deploy: read the build status, then check the live pages and the health light.
