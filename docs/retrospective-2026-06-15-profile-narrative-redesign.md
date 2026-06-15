# Retrospective — AI profile narrative redesign + 2-step lifecycle (2026-06-15)

Owner-driven redesign of the AI student profile. Five commits on `main`
(`dc89c39`→`68fd1ac`), **no migration**. Plan: `docs/scholarship/profile-narrative-redesign-plan.md`.
Worktree-isolated; another agent held the primary checkout.

## What Was Built

- **One profile, generated twice, always by the system.** Draft at the Check 2 → reviewer
  handoff (Gemini Flash); FINAL at "Save verdict & generate final profile" (Gemini Pro), which
  **replaces** the draft and **is** the sponsor/pool version. No separate confidential vs
  anonymous profiles; no manual Generate/Save/Publish/Refine controls; no anonymous-profile card.
- **Narrative prose** (~3 paragraphs, no section headers), warm, no fundraising clichés.
- **PII-redaction policy (owner-revised):** refer to the student by alias; block ONLY name, NRIC,
  photo, phone, email, street address (student + guardian). School, town/state, institution,
  occupations are allowed. Split the leak scanner: strict `scan_anon_for_identifiers` (graduation
  relay) vs relaxed `scan_profile_pii` (the profile).
- **Richer, honest inputs:** merit score, subject-area grade mix, the confirmed programme +
  institution, and the **student's answers to Check-2/reviewer queries**. The final also folds in
  interview findings, the four-fact verdict, the reviewer's conclusion, and the recommended amount.
- **He/she, never "they"** (from gender, NRIC-digit fallback); em-dashes used sparingly.
- **Income honesty:** STR/JKM = B40/welfare status, NEVER an income figure; a payslip/EPF on file
  (either route) is used authoritatively; otherwise income is "reported", never attributed to a
  guessed earner. (`scan` + `_income_evidence` from `income_engine`.)
- **Cockpit** renders the profile as plain read-only text (no scroll box). Final published to the
  pool on Approve.
- **Backfill:** generated drafts for all 7 reviewer-assigned students via a no-arg, flag-gated
  `backfill_assigned_profiles` command wired to the internal cron endpoint (runs on the service —
  the sandbox can't reach the prod DB). Validated live on #72.

## What Went Well

- Owner-in-the-loop previews: assembled the real prompt on real data (#72) and iterated the *prompt*
  (pronouns, em-dashes, STR/income honesty) before spending any Gemini calls. The live output then
  matched the agreed style first try.
- The verdict→Pro-final path already existed, so the lifecycle was mostly UI removal + prompt rewrite.

## What Went Wrong

1. **`CHECK2_AUTO_GENERATE` was referenced in code but never defined in settings** — so it was
   permanently `False`, and the handoff auto-draft had silently *never* worked.
   - *Root cause:* a flag added as `getattr(settings, 'CHECK2_AUTO_GENERATE', False)` with no
     matching `settings.CHECK2_AUTO_GENERATE = os.environ.get(...)`. Setting the Cloud Run env var
     did nothing; the code never read it.
   - *Fix:* wired it in `base.py`. **Lesson:** a feature flag isn't live until the env var is read
     INTO settings — grep settings for the name, don't just set the env var. (lessons.md)
2. **Tried to run the backfill from the sandbox against prod** — failed: the sandbox can't resolve
   the Supabase DB host (DNS blocked; that's why migrations use MCP).
   - *Root cause:* assumed local→prod DB reachability that doesn't exist here.
   - *Fix:* ran it ON the service via the existing internal cron endpoint (a no-arg command). For
     prod-side one-offs, prefer the cron endpoint / a Cloud Run Job, not a local run.
3. **Briefly relaxed the shared leak scanner globally**, which would have loosened the
   graduation-message relay too.
   - *Root cause:* one function served two policies.
   - *Fix:* split into `scan_anon_for_identifiers` (strict) + `scan_profile_pii` (relaxed); tests for both.

## Design Decisions

See `docs/decisions.md` (2026-06-15): one PII-redacted narrative profile (no separate anon), the
6-item redaction policy, scanner split, income-honesty rule, and the verdict→Pro-final→pool flow.

## Numbers

- 5 commits, **0 migrations**. Backend **~2433 pytest** (1269 scholarship + ~1164 courses/reports);
  jest 306; i18n parity 2682×3; web build clean; all Cloud Builds SUCCESS.
- 7 profiles backfilled `[4,9,10,12,15,24,72]`; `CHECK2_AUTO_GENERATE` wired + on (durable env var).
