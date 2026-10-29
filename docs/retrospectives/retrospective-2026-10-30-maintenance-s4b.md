# Retrospective: Student maintenance Sprint 4b, when results are due and the student results emails (2026-10-30)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 4, second half). Shipped on main as
`e421d37b` (part 1: result terms and standing), `9da575eb` (part 2: emails and the Student communications tab),
`eaee818a` (fixes for the 10 adversarial review findings), `9809de16` (migration 0188) and `47d00f11` (removing the
noqa comments, so the code-standards ratchet held). Live as api revision 01193-58g. Migration
`scholarship/0188_results_expectations_student_email_templates` was applied by hand, migrate-first, at
2026-10-29 21:40 UTC, with RLS and one service_role policy on each new table.

## What Was Built

- **Result terms** (`ResultsExpectation`, `results_expectations.py`).
  - Her first term is placed from the day she was funded; every later term chains from the stored end of the
    previous row.
  - Each term is due `results_due_days_after_term` days after it ends, and becomes "not submitted" after
    `results_overdue_grace_days` more. Both numbers are organisation settings.
  - There is no back-dated debt: the schedule starts with the term she is in now.
  - An accepted result meets her oldest open term, and a repeated semester does not use up a new term.
- **One late rule** (`results_expectations.late`). The standing ("Not submitted"), the Scholars list's Results
  overdue filter, tile and Next due column, the scholar file, her My Bursary page (a boolean sent by the server)
  and both daily jobs all read it.
  - A graduate, a file that is ready to close, and a closed file are never late.
  - A result she sent this term that is waiting for review is not counted as her lateness.
- **Student results emails** (`StudentEmailTemplate`, `student_comms.py`).
  - There are three kinds (results due, results overdue, result queried), in en, ms and ta. Each student gets the
    one in her own language.
  - The default wording lives in code. An organisation only gets a row when it rewords a letter, so nothing is
    seeded. The wording is edited on Organisation → Settings → Student communications.
  - Each email comes from the organisation's own sender and is metered to that organisation.
  - All three are dark until `MAINTENANCE_REMINDERS_ENABLED` is set. A student on hold gets no due or overdue
    email.
- **Daily jobs.**
  - `results-overdue-flag`: makes the term rows, pairs accepted results with them, and writes one staff line and
    one email per late student.
  - `results-due-reminders`: sends the reminders. Each one claims its row first and gives the claim back if the
    send fails.
  - Both jobs are idempotent and handle each student separately, so one failure does not stop the run.

## What Went Well

- The kill switch was designed in from the start. With it off, the jobs still keep each student's terms and the
  staff line up to date, and nothing a student receives is stamped. Switching it on later therefore still reaches
  everyone who is due or late.
- The per-function doors fence from S4a caught the new writers (`reconcile`, `unlink`) and readers (`finished`,
  `pending_since`) as soon as they appeared, and each had to be named on purpose.
- The work was split into two reviewable commits when it passed the file budget. The migration was deferred
  behind Billing's 0187, so neither session forked the migration graph.

## What Went Wrong: the 10 adversarial review findings

1. **HIGH: terms were recomputed from the funding date on every run.** Changing terms-a-year (2→4, 4→1)
   therefore overlapped, gapped or back-dated terms, and a test locked the overlap in. **Root cause:** the
   schedule was treated as a pure function of (origin, setting), but the setting is mutable while the rows are
   promises already given to a student. **System change:** `term_starts_on` is stored. The next term starts at the
   last row's `term_ends_on`, at the length set when that row is made. Only the first term reads the funding
   date. Tests cover a 2→4 switch, a 4→1 switch and a changed funding stamp.
2. **MED-HIGH: graduates and closed files could read "not submitted".** **Root cause:** "late" was defined over
   the open rows alone, without asking whether she was still owed a result. **System change:** no new terms after
   an accepted graduating result or at ready_to_close, and both jobs skip those students. Graduated is checked
   before overdue. Closed files are ignored by `next_due` and `late`, including in the closed list.
3. **MED: a result waiting for review excused her even if it was sent before the term began.** **System change:**
   only a pending result sent on or after the oldest open term's stored start counts.
4. **MED: the list filter and tile disagreed with the Standing column.** **Root cause:** each surface had its own
   copy of "late". **System change:** there is one rule, `late`. The list annotates `next_due_starts`,
   `pending_for_due` and `graduated_any`, and `overdue_q` follows the same rule with the query budget unchanged.
5. **MED: a re-sent accepted result for a semester already counted used up the next term.** **System change:**
   semester labels are compared with case, spacing and punctuation folded.
6. **LOW-MED: several late terms produced several lines and emails.** **System change:** one line and one email
   per student per run, naming the oldest due date, with all her late rows stamped.
7. **LOW-MED: the reminder was stamped after sending, so two runs could both send, and a failed send was
   silently retried.** **System change:** the row is claimed first with a compare-and-set, given back if the send
   fails, and only one reminder goes per student per run.
8. **LOW: one bad row stopped the whole run, and the flag and the email shared one stamp.** **System change:**
   each student runs in her own try/except. `overdue_emailed_at` is kept apart from `overdue_flagged_at`, so a
   failed or switched-off email is retried.
9. **LOW (owner default, reversible): a student on hold could still be chased.** **System change:** no due or
   overdue email while she is on hold. Her terms and standing still update. This is recorded in decisions.md.
10. **LOW: the browser decided "late" by comparing dates, and the activity line printed a raw ISO date.**
    **System change:** the server sends the `next_result_overdue` boolean, and the date goes through
    `formatDate`.

**The shared root cause of 1–4:** a derived value (the schedule, "late") was computed in several places and from
the origin each time, instead of from stored facts in one place. **Main lesson** (recorded in `lessons.md`): a
schedule derived from settings must chain from its stored rows, never be recomputed from the origin.

**Process:** three `# noqa` comments added to the jobs raised the code-standards noqa ratchet. They were removed
in their own commit rather than the ratchet being raised.

## Design Decisions

- **The term model:** terms count from the day she was funded, with no back-dated debt, and the due dates are
  stored (decisions.md, 2026-10-29, S4b). We do not read institution calendars, because there is no reliable
  source for them.
- **Student email wording is per organisation, with the defaults in code.** One platform switch controls all
  three kinds. There is no student opt-out field; these are transactional notices about her own bursary.
- **A closed file's open rows are ignored, not settled,** so `closure.py` was not touched.

## Numbers

- Lead's run on `47d00f11`: **10,352 pytest** passed (3 skipped); **4,979 jest in 320 suites**; i18n ALL PASSED;
  bundle budget ok (median 146.608 kB); `makemigrations --check` clean.
- Adversarial review: 1 HIGH, 4 MED, 5 LOW. All were fixed, each with a regression test.
- Commits: part 1 (32 files), part 2 (34 files), review fixes (15), migration (1), ratchet (1). One migration
  (0188), applied by hand.
