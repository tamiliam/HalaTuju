# Retrospective — Now sprint 2 (2026-10-01): TD-253 and TD-207

**Scope:** build the owner's TD-253 ruling (every interview agenda item carries an answer the
reviewer chose; silence is refused) at both ends, and make "Forgot password" work for an admin past
onboarding (TD-207). Built by one agent; an adversarial reviewer reads the diff before the lead
commits. No migration, no data change, no ledger raised.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-253 api | `interview_completeness.py`: `agenda_keys`, `is_answered`, `missing_agenda_items`, `decision_gate_applies`, `decision_refusal`; wired into `interview/submit/` and `record-verdict/` | `test_interview_completeness.py` (18 tests; the five writing roles looped) |
| TD-253 web | `interviewCompleteness.ts`; `isDecisionReady(…, interviewComplete)`; cockpit hint + submit refusal in words | `interviewCompleteness.test.ts`, `view.decision.test.tsx` (+6, roles looped), `officerCockpit.test.ts` (+1) |
| TD-207 | `recovery_session.is_fresh_recovery_for`; `request.auth_claims` on the middleware | `AdminSetPasswordTest` (+7) |

## Decisions the ruling did not make (recorded in decisions.md)

- **A rationale is not required with a verdict, nor a verdict with a rationale.** The screen has one
  verdict button (Resolved) and an answer box. Asking for a verdict would force "Resolved" on an
  unresolved point; asking for words would refuse the bare Resolved the record has always shown as
  "Resolved ✓". The ruling's "See conclusion" is a typed answer.
- **Delete counts as a choice.** It is the existing "this question does not apply" act. It also means
  a reviewer could delete every item, the Motivation item included — flagged to the owner.
- **A reopened decision is the reviewer's again**, so the gate binds there (the reopen unlocks the
  interview, so nothing is stranded). A decision already recorded and not reopened, and everything at
  QC, are not reached.

## What went well

- The agenda was defined against what the cockpit DRAWS, not against `interview_agenda_full` alone:
  the cockpit suppresses Check-2-owned anomalies and the serializer dedupes two identity flags, so a
  server list built from the function would have refused submits over questions nobody could see.
- Seven existing tests walked a case through submit or decide on an empty interview; each now answers
  the agenda through one helper (`factories.answered_findings`), not by weakening the gate.

## What bit

- **The `/profile` route already prints at its first-load line (310 / 310 kB) on the unchanged tree.**
  Measured by building with the message files at HEAD: the same 310 prints. The two new strings add
  about 0.1 kB gz to every ledgered route (shortened once to cut it); `bundle-budget` passes, but the
  "0.5 kB under the line" margin was already gone before this sprint. Reported to the lead.
- The bundle measure was slower than it needed to be: a gz figure taken from the build manifest does
  not equal Next's printed figure, so only a like-for-like build (HEAD messages vs new) gives a delta.

## Not done

- No live test of the reset (no production access). How the owner tests it is in
  `halatuju_api/CLAUDE.md`'s state note.
- The new Tamil (two strings) awaits the owner's reading.
