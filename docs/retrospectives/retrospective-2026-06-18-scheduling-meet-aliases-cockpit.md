# Retrospective — Interview scheduling + Google Meet, email aliases, cockpit live-review (2026-06-18)

Commits `d13b949` → `a51517a` (10). Migration `scholarship/0061` (migrate-first). Branch
worked in a git worktree (`.worktrees/sched` / `feat/interview-scheduling`); pushed `HEAD:main`.

## What Was Built

1. **In-app interview scheduling + Google Meet (dark behind flags).** The assigned reviewer proposes 2–3 times
   (`InterviewSlot`); the student picks one on `/scholarship/application`; the system auto-creates a **Google Meet**
   link + calendar event and sends a bilingual (EN+BM) confirmation + 1-day/1-hour reminders (to student + reviewer).
   Self-service reschedule/cancel to a 12 h cutoff. New `scheduling.py` service + `meeting.py` (Workspace service
   account + **domain-wide delegation**, best-effort), booking columns on `ScholarshipApplication` + `interview_slots`
   table (migration `0061`), `send_interview_reminders` cron, admin propose/withdraw + student book/cancel endpoints,
   cockpit "Propose interview times" card + student booking panel, Guide + FAQ. Two flags
   (`INTERVIEW_SCHEDULING_ENABLED`, `INTERVIEW_MEET_ENABLED`). **Meet proven end-to-end** (real link created +
   deleted impersonating `admin@halatuju.xyz`); `INTERVIEW_MEET_ENABLED=1` is live, the surface flag stays OFF
   pending the owner's reviewer briefing.
2. **Google Workspace `halatuju.xyz` set up + email addresses mapped to aliases.** Domain-authenticated in Brevo
   (any `@halatuju.xyz` sends). From = `info@`, support copy = `help@`, interview reply-to = `interview@`, sponsor =
   `sponsor@`, internal notifications = `contact@`, Meet organiser = `admin@`. Fixed the lost-reply problem (emails
   said "reply" but were sent from a non-existent `noreply@`). Removed personal `tamiliam@gmail.com` from all
   user-facing copy; killed the dead `noreply@halatuju.com` fallback.
3. **Contact-form notifications.** The `/contact` form (Turnstile → `contact-submit` Edge Function →
   `contact_submissions`) stored rows but alerted no one. New cron `notify-contact-submissions` emails each unread
   submission to `contact@` (Reply-To = sender). Cleared the 2 unseen rows (both owner tests).
4. **Cockpit + UX live-review fixes.** Assignment dropdown lists only reviewers+supers; Sentence-case status labels
   + "Profile complete"→"Completed"; reviewer-name assignee filter; sortable Name/Merit (server-side); single-row
   filters; footer "B40 Aid" links; Guide images at natural size (float only the portrait one). Then the round-4
   batch: profile merit→grades **returns to /profile**; Decision panel **freezes** after recording (read-only,
   superadmin reopen); audit lines show **full name** not email; Interview Stage **save confirmation** + **read-only
   blue-box record after submit** (answered questions only) — which also closed a duplicate-draft bug.

## What Went Well
- **Worktree isolation** kept this entirely clear of the other agent's `feature/doc-eval-harness`; every push was a
  clean fast-forward of `origin/main`.
- **Migrate-first** for `0061` (table + columns + RLS + django_migrations row) verified before push; advisor clean.
- **Meet validated before enabling** — a self-contained DWD test (temp key, create+delete a real event) proved the
  Google integration without touching the app, so flipping the flag was low-risk.
- **Dark-by-default flags** let a large feature ship to prod with zero user-visible change until deliberately exposed.

## What Went Wrong
- **#15 "vanished" interview findings.** *Symptom:* a reviewer believed his interview text was lost. *Root cause:*
  the Interview Stage gave **no save confirmation**, so he wasn't sure it persisted and kept a separate copy; his
  narrative actually landed in the Decision Conclusion. Compounded by a latent bug — pressing **Save after Submit**
  spawned a **second (draft) interview session** (the save path created a new draft when none existed). *Fix:*
  explicit "Saved ✓"; after Submit the panel is read-only with no write controls, so no duplicate can be created;
  superadmin reopen for corrections.
- **Initial misdiagnosis of #15** as two-overlapping-boxes confusion. *Root cause:* I theorised from the code before
  the owner clarified the reviewer's actual experience (no save certainty). *Fix (process):* when a user reports a
  "lost data" symptom, confirm the *user's* sequence of actions before proposing a UX redesign — the DB state plus
  the user's account beat a code-only theory.
- **Cockpit had no freeze on committed work.** *Symptom:* submitted/decided panels still looked editable. *Root
  cause:* the panels gated only on `canWrite`, never on "already committed". *Fix:* `interviewLocked`/`decisionLocked`
  computeds + read-only renders; superadmin-only reopen.

## Design Decisions (see docs/decisions.md)
- Google Meet via a **Workspace service account + domain-wide delegation** (not per-user OAuth, not Jitsi).
- **Panel-freeze model**: Save = editable draft (overwrites in place); Submit/record = read-only; superadmin reopens.
- **Email-alias mapping**: global From = `info@` so replies are deliverable; topical aliases by role.

## Numbers
- Tests: **2478 backend pytest** (scholarship+courses+reports) + **327 jest**. i18n en/ms/ta parity. `next build` clean.
- Migration: `scholarship/0061` (1 new table + 11 columns; migrate-first via Supabase MCP; RLS + advisor clean).
- Ops live: `INTERVIEW_MEET_ENABLED=1`, `MEET_ORGANISER_EMAIL=admin@halatuju.xyz`, `DEFAULT_FROM_EMAIL=info@`,
  `ADMIN_NOTIFY_EMAIL`/`COURSE_REFRESH_REMINDER_EMAIL=contact@`. Cloud Scheduler: `halatuju-interview-reminders`,
  `halatuju-notify-contact-submissions`. Service account `halatuju-meet@` + DWD authorised.
- **Parked (owner):** flip `INTERVIEW_SCHEDULING_ENABLED=1` to expose scheduling (after briefing reviewers); add a
  merged SPF record; capture a scheduling-card screenshot for the Guide.
