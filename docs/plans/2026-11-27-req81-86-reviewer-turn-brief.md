# #81 + #86 — a case that is the interviewer's turn stays on their list (brief, 27 Nov 2026)

Requests #81 (analysis 192, 4.5 h) and #86 (analysis 199, +3.0 h when built with #81), org 11. Both bugs, no charge.
Both approved, posted (comments 271, 270) and scheduled by the owner for 27 Nov. No organisation comments since.
Branch `req81-86-reviewer-turn` in worktree `.worktrees/req81-86`, cut from origin/main b9915d29e (live is 3cb093b75).
Lands on a later train via the lead. Planned total: 7.5 h.

## What the organisation was promised (build exactly this)

#81 (case 513: verdict saved on every Approve, but the case never moved to QC and dropped off the interviewer's list):
- "Stop a sign-in from wiping quiz answers that are already saved."
- "Make the \"not sent to QC\" message name the missing step."
- "Keep a case like this visible on a list until it reaches QC."

#86 (case 196: QC reopened it to the interviewer on 24 Nov; it is still assigned to them but is not on their list; the
email links only to the login page):
- "A case QC sends back will show again on the interviewer's list of open cases, marked as returned by QC."
- "The email will include a direct link to the case."
- "The same fix covers cases like 513, where the verdict was saved but the case did not reach QC."

## What the analysis found (verify, do not trust)

- QC reopen: `views_admin/verdict.py:418-437` → `reopen.reopen_decision` (`reopen.py:127-155`): sets
  `decision_reopened_at`, status `interviewed` → `interviewing`, keeps `assigned_to`, does NOT clear `verdict_decided_at`
  (cleared only by `close_reopen_with_change`, `reopen.py:238-257`).
- Email: `_email_reviewer(app, 'returned', …)` (`verdict.py:259-269`, sent at :435), template `qc_returned`
  (seed `seed_partner_email_templates.py:210`), `{dashboard_link}` = `{frontend}/admin/login` (`emails/reviewer_mail.py:19-22`).
- "My open" list: `programme_overview.mine` filters `AWAITING_VERDICT, assigned_to=admin` (`programme_overview.py:595`);
  the card opens `/admin/scholarship?assigned=me&band=open` (`halatuju-web/src/components/admin/PendingCards.tsx:30`) →
  `review_sla.in_band` (`review_sla.py:114`). `AWAITING_VERDICT` requires `verdict_decided_at IS NULL`
  (`review_sla.py:39-44`). Both cases fail it: 513 = `interviewing`, verdict saved, no reopen; 196 = `interviewing`,
  verdict saved, reopened.
- Ruling: `docs/decisions.md:10747` (QC gate, 2026-07-02) "Reopens → back to the reviewer (`interviewing`) with an
  emailed gaps note"; :10759 assumed the reviewer clock keys on `verdict_decided_at IS NULL` and missed that a reopened
  case keeps its stamp.

## Steps

1. **#81 root cause first: the quiz wipe.** Find how a student's saved interest-quiz answers can be cleared on sign-in
   (profile sync / onboarding / sign-in from another device; check the web's local-state → server sync and any
   API upsert that writes an empty quiz over a saved one). Read-only production evidence for case 513 is allowed
   (`BEGIN READ ONLY … ROLLBACK`, counts/ids/timestamps only, Supabase MCP project pbrrlyoyyiftckqvzvvo). Fix it so a
   saved, non-empty set of answers is never overwritten by an empty or missing one (a deliberate retake still saves).
   Regression test that would have caught it. **If you cannot find a path that wipes them, STOP that item and report
   what you ruled out** — do not ship a guess.
2. **#81: name the missing step.** When Approve saves the verdict but the case cannot move to QC, the message names
   which required step is missing (in the reader's language). Take the missing step from what the completeness gate
   already returns. ⚠ `completeness.py` is marked DO NOT CHANGE: do not change its rules. If naming the step needs a
   change there beyond reading its output, STOP and report the options.
3. **One "reviewer's turn" rule (#81 + #86).** A single server predicate in `review_sla.py`: assigned, not terminal,
   not `interviewed`/QC-stage, and EITHER no verdict saved, OR reopened by QC and not yet re-decided, OR verdict saved but
   the case did not move to QC. Use it for `programme_overview.mine` and `band=open` ("My open") only. Served, never
   derived in the browser.
   **Do NOT change the nudges (`send_review_nudges`) or the overdue/SLA bands** — the old `assigned_at` clock would at
   once mail "overdue" about a reopened case. Leave `AWAITING_VERDICT` as it is for them; log a TD-NEW-<name> for
   "reopened case gets no verdict reminder" with the reason.
4. **#86: "Returned by QC" mark.** The My-open row for a reopened, not-yet-re-decided case shows "Returned by QC"
   (served flag). en final; ms + ta drafts marked for Sol's read; list every key.
5. **#86: the case link in the email.** Add a `case_link` variable (`{frontend}/admin/scholarship/<id>`) to the
   `qc_returned` email: the partner_comms allow-list, the built-in body, the seed. The stored template row in production
   holds `{dashboard_link}`: if a data migration is needed to put `{case_link}` into stored rows, it must update a row
   ONLY when its body still equals the old seed text exactly (an organisation's own edit is never overwritten), must be
   reversible, and must be safe for the old image (an unknown variable must not break the old code's rendering — check
   and test). Name it in the report; do NOT apply it anywhere. If a no-migration path exists that keeps the promise,
   prefer it and say why.
6. **What is owed does not move.** No change to blockers, verdicts or the completeness rules. If the verdict engine reads
   nothing new, no `VERDICT_ENGINE_VERSION` bump; say why.
7. **Docs.** `docs/decisions.md` dated entry (27 Nov 2026, #81 + #86, the reviewer's-turn rule, the email link);
   CHANGELOG under a heading for this; TD-NEW-<name> for anything found and not built.

## Rules

- Opus build. Targeted tests while building; at the end, ONCE, through the queue, from `halatuju_api`:
  `caffeinate -i -m -s python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- /Users/elanjelian/.venvs/halatuju-py311/bin/python -m pytest -q -n auto -p no:cacheprovider`
  (never the 3.12 .venv), plus `manage.py check` and `makemigrations --check --dry-run` with the same python.
  Web: run `npm ci` in this worktree's `halatuju-web` (never a node_modules symlink), then through the queue
  `npm run gates` and `npm run bundle-budget -- --gate` (median under 156 kB; never raise a budget, floor or ledger —
  if over, stop and report route-by-route growth). Leave mobile-check to the lead.
- Oversize files in `code-standards.json` `budget.oversize_files` may not grow past their budget. NEVER raise a budget,
  floor, ledger or allowance. If a change would push one over, put the code in a small new module instead.
- No production writes, no paid calls, no re-reads, no document downloads, no emails sent. No personal data in code,
  tests, docs or output: case numbers only; they/them; "the student".
- Bash: absolute paths; no `VAR=` at the start of a command; no `$()`; never `git add -A`; never bare `git stash`;
  NO PUSH. Work only in this worktree, on branch `req81-86-reviewer-turn`.
- Commits: honest type with the word "sprint", e.g. `fix: sprint #81 #86 - …`. Final commit trailers:
  `Phone-check: <plain line>` / `Migration: none` (or `<name> (additive|data)`) / `Services: both` /
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Report back (≤ 30 lines)

Commits (sha + one line); the quiz-wipe root cause and fix (or why you stopped); what the interviewer now sees on My open
and in the email; the message on a failed move to QC; the reviewer's-turn rule (file:line); nudges/bands untouched;
migration name or none; blockers/verdict unchanged and version decision; new/changed strings for Sol; test counts
(targeted, full API, web gates, bundle median); run time.

Stop at 120k. Commit your work. Send back a split plan.
