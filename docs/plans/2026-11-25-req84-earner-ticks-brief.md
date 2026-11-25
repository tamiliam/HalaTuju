# #84 — a ticked earner that the family details say is not working (brief, 25 Nov 2026)

Request #84 (org 11). Analysis 190 approved and posted 24 Nov (comment 265); scheduled by the owner 24 Nov. Bug, no charge,
4.0 h build + 0.5 h answer (already given). No organisation comments since the analysis.
Branch `req84-earner-ticks` in worktree `.worktrees/req84-earner-ticks`, cut from side/laptop 85d80be6a (contains #78 and
S1b–S3, unreleased; lands 25 Nov 16:00). This branch lands after #78 and #85.

## What the organisation was promised (build exactly this)

From the posted analysis:
- "When a student ticks someone as working whom the family details mark as not working (or do not list), we will ask the
  student to check before saving."
- "The case page will show a clear warning when the two answers disagree, instead of a plain \"Earns\"."
- "Other open cases have the same mix-up, and they will benefit from the same change."

The fault: on the income step the student ticked every household member as working (father, mother, guardian, elder brother,
elder sister), while the family details say the mother is unemployed and list no guardian or siblings. The case page shows
"Earns" for every ticked person, and the blockers ask for IC + income proof (+ birth certificate for the mother,
guardianship letter for a guardian) for each one.

## Steps

1. **Find the two answers.** Locate where the income-step earner ticks are stored and read (api + web), where the family
   details store employment status and which members exist (guardian, siblings), and where the case page renders "Earns"
   and where blockers are derived from the ticks (`services/blockers.py`, `income_engine/*`). Write down the exact fields
   before changing anything. Check `docs/decisions.md` for any earlier ruling on earner ticks vs family details and follow it.
2. **One rule, one home.** A single server function decides, per household member, whether the tick disagrees with the family
   details: ticked as working but the family details say not working (unemployed / housewife / retired / deceased / whatever
   values the field uses — list them from the code), or ticked but that member is not listed at all. It is served to the web;
   the browser does not re-derive it.
3. **Student side (web).** On the income step, when the student saves with a disagreeing tick, ask them to check (a clear,
   non-blocking confirm naming the person and what the family details say; they may go back and change either answer, or
   confirm). Do not silently untick. Follow the house style for confirms and toggles (memory: toggles, not tick boxes, except
   agree/confirm statements). New strings in en, plus ms and ta drafts (mark "for Sol's read").
4. **Officer side (web).** On the case page, a disagreeing member shows a clear warning instead of a plain "Earns" (e.g.
   "Ticked as earning — family details say unemployed"). Served, not derived.
5. **Blockers.** DO NOT change what is owed without stopping first. The posted text promises a check and a warning only; it
   does NOT promise to drop the income-proof blockers for a disagreeing tick. Keep the blockers as now unless the code shows
   the promise cannot be met otherwise — then stop and report. (If a student confirms, proof is still owed.)
6. **Other open cases.** No data migration and no production writes: the warning is computed live, so open cases benefit
   when it ships. Count (read-only, counts only) how many live open cases have at least one disagreeing tick, for the report.
7. **Version.** If anything the verdict engine reads changes, bump `VERDICT_ENGINE_VERSION` (side/laptop has 2026-11-23.1;
   use a placeholder that sorts after it and say so — the lead re-sets versions at landing). If nothing it reads changes, say
   why no bump is needed.
8. **Docs.** decisions.md dated entry (25 Nov 2026, #84); CHANGELOG under a #84 heading; any TD-NEW-<name> for what you find
   but do not build.

## Rules

- Opus build (income / eligibility flow). Targeted tests while building; the full API suite ONCE at the end through the queue:
  `caffeinate -i -m -s python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- /Users/elanjelian/.venvs/halatuju-py311/bin/python -m pytest -q -p no:cacheprovider`
  from `halatuju_api` (never the 3.12 .venv). Web: run `npm ci` in this worktree's `halatuju-web` (never a node_modules
  symlink), then through the queue `npm run gates`, `npm run bundle-budget` (median must stay under 156 kB; never raise a
  budget, floor or ledger — if over, stop and report the route-by-route growth). Leave mobile-check to the lead.
- No production writes, no paid calls, no re-reads, no document downloads. Production DB (Supabase MCP, project
  pbrrlyoyyiftckqvzvvo) only `BEGIN READ ONLY; SELECT …; ROLLBACK;`, counts and ids only. No personal data in code, tests,
  docs or output: case numbers only; they/them; "the student".
- Bash: absolute paths; no `VAR=` at the start of a command; no `$()`; never `git add -A`; never bare `git stash`; no push.
  Work only in this worktree.
- Commits: honest type, the word "sprint", e.g. `fix: sprint #84 - ...`. Final commit trailers:
  `Phone-check: <a case where a ticked earner disagrees with the family details shows the warning; the student is asked to check on save>` /
  `Migration: none` / `Services: both` / `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Report back (≤ 30 lines)

Commits (sha + one line), the fields and the one rule, what the student and the officer now see, blockers unchanged (or why
you stopped), count of live open cases affected, version decision, new strings for Sol, test counts (targeted, full API,
web gates, bundle median), run time.

Stop at 120k. Commit your work. Send back a split plan.
