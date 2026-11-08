# Request #55 — Notes for the reviewer (feature sprint, 2026-11-07)

Executor: Opus agent. Branch `req55` (from origin/main dc013e5e). Approved analysis 144 (9.5 h, quoted,
scheduled 2026-11-07). Owner approved the mock-up 2026-11-07:
https://claude.ai/artifact/GcgdVoxctk4kHwvwPt1V7S (two screens: org admin writes; reviewer/QC reads).

**Main is under audit: commit and push to `req55` only. Never push or merge main, never deploy, never
apply the migration to production.** The audit agent applies the migration (migrate-first, by hand) and
deploys later.

## The ask (organisation, verbatim gist)

Before assigning a student to a reviewer, the org admin reviews the application and picks out things for
the reviewer to explore; today she texts them. She wants to write them on the application page, for
ease of communication and as a saved record, with a size limit like the reviewer's Recommend box.

## Owner-settled decisions (analysis 144 + mock-up)

| # | Decision |
|---|---|
| 1 | A "Notes for the reviewer" card on the admin application page (`/admin/scholarship/[id]`), right column, directly UNDER "Reviewer assigned" (`view/AssignAndWitness.tsx`). |
| 2 | Write: org admins (role `org_admin`) and platform supers. Nobody else. Read: the assigned reviewer, QC, and staff who can already open the file (the existing fence). Students and sponsors NEVER (not in any student or sponsor serializer; sponsor serializer is an allowlist — leave it). Never fed into any AI prompt (case summary, profile generation, verdict). |
| 3 | Writable from Awaiting Review until the reviewer records a decision (use the codebase's own status/decision markers; locate the "Awaiting Review" stage and the reviewer-decision point — e.g. `verdict_decided_at` / interview submit — and pick the one that matches "until the reviewer records a decision"; justify). After that: read-only, notes stay on the file for good (incl. after award). |
| 4 | Append-only: each note stores author (staff identity) + timestamp; no edit, no delete endpoint. To correct, add another. |
| 5 | 2,000-character limit per note, server-enforced, with a live counter in the box ("97 / 2,000"). Blank / whitespace-only refused. |
| 6 | Reviewer/QC card: read-only list (author, date, text, newest last); empty state "No notes from your org admin." The org-admin card shows the list + "Add a note" textarea + counter + "Notes can't be edited or deleted. To correct one, add another." + "Add note" button. |
| 7 | en / ms / ta. British English. Update the Reviewer Guide and FAQ (find where they live — authored content may be in the DB or in messages/docs; never conclude absence from a grep alone) and `docs/scholarship/role-matrix.md`. |

## Build notes (read the CLAUDE.md files first — they bind)

- **Model + migration:** new model (e.g. `ReviewerNote`: application FK, body ≤2000, author FK/identity as
  other staff-authored rows do, created_at). Additive migration only. Write the migration file AND the
  matching hand-apply SQL (postgresql DDL + `django_migrations` ledger row in one transaction, RLS enabled
  with the `service_role` policy as `docs/security-posture.md` says for a new table) into the brief's
  "Migration" section below, so the audit agent can apply it. Do NOT apply it anywhere but your local/test DB.
- **API:** new admin endpoints through `_AdminBase` (`_org_scoped` / `_org_allows`): list + create. The H3
  guard fails a wired route no test drives or that skips the fence — drive both. Reviewer may read only
  applicants assigned to them (existing reviewer scoping). Refusals carry a code + words in 3 languages.
  Follow `docs/build-for-tenancy-conventions.md`.
- **Query budget:** the applicant-detail GET is pinned at 38 queries. Prefer a separate notes fetch (or
  prove the budget holds); never raise a budget, floor or ledger; split a file first if one is at its
  allowance (`code-standards.json`).
- **Activity:** consider whether adding a note belongs in the existing activity log (`activity.py`,
  `models/activity.py`, `models/staff_activity.py`) — smallest consistent choice.
- **Web:** the card component in `view/` (new file), wired in `view.tsx` under AssignAndWitness. Use the
  existing card styles. Mobile standard applies (`docs/mobile-standard.md`), touch targets ≥44px.
- **Tests:** permissions matrix (org_admin/super write; reviewer assigned/unassigned, qc, admin view-only,
  finance, partner, other org, student, sponsor), stage window, 2,000 limit, append-only, never in AI
  prompts / student / sponsor payloads, rendered web tests for both views and the counter.
- **Gates:** full API suite `-n auto`, `manage.py check`, `makemigrations --check` (clean after your
  migration), `npm run gates`, bundle ratchet, `npm run mobile-check` — heavy runs through
  `python /Users/elanjelian/Python/Settings/_tools/test_queue.py -- …` (no `|` in args). CHANGELOG,
  `docs/decisions.md`, schema docs where models are documented. Commit type `feat:`.

## Migration (to be filled in by the builder: file name + exact hand-apply SQL)

**File:** `halatuju_api/apps/scholarship/migrations/0205_reviewer_notes.py` (depends on `scholarship 0204_decisionreopen_reopened_from`
and `courses 0093_retire_partneradmin_is_super_admin`). NEW TABLE ONLY; no existing column changes. If another branch
takes 0205 first, renumber on rebase and change the ledger row's name to match.

**Pre-check (read-only):** `SELECT name FROM django_migrations WHERE app = 'scholarship' ORDER BY name DESC LIMIT 2;`
must show `0204_decisionreopen_reopened_from` on top, and `SELECT to_regclass('public.reviewer_notes');` must be NULL.

**Hand-apply SQL** (Postgres DDL rendered offline with Django's postgresql schema editor from the migration; the same
text is in the migration's docstring):

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE "reviewer_notes" ("id" bigint NOT NULL PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY, "body" varchar(2000) NOT NULL, "author_email" varchar(254) NOT NULL, "created_at" timestamp with time zone NOT NULL, "application_id" bigint NOT NULL, "author_id" bigint NULL, CONSTRAINT "reviewer_note_not_blank" CHECK (NOT ("body" = '')));
ALTER TABLE "reviewer_notes" ADD CONSTRAINT "reviewer_notes_application_id_37b4a124_fk_scholarsh" FOREIGN KEY ("application_id") REFERENCES "scholarship_applications" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "reviewer_notes" ADD CONSTRAINT "reviewer_notes_author_id_a99641f0_fk_partner_admins_id" FOREIGN KEY ("author_id") REFERENCES "partner_admins" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "reviewer_notes_application_id_37b4a124" ON "reviewer_notes" ("application_id");
CREATE INDEX "reviewer_notes_author_id_a99641f0" ON "reviewer_notes" ("author_id");
ALTER TABLE public.reviewer_notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY reviewer_notes_service_role ON public.reviewer_notes FOR ALL TO service_role USING (true) WITH CHECK (true);
INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0205_reviewer_notes', now());
COMMIT;
```

**After:** run the Supabase Security Advisor (0 errors before the deploy). Read back:
`SELECT relrowsecurity FROM pg_class WHERE relname = 'reviewer_notes';` (true) and
`SELECT policyname, roles FROM pg_policies WHERE tablename = 'reviewer_notes';` (one row, `{service_role}`).

**Order:** apply the SQL, then deploy api + web together. Between the two nothing reads the table, so the old image is
safe. Deploying first would make only the new card's fetch 500 (the rest of the case page does not depend on it).
**Rollback:** `BEGIN; DROP TABLE reviewer_notes; DELETE FROM django_migrations WHERE app = 'scholarship' AND name = '0205_reviewer_notes'; COMMIT;`
— **only before any note exists.** ⚠ Once notes exist, do NOT roll the API image back while the table stays: the
two foreign keys have no `ON DELETE` in the database (Django does the CASCADE / SET NULL in Python, and the old image
does not know the model), so on the old image deleting a staff member who wrote a note, or an application that has
notes, fails on the foreign key; and the old `staff_footprint` does not count `reviewer_notes`, so it would offer
that delete in the first place. Once notes exist, roll FORWARD (fix and redeploy) instead.
