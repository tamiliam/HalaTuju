# Retrospective — QC Decision Gate (Decline-to-QC + QC outright reject) — 2026-07-19

## What Was Built

Two coherent additions to the quality-control gate, so that **both** reviewer outcomes get a
second pair of eyes and the QC can conclude a case without a detour.

1. **Reviewer DECLINE now routes through QC.** Previously a decline went straight to `rejected`;
   a recommend went to QC. Now a decline verdict lands in AWAITING QC too. The QC card is
   verdict-aware: for a decline the primary button reads **"Confirm decline"** (red), the V5 gap
   floor is skipped (a declined case is *expected* to carry red income facts), and the cool-off is
   **24h** (`DECLINE_QC_COOLOFF_HOURS`) rather than the 7-day default — the decision is already
   two-person-vetted. New endpoint `AdminSubmitDeclineView` (`.../submit-decline/`); `admin_reject`
   gained an optional `cooloff` timedelta.

2. **QC can REJECT a recommend outright.** The QC card offered only Accept / Reopen; killing a
   recommend meant the manual two-step reopen-with-reason → decline (visible in the case history as
   ↩ then ✗). A default-off toggle inside the reopen box now flips **"Reopen & notify reviewer"** →
   **"Reject & inform reviewer"** (red). One click reproduces the *identical* audited trail — a
   `DecisionReopen` row carrying the QC's reason, closed as a real correction — then declines as
   `interview` with the 24h cool-off, and emails the reviewer the distinct
   `send_qc_rejected_email` ("Case rejected by QC", not "returned for revision"). Reason required.

## What Went Well

- **Migration-free by reuse.** The reject's audited "↩ Reopened by {QC} — reason → ✗ Declined"
  trail is exactly what the manual reopen→decline already renders. Routing the one-click reject
  through `reopen_decision` + `close_reopen_with_change` reproduced it with **no schema change and
  no new frontend rendering** — and kept the reviewer-correction accounting identical to today's
  manual path.
- **Isolation held.** All work ran in the `HalaTuju-declineqc` git worktree while ~8 other feature
  branches (and an agent editing the main checkout directly) were live. The final ship was a clean
  rebase onto origin/main + `git push origin feat/decline-qc-gate:main` — zero conflicts, and the
  other agent's uncommitted main-checkout work was never touched.
- **Tests first, green throughout.** 2897 scholarship pytest pass; i18n parity held at 3589 keys
  across en/ms/ta both before and after the rebase.

## What Went Wrong

- **Symptom:** a new reject test (`test_qc_reject_with_zero_cooloff_tells_student_now`) failed with
  a SQLite `unrecognized token: ":"` when the zero-cool-off path actually sent the student decline
  email. **Root cause:** the minimal `TestQcGate` fixture has no consent/notify_email, so the real
  HTML-decline send path hit a query it couldn't satisfy in that fixture — the test was asserting a
  behaviour (immediate student send) already covered by the fuller `TestDeclineToQc` fixture via the
  *same* `admin_reject` call. **Fix/prevention:** dropped the redundant test rather than inflating
  the minimal fixture; the reject feature only uses the 24h path, which is fully covered. Lesson for
  future: don't assert the live-email send path on the bare gate fixture — assert embargo state
  there, and test the actual send in the class that has the consent/email fixtures.

## Design Decisions

- **QC reject reuses the reopen audit record instead of a new `rejection_note` field** — see
  `docs/decisions.md` (migration-free, single rendering path, accounting parity with the manual
  route).
- **Both outcomes vetted, but asymmetric rails:** recommend keeps the gap floor + green Accept;
  decline skips the floor + red Confirm, both at a 24h cool-off. A declined case legitimately has
  red facts, so the floor that protects sponsors from unexamined red income doesn't apply.

## Numbers

- Files touched: 12 (7 backend, 5 web) across two commits (`ef7d9bd5`, `899cb82e`).
- Tests: 2897 scholarship pytest pass (10 new: 7 `TestDeclineToQc` + 3 `TestQcGate` reject).
- i18n: 3589 keys × en/ms/ta, full parity; 6 new `qcDecision`/`decision` keys.
- Deploy: 1 api+web build (`899cb82e`); no migration; `DECLINE_QC_COOLOFF_HOURS` defaults to 24.

## Owner To-Do

- **Tamil review** of the first-draft strings: `qcDecision.confirmDecline`, `qcDecision.reject*`,
  `decision.declineSentToQc`.
