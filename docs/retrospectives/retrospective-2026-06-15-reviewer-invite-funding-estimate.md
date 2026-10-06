# Retrospective — Reviewer-invite & funding-estimate live-review round (2026-06-15)

A live-review session driven by the owner inviting real reviewers and reviewing real
applicants. Seven commits on `main` (`0eecd1d`→`4c2053f`), **no migration**. Worktree-isolated
(`.worktrees/r15`) while another agent held the primary checkout on `feature/doc-eval-harness`.

## What Was Built

1. **Reviewer-assignment email** (`0eecd1d`) — `emails.send_reviewer_assigned_email`, hooked
   into `services.assign_reviewer`. Best-effort, English, fires once per (re)assignment, never
   on unassign or a no-op. Names the applicant; links to `/admin/login`.
2. **Invite name metadata** (`d85365a`) — the Supabase invite POST now sends `data:{name}` so the
   "Invite user" email template can greet by name via `{{ .Data.name }}`.
3. **Reviewer email copy** (`54c4592`) — closes with "B40 Assistance Programme" (the canonical name).
4. **Funding-estimate model rebuild** (`ca1d7a5`, `a6a0ecb`, `5354ae0`) to the owner's
   interview-based table: a single per-pathway **monthly shortfall = living costs − govt
   allowance − PTPTN**, × the **per-pathway typical duration**, rounded to RM100. Splits
   Politeknik (`poly`) vs public-university diploma (`university`); **drops the device one-off**
   (tranche support); **no degree category** (post-SPM can't enter degree direct, bar PISMP);
   `kkom`/`iljtm`/`ilkbs` left un-estimated. `variable` (asasi, uni-diploma) + `practical`-term
   flags surfaced on the cockpit card. Classifies from `chosen_programme` when the pathway-type
   field is blank (the #62 offer-letter-auto case). Duration is the table value, NOT the
   student's year-rounded `programme_months`.
5. **Gopal offer-vs-pathway guidance** (`4c2053f`) — when the offer letter differs from the
   chosen pathway, Gopal now names the difference and offers two real options: update the
   pathway in /profile to match, OR leave it and confirm via the (live) Check-2 `pathway_confirm`
   step after submit. Replaces the old "do nothing, don't edit anything".
6. **Ops (no code):** connected **Brevo** as Supabase Auth custom SMTP (reusing the api's
   verified `noreply@halatuju.xyz` sender) — fixes the invite/password-reset rate limit;
   rebranded the Supabase "Invite user" template; corrected the stale CLAUDE.md note that said
   `CHECK2_STUDENT_QUERIES_ENABLED` was off (it's ON in prod).

## What Went Well

- Worktree isolation + refspec push kept the other agent's branch untouched across 7 deploys.
- The funding model was aligned with the owner *before* coding (showed the exact per-pathway card
  texts and numbers for sign-off first) — the build then matched intent in one pass.
- Live verification (Supabase auth logs, `gcloud run …describe` env) caught and corrected two
  wrong assumptions before they misled the owner further.

## What Went Wrong

1. **Asserted stale state twice** — claimed "/profile pathway is read-only" and
   "`CHECK2_STUDENT_QUERIES_ENABLED` is off", both wrong.
   - *Root cause:* trusted the CLAUDE.md notes and an Explore agent that read the **primary
     checkout** — which sits on the *other agent's* branch (`feature/doc-eval-harness`), not
     `main`/live. The pathway picker and the live flag both differed from what those sources said.
   - *Fix:* when stating feature/flag state, read code from `main` (the worktree) and verify
     runtime flags against the running service (`gcloud run services describe`), never from
     CLAUDE.md or the primary checkout. Captured in `lessons.md`.
2. **Funding estimate first shipped with a duration override** that made STPM show 24 months
   (from a student's "2-year" entry) instead of the real 18.
   - *Root cause:* misread the owner's "programme_months goes in years" as "use it as an
     override" when it actually meant "it's too coarse to trust".
   - *Fix:* removed the override; the per-pathway table is authoritative for duration. Test added.
3. **Reviewer-email copy needed a follow-up commit** (said "HalaTuju scholarship programme",
   corrected to "B40 Assistance Programme").
   - *Root cause:* wrote programme-name copy without checking the canonical name first.
   - *Fix:* use "B40 Assistance Programme" for officer/student-facing copy (it's the live name).

## Design Decisions

See `docs/decisions.md` (this date): the funding-estimate shape (single shortfall × fixed
duration, no device, no student-duration override, poly/uni-diploma split), classifying from
the chosen programme, and Brevo-as-Supabase-SMTP.

## Numbers

- 7 commits, **0 migrations**.
- Backend **2430 pytest** (1266 scholarship + 1164 courses/reports); jest 306; i18n parity **2681×3**.
- `next build` clean; all Cloud Builds SUCCESS; smoke 200/200.
