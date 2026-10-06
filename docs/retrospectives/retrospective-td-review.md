# Retrospective — Tech Debt Review Pass (2026-03-15)

Follow-up review of the Bug Fixes & Auth Gating sprint. Separate session.

## What Was Done
- Reviewed error/loading/404 pages — found hardcoded English text, no i18n
- Rewrote all three pages with `useT()` and trilingual translations (7 keys in `errors` section)
- Fixed `text-red-400` → `text-primary-500` in error.tsx for brand consistency
- Removed dead `getJSON`/`setJSON` from storage.ts (added but never used)
- Updated tech debt register: TD-014, TD-042, TD-048 marked resolved
- Corrected CHANGELOG (stale reference to removed helpers, constant count 22→19)

## What Went Wrong

1. **Error pages shipped without i18n in the prior session.**
   Why: TD-042's spec said "helpful error messages in BM/EN/TA" but the implementation used hardcoded English. The spec wasn't read before implementing.
   Fix: Always read the tech debt item's "What consistent looks like" field before implementing — it defines acceptance criteria.

2. **`getJSON`/`setJSON` were added as dead code.**
   Why: Speculative utility functions with no call site. YAGNI violation.
   Fix: Don't add utility functions unless at least one call site exists.

## Numbers
- Files fixed: 4 (storage.ts, error.tsx, loading.tsx, not-found.tsx)
- Message files updated: 3 (en.json, ms.json, ta.json — 7 keys each)
- Dead code removed: 2 functions (getJSON, setJSON)
- Backend tests: 424 passing, 0 failures
