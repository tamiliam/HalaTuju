# Check 1 — Identity/IC OCR hardening (sprint plan)

**Status:** PLANNED as one sprint — to build **after the next compact**. Branch
`check1/identity` already holds the FIRST fix (name-truncation, done + tested, NOT
deployed); the rest of this list ships with it as one batch. Part of the master
pipeline (`application-processing-pipeline-plan.md`, CHECK 1) and TD-081.

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

2. **Address "MyKad" + card-label leak (deterministic strip).** The extracted IC address
   reads *"MyKad, C65B JALAN SEJATI, …, KEDAH"* — "MyKad" is the **card's own label**, not
   the address (same on the parent IC). Strip "MyKad" and other card labels
   (WARGANEGARA, ISLAM/AGAMA, LELAKI/PEREMPUAN, etc.) from `_extract_address`. Cheap,
   `vision.py` only. (Address stays a **soft data point** per the IC display — not a blocker.)

3. **Marker-less names (Chinese / Christian / Chindian, no A/L·A/P).** The marker anchor
   doesn't fire → the name falls to the weaker "line-after-NRIC" tier and can even leak
   into the address. Best fixed by the Gemini fallback (#5); add deterministic guards
   where cheap.

4. **Blurry NRIC digit misreads (8↔6 on low-res scans).** A single misread digit fails the
   exact match (e.g. YESWINDRAN `…0681` vs typed `…0661`). Gemini second-read (#5) +
   clearer, action-specific guidance (#6).

5. **★ Gemini fallback for the IC (the central lever — the owner's "OCR first, then Gemini
   if necessary").** Today the IC is **deterministic-only**; supporting docs already use
   Gemini. When the cheap read is **low-confidence** (name mismatch, marker-less name,
   blurry NRIC, noisy address), call Gemini to re-extract **NRIC / Name / Address** as a
   clean second opinion. **Cost-gated** — only fires when the deterministic read is shaky,
   so most uploads stay free. Reuse the existing `_call_gemini_json` seam (mock in CI;
   never a live call in tests). This one change improves names (#3), NRIC (#4) **and** the
   address (#2) together. Needs a confidence/uncertainty signal to decide when to escalate.

6. **Gopal name-mismatch guidance is one-sided (NEW, owner 2026-06-02).** A name mismatch
   is **bidirectional** — it can be the **OCR misreading the card** *or* the **student
   having typed their name wrongly in their profile**. Gopal currently implies the
   *document* is wrong ("re-upload a clearer photo"). It must offer **both** paths: (a)
   re-upload a clearer photo if the photo was misread, **or** (b) **edit the profile name**
   (with a **/profile link**) if they mistyped it. NB: the IC redesign removed the old
   `VisionChip` "name-soft" message that carried the profile link — so this guidance now
   lives in **Gopal** (`help_engine.py` name-mismatch prompt/fallback copy, en/ms/ta), and
   the link must come back via Gopal.

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
