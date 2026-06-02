# Check 1 — Identity/IC OCR hardening (sprint plan)

**Status:** ✅ BUILT (2026-06-02, branch `check1/identity`) — all six items done +
tested, gates green (522 scholarship pytest · 231 jest · i18n 1793 · `next build`
clean). **NOT deployed yet** (no migration; deploy = merge `check1/identity` → `main`
+ push, user-gated). Part of the master pipeline
(`application-processing-pipeline-plan.md`, CHECK 1) and TD-081.

> **Principle (owner):** the student must get **good feedback on every document they
> upload** — otherwise it's more work for us later. Check 1 is upstream, so getting it
> right de-risks all four facts (Identity / Academic / Income / Pathway) downstream.

This sprint = **the Identity/IC document only** (the first of the four facts; we'll do
Academic / Income / Pathway document Check-1 in later passes).

---

## The IC Check-1 issue list

1. **Name truncation — ✅ DONE (branch `check1/identity`, commit 68afd50, not deployed).**
   When `extract_mykad`'s name line ENDS with a parentage marker (A/P, A/L, BIN, BINTI,
   S/O, D/O), the surname spilled to the next OCR line → append it. *"THERESA ARUL MARY
   A/P" → "THERESA ARUL MARY A/P A.PHILIPS"*. Deterministic; 29 vision tests (+2). Side
   effect: the verdict's Identity now reads a clean "Name match" instead of the
   "OCR truncated it…" workaround.

2. **Address "MyKad" + card-label leak (deterministic strip) — ✅ DONE.** The extracted IC
   address read *"MyKad, C65B JALAN SEJATI, …, KEDAH"* — "MyKad" is the **card's own label**,
   not the address. New `_ADDRESS_LABEL_TOKENS` + `_is_card_label_line()` drop any line made
   up entirely of card chrome (MyKad / WARGANEGARA / ISLAM / AGAMA / LELAKI / PEREMPUAN /
   PENDAFTARAN / NEGARA …) inside `_extract_address`. Cheap, `vision.py` only; address stays a
   **soft data point**, not a blocker. +3 tests.

3. **Marker-less names (Chinese / Christian / Chindian, no A/L·A/P) — ✅ COVERED by #5.** The
   marker anchor doesn't fire → the name falls to the weaker "line-after-NRIC" tier. When that
   produces a name that mismatches the typed profile, #5 escalates to the Gemini second opinion,
   which reads the printed name correctly. (No mismatch vs profile → no cost, by design.)

4. **Blurry NRIC digit misreads (8↔6 on low-res scans) — ✅ COVERED by #5.** A single misread
   digit fails the exact match (e.g. `…0681` vs typed `…0661`). #5's Gemini second opinion reads
   the **card image** (not just the OCR text), so it can recover the misread digit; the merge
   only adopts Gemini's NRIC when it **matches the profile** and the deterministic read did not.

5. **★ Gemini fallback for the IC — ✅ DONE (the central lever; owner's "OCR first, then Gemini
   if necessary").** `run_vision_for_document` now runs the cheap deterministic read first, then
   `_should_gemini_ic()` escalates **only when low-confidence** (a core field missing, OR the read
   disagrees with the typed profile). On escalation `_gemini_ic_second_opinion()` sends the card
   **image** to Gemini (`_call_gemini_json` extended with an optional `image=`) → clean
   `{nric, name, address}`; `_merge_ic_reads()` folds it in conservatively (Gemini wins a core
   field only when it matches the profile and the deterministic read didn't; the soft address
   always prefers the cleaner Gemini value). Behind knob **`IC_GEMINI_FALLBACK_ENABLED`** (default
   ON, env `'0'` to disable). One change improves names (#3), NRIC (#4) **and** address (#2).
   Mock seam in CI — never a live call in tests. +15 tests (pure helpers + DB integration).

6. **Gopal name-mismatch guidance now bidirectional — ✅ DONE.** A name mismatch can be the OCR
   misreading the card **or** the student having typed their name wrongly. `help_engine` gained a
   per-verdict `VERDICT_FIX_HINT`; the `name_mismatch` hint instructs Gopal to offer **both** paths
   without assuming which is wrong. The **/profile link** comes back via the coach: `DocumentHelpCoach`
   renders an "Edit your name in your profile" → `/profile` link whenever `verdict === 'name_mismatch'`
   (works for AI and fallback copy). Fallback copy in en/ms/ta rewritten bidirectionally + new
   `scholarship.docs.help.editProfileName` key (i18n parity 1793). +2 prompt tests.

---

## Approach / sequence (within the sprint)
1. **Deterministic, cheap:** name truncation ✅ + the address label strip (#2). No AI.
2. **The Gemini fallback (#5)** — the core build: a confidence gate + the Gemini IC
   re-extract, behind the cost knob; covers #3, #4, and cleans #2 further.
3. **Gopal guidance (#6)** — prompt/copy + the profile link, en/ms/ta.

## Constraints
- **Cost-gated AI:** Gemini only on low-confidence; reuse the `_call_gemini_json` seam;
  **mock in CI**, never a live model call in tests; ship behind the existing cost knob.
- **Address stays soft** (data point, not a blocker) per the IC per-item display.
- **British English; i18n parity en/ms/ta** (Tamil first-draft). Gates: pytest + jest +
  `check-i18n` + `next build`; deploy migrate-first only if a migration appears (none
  expected — these are extraction/serializer/copy changes).
- **One deploy** for the whole Identity batch (name fix + #2 + #5 + #6).

## Handoff (post-compact pickup)
- Branch **`check1/identity`** = the name-truncation fix (commit `68afd50`) + this plan,
  **pushed, not deployed**. Resume here; build #2, #5, #6 on it; then gates + one deploy.
- `main` is clean at the UI-polish batch deploy (`6860052`). All earlier verification
  passed except this Check-1 hardening (queued).
- Later passes: the same Check-1 treatment for **Academic / Income / Pathway** documents,
  and the bigger **`/application` state machine** sprint (form XOR queries + Check-2
  emails) — both already in the master plan.
