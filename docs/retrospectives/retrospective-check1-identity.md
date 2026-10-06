# Retrospective — Check-1 Identity/IC OCR hardening

**Date:** 2026-06-02 · **Branch:** `check1/identity` → `main` (`3d110a4`) · **Deployed:** yes (api `…00250-c2w`, web build SUCCESS; no migration)

## What Was Built

The first of the four "facts" (Identity / Academic / Income / Pathway) got a dedicated Check-1 hardening pass so the student gets **good feedback on the IC they upload**. Six issues, one batch, one deploy:

1. **Name truncation** *(shipped earlier, `68afd50`)* — a parentage marker (A/L · A/P · BIN · BINTI · S/O · D/O) at the END of the MyKad name line means OCR line-broke the surname onto the next line; it's now appended (`_with_trailing_surname`). *"THERESA ARUL MARY A/P" → "… A/P A.PHILIPS"*.
2. **Address card-label strip** — `_extract_address` now drops any line made up entirely of MyKad card chrome (`_is_card_label_line`: MyKad / WARGANEGARA / ISLAM / AGAMA / LELAKI / PEREMPUAN / PENDAFTARAN / NEGARA), so the surfaced home address no longer reads *"MyKad, C65B JALAN SEJATI…"*.
3 + 4 + 5. **★ Gemini IC second opinion (cost-gated)** — the central lever. `run_vision_for_document` keeps the free deterministic read, then `_should_gemini_ic()` escalates to a Gemini **image** read ONLY when low-confidence (a core field missing, OR the read disagrees with the typed profile). `_gemini_ic_second_opinion()` sends the card image to Gemini (`_call_gemini_json` extended with an optional `image=`); `_merge_ic_reads()` folds it in conservatively — Gemini wins a core field only when it matches the profile and the deterministic read didn't; the soft address always prefers the cleaner Gemini value. Behind `IC_GEMINI_FALLBACK_ENABLED` (default ON). One change covers marker-less names (#3), blurry-digit NRICs (#4), and noisy addresses (#2) together.
6. **Cikgu Gopal name-mismatch guidance is now bidirectional** — a mismatch can be a misread photo OR a mistyped profile name. `help_engine.VERDICT_FIX_HINT['name_mismatch']` instructs the coach to offer BOTH fixes without assuming which is wrong; `DocumentHelpCoach` renders an "Edit your name in your profile" → `/profile` link whenever `verdict === 'name_mismatch'`. Fallback copy rewritten bidirectionally in en/ms/ta + new `scholarship.docs.help.editProfileName` key.

## Numbers
- **1558** backend pytest (522 scholarship) · **231** jest · i18n parity **1793** (en/ms/ta) · `next build` clean.
- **+17** backend tests this sprint (vision pure helpers + DB-backed Gemini-escalation integration + help-engine prompt assertions).
- **1 deploy** (both services), **0 migrations**.

## What Went Well
- **Cost discipline by construction.** The Gemini path is gated on a *low-confidence* signal, not on every upload, so an ordinary clean IC never costs a model call — and it's killable via one env var. The escalation criterion (missing field OR disagrees-with-profile) is exactly the case where the student would otherwise see a scary mismatch, so the spend lands where it earns its keep.
- **Conservative merge kept the model on a leash.** `_merge_ic_reads` only lets Gemini overwrite a core field when it *agrees with the profile* — so a confident deterministic match can never be flipped by a hallucinated second read. The student-facing verdict still comes from the deterministic matchers.
- **One mock seam.** Reusing `_call_gemini_json` (extended, not forked) meant every test runs with zero billable calls and the existing patch points kept working.

## What Went Wrong
- **`NameError: _STR is not defined` at module load.** *Symptom:* the first test run failed at collection — `_IC_GEMINI_SCHEMA` referenced the `_STR` shorthand, which is defined ~80 lines LOWER in `vision.py` (in the supporting-doc section). *Root cause:* I placed the new IC helpers high in the file (next to `run_vision_for_document`) but reused a module constant that is only bound later — Python executes module-level bindings top-to-bottom, so a forward reference at import time throws. *Fix applied:* inlined the schema literal (`{'type': 'string'}`) instead of the forward-referenced constant. *System change:* caught immediately because gates were run before commit — no workflow change needed, but noted in `lessons.md` as a module-load-order gotcha for future shared-constant reuse.

## Design Decisions
See `docs/decisions.md` → "Cost-gated Gemini IC second opinion (escalate-on-low-confidence + conservative merge)".

## Carried Forward
- **Live billable smoke** of the IC Gemini path with a real low-confidence MyKad (user-run) — the only thing CI can't do.
- The same Check-1 treatment for **Academic / Income / Pathway** documents (TD-081 residual).
