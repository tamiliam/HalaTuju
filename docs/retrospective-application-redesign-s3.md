# Retrospective — `/scholarship/application` redesign, Sprint 3 (funding) — v2.4.2, 2026-05-27/28

Third sprint of the Step-4 redesign. Plan: `docs/scholarship/application-redesign-plan.md`. Commit `1bf7a09`;
migration `scholarship 0013` (migrate-first).

## What Was Built
The funding tab moved from itemised RM amounts to **"How you'd use the support"**: a stated cap ("up to RM3,000 —
the actual amount may be lower…"), a programme-length dropdown, a **tick-only** category checklist (living, transport,
accommodation, books, device, tuition *with "often covered" helper*, something-else → free text), and an optional
open box ("how you're planning to fund your studies / how you'd manage without"). **No total, no per-category
amounts, no balance question.** Backend: `FundingNeed` gained `categories` (JSON) + `funding_note` (text) +
`programme_months` (int) via additive migration `0013` (0 existing rows); **funding-complete = ≥1 category ticked**.
Legacy amount columns kept as dead columns (see TD-059).

## What Went Well
- **The S2 lessons paid off immediately.** The subagent **kept** its screenshots this time (per the updated spec), so
  I reviewed the correct funding UI directly — no round-trip; and I **serialised** the build vs the screenshot dev
  server (no `.next` collision). The two S2 "what went wrong" items did not recur.
- Migrate-first `0013` verified (3 columns + migration row, 0 funding rows) before the push — zero-risk additive.
- Stitch on `GEMINI_3_FLASH` eventually persisted the correct screen within reach.

## What Went Wrong
1. **Stale Stitch duplicates muddled the sign-off.**
   - *Symptom:* two "Funding Support" screens existed, **both** showing the removed total/amount design (RM 18,000 /
     per-year estimates); my latest (correct) FLASH prompt's screen wasn't among them when I first polled.
   - *Root cause:* a timed-out Stitch generation doesn't fail cleanly — earlier timed-out attempts (from prior turns)
     **persisted later** as same-titled duplicates, so polling `list_screens` surfaced old attempts, not my newest.
   - *System change:* lesson added — after a Stitch timeout, when polling, **verify the screen's content matches your
     latest prompt** (don't trust the title or assume the first/newest-listed screen is yours); stale timed-out
     attempts accumulate as indistinguishable duplicates. FLASH lands within the client window more reliably.

## Design Decisions
Funding "contribution" model (capped RM3,000, no total, tick-only) — recorded in the plan doc. Nothing new
architectural.

## Numbers
- 12 files; migration `0013` (3 additive AddField, migrate-first, 0 rows). Full backend pytest **1119**; full jest
  **116**; i18n parity **1209**.
- Both services deployed (web `halatuju-web-00215-xsh`, api `halatuju-api-00169-tph`); api health 200; v2.4.2;
  verified live.
