# Retrospective — Post-award S7: bank-details capture

**Date:** 2026-06-29
**Branch:** `feat/bank-details` (worktree off `origin/main`; rebased onto current main before close)
**Migration:** `scholarship/0081_bankaccount` (CreateModel + additive `bank_statement` choice; table + RLS applied migrate-first via Supabase MCP)
**State:** built + tested + committed; **deploy owner-gated** (push = deploy), table already on prod.

## What Was Built

An `awarded`/`active` student now captures their bursary **payout account** in the Action Centre:
1. A `bank_details_missing` task appears (always student-visible, independent of the Check-2 flag).
2. They **upload a bank statement/passbook** → the system **field-extracts** Bank Name / Account Number /
   Account Holder (Gemini, riding the existing document-assist pipeline).
3. The three values **pre-fill a confirm form** → the student **reviews/corrects** them → **Save**.
4. **The holder must be the student** — a hard gate re-checked server-side against the application name
   (`vision.name_match`); a different name is refused (`bank_holder_mismatch`) and **Cikgu Gopal** coaches
   it, as he does a field we couldn't read clearly (`bank_details_unclear`).
5. Saved → the three fields land in a dedicated RLS'd `bank_accounts` table. **Shown on no surface yet.**

New: `BankAccount` model + `bank_statement` doc type; `GET/POST /scholarship/bank-account/`;
`resolution.sync_bank_details_item`; `BankDetailsTask` card in `ActionCentre.tsx`. +20 backend pytest.

## What Went Well

- **Reuse over reinvention.** The feature is large in surface but small in genuinely new plumbing — it rides
  the existing document-assist pipeline (`GEMINI_EXTRACT_DOC_TYPES` + `extract_document_fields` +
  `doc_student_verdict`), the Action Centre (`ResolutionItem` + `ActionCentre.tsx`), and Gopal
  (`verdict_for_document` + `VERDICT_GUIDANCE`). The only new model is the one that *had* to be new
  (financial PII in its own RLS'd table).
- **Upload-THEN-confirm caught the right risk.** Pre-filling from the read but making the student confirm
  (rather than auto-saving the OCR) directly addresses the money-safety hazard — a misread digit can't be
  silently committed. The serializer also rejects a too-short account-number fragment.
- **Local test on the real server.** Drove the actual running Django server (not the test harness) against a
  seeded awarded student through every path — task appears → confirm (match) → resolve, and the two hard
  rejections (holder mismatch, short number) + Gopal verdict mapping. Caught nothing new (the test suite had
  it), but proved the full middleware→view→model stack end-to-end before close.

## What Went Wrong

1. **An awarded student couldn't reach the Action Centre / upload at all (six API tests 403'd).**
   *Symptom:* every endpoint test returned 403 `no_application`. *Root cause:* `_current_application` —
   the helper that finds the student's working application for the upload + Action Centre + bank endpoints —
   filtered on `POST_SHORTLIST_EDITABLE`, which stops at `interviewed`. The post-award lifecycle (S1–S6)
   added `awarded`/`active`/`maintenance` states but **never extended the student-surface lookup to include
   them**, so the funded student's working surface was silently unreachable. *Fix / system change:*
   broadened `_current_application` to span the funded states (verified safe — `revert_if_profile_incomplete`
   only acts on `profile_complete`, `switch_income_route` never un-submits). **Lesson (cross-cutting, added
   to `docs/lessons.md`):** when a sprint adds lifecycle states, audit the *surface-lookup* helpers that gate
   where a user can act — a new status is invisible to the UI until the lookup includes it.
2. **The Django interactive shell mangled the seed script.** *Symptom:* `manage.py shell` heredoc choked on
   the blank lines inside a `for`/`def` block (the interactive console treats a blank line as end-of-block),
   throwing `SyntaxError` and leaving nothing seeded. *Root cause:* piping a multi-line block to the
   *interactive* console, which has REPL block semantics, not script semantics. *Fix / system change:* run
   one-off Django scripts in non-interactive (script) mode — `manage.py shell -c` running the file's contents
   — not piped stdin. Minor; noted here, not promoted (low recurrence).

## Design Decisions

(Logged in `docs/decisions.md`: dedicated `BankAccount` model vs `OnboardingResponse.answers`; upload-then-
confirm vs auto-save; the hard holder==student gate; broadening `_current_application` to the funded states.)

## Numbers

- **1 commit** (code) + the close commit; migration `0081`.
- **Backend:** 1783 scholarship pytest (+20 new in `test_bank_account.py`); `makemigrations --check` clean.
- **Frontend:** `next build` clean; i18n en/ms/ta parity **3000×3** (Tamil first-draft on the new strings).
- Migrate-first applied to prod (`bank_accounts` table + RLS); security advisor INFO-only (matches the
  sibling tables `disbursements` / `whatsapp_messages` / `bursary_agreements`).
