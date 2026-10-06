# Retrospective — request #28 follow-up: "Checked – still unknown" and Flag for review (2026-10-06)

Sprint (analysis #74, 7.5 h; the owner chose a notes log, option A). **LIVE 2026-10-06** — pushed
`66a622b1..9e849b9a`; builds SUCCESS, web `halatuju-web-00961-vjs`, api `halatuju-api-01108-w2p`.
Migration `0167_merchant_flags` (two tables, RLS + service-role policy) applied migrate-first by the
owner in the SQL editor; read back (tables, constraints, RLS, policies, ledger 0165-0167 contiguous;
Security Advisor nothing new).

## What was built
- **Fix:** a UI-only "Checked – still unknown" option in the native category select, mapped to
  `unsorted` + `decided_by='owner'`. Offered only on unsorted rows; a checked row shows it selected.
- **Feature:** `MerchantFlag` (one per organisation and shop, never deleted, reopenable) and
  `MerchantFlagNote` (open / note / close, each with author and time, kept for ever). Flag column,
  modal dialog (lazy chunk), "Flagged only" filter. Org-fenced: another organisation's read is
  byte-identical to "no flag"; writes need a shop the organisation's students used.
- **Room under the near-line gate:** 24 dead `scholarship.nextSteps.*` keys deleted from en/ms/ta
  (each proven unreferenced, with positive controls, across every registered worktree).

## What went wrong
1. **The first #28 release claimed a step the screen could not perform.** Re-choosing the selected
   value of a native `<select>` fires no change, so an already-unsorted shop could never be marked
   checked. Why: the rendered test started from a shop in ANOTHER category, so it exercised the
   one path that worked, and the completion report was written from the test, not from the owner's
   real case. Fix: the new test starts from an untouched unsorted row (bite-checked); lesson
   recorded below; the wrong completion draft (#72) was withdrawn before approval.
2. **The push was refused locally by a gate that landed minutes earlier** (near-line bundle margin,
   0.15 kB). Why: our 0.067 kB of strings took two student routes to 0.10 / 0.13 kB of room. Fix: the
   new gate worked as intended — weight was taken off (dead keys), not the line raised.

## Numbers
pytest 8007 passed / 3 skipped (pre-rebase tree; the later commits are docs, bundle script and
catalogue only) · jest 4036 / 243 · i18n 5402 keys · bundle median 227.818 kB, `/scholarship/application`
273.625 of 274, `/scholarship/apply` 271.596 of 272.
Time: planned 10 h for the whole request (2.5 + 7.5), actual about 5 h (2 + 3).
