# Retrospective — Admin Roles realignment + post-deploy fixes + B40 income policy (2026-06-09)

A milestone close covering one continuous body of work shipped to production on 2026-06-09:
the 4-role admin realignment, two post-deploy fixes, and the B40 income-gate policy change.

## What Was Built

**Admin roles realignment (4 sub-sprints, commits `df00d36` → `a156381`)**
- New role model `super / admin / partner / reviewer` (retired `viewer` → `admin`). Legacy
  `is_super_admin` kept in lockstep (expand-contract); `has_role(admin, *roles)` lets `super`
  pass everything while `admin`/`partner` fail execute gates (admin is read-only for now).
- **Scoping enforced everywhere:** `get_partner_students` (the single choke-point for Students /
  Dashboard / CSV export) is role-aware; every B40 endpoint — list, detail, **and all actions**
  (verify-accept, verdict, interview, reject, award, profile generation, run-vision, …) routes
  through `_scoped_application`, so a reviewer can neither see nor act on an unassigned applicant,
  and a partner is 403 on B40. Covered by leak tests.
- **Frontend:** role-driven nav menu; invite page rebuilt (role-first selector, dynamic title,
  Partner-only organisation, super not invitable); profile page redesigned — fixed a bug where a
  super admin saw reviewer-credential fields, made it responsive (2-col), added qualification /
  field-of-study dropdowns (+ Other), a public-university autocomplete (20 IPTA, acronym + EN/BM
  alias matching, free-text fallback, stores the BM name), a +60 phone mask, and a structured
  address split (street / postcode / city / state).
- Migrations `courses 0053` (role choices) + `scholarship 0055` (ReviewerProfile structured
  address). **Go-live data fix:** two CUMIG accounts mis-tagged `reviewer` corrected to `partner`
  before the new code went live (closing a prior over-exposure — they could previously see *all*
  B40 applications).

**Post-deploy fixes (commit `570f76d`)**
- Invite an **already-registered** user: a Supabase `422 email_exists` is no longer a failure —
  the admin row is created and links to the existing account by email on next sign-in.
- Search the **B40 Applicants** and **Students** lists by **phone + email** (not just name/NRIC).

**B40 income-gate policy change (commit `8033e7b`, migration `0056`)**
- Per the DOSM 2024 B40 line (RM5,860): a non-STR applicant whose **gross** household income is at
  or below the cohort `income_ceiling` is shortlisted **regardless of family size**. Per-capita
  (RM1,584) is now a **safety net** that only rescues households *above* the gross ceiling with many
  dependents — it is no longer the primary gate. STR fast-path unchanged.
- New `rescore_pending_decisions` service + `rescore-pending` cron job re-applies the engine to
  **un-released** decisions only; run once on deploy, flipping the one pending RM5,500 / family-of-2
  applicant (#67) from rejected → shortlisted before their decision was sent.

## What Went Well

- **Migrate-first held throughout.** Every schema touch (0053/0055/0056) was applied to prod via the
  Supabase MCP *before* the code push; zero schema-mismatch 500s across three deploys.
- **Isolated worktree kept the parallel agent's Action Centre work completely untouched** — built
  off clean `origin/main`, fast-forward merged, never entangled with `feature/action-centre-mount`.
- **The re-score tool turned a scary "re-judge live applicants" step into a safe, reusable one** by
  scoping strictly to un-released decisions and re-running the *actual* engine (no logic duplication).

## What Went Wrong

1. **First answer to the per-capita question trusted a stale role label.** *Symptom:* my initial
   data analysis treated the two "Sivamani" accounts as reviewers (their `role` column said so).
   *Root cause:* I read the `role` column as ground truth; two identically-named "reviewers" sharing
   one organisation was a tell I didn't question. *Fix:* when a role/label drives a data answer,
   sanity-check it against the owner if the shape looks odd, before computing on it.

2. **The invite flow shipped without testing the "user already exists" path.** *Symptom:* inviting a
   real person failed with a misleading "Failed to send invite email" (a 422 `email_exists` collapsed
   into a generic 502). *Root cause:* the invite redesign only exercised the new-email case; the
   single most common real case (the invitee already signed in as a student / via Google) was
   untested. *Fix:* when touching an invite/auth flow, always test the already-registered branch.

3. **First `next build` failed on a stale `'viewer'` comparison the per-file `tsc` missed.** *Symptom:*
   `tsc --noEmit` on the edited files looked clean, but `next build` failed on `canWrite !== 'viewer'`
   in the cockpit after I narrowed the role union. *Root cause:* narrowing a shared type has
   cross-file ripples that a tsc-on-changed-files check doesn't surface. *Fix:* after a shared-type
   change, run the full `next build`, not just `tsc` on the files you edited.

4. **Removed the worktree, then needed it back for sprint-close.** *Symptom:* cleaned up the
   `feature/admin-roles` worktree on request, then had to re-create it to commit the close docs.
   *Root cause:* worktree teardown happened before the sprint was formally closed. *Fix:* run
   sprint-close (which commits docs + pushes) *before* tearing down the feature worktree.

## Design Decisions

See `docs/decisions.md` for the full entries:
- 4-role model via expand-contract + `has_role` (admin = read-only by failing execute gates).
- B40 income gate: gross income is the primary test; per-capita demoted to an above-ceiling safety net.
- Re-scoring via a `rescore-pending` job (un-released decisions only) rather than a SQL update.
- Invite an already-registered user by granting the role + linking by email, not by re-inviting.

## Numbers

- Backend pytest: **2029** (all `apps/`). Frontend jest: **276**. i18n parity: **2468** × en/ms/ta.
- 3 production deploys (api+web, then api, then api), all Cloud Build SUCCESS, verified live
  (401-not-500 on gated paths, public 200, no error logs).
- Migrations: `courses 0053`, `scholarship 0055`, `scholarship 0056` (all migrate-first via MCP).
- Prod admin state after: 1 super (owner) + 2 CUMIG partners + 0 reviewers. One applicant (#67)
  re-scored rejected → shortlisted under the new income rule.
