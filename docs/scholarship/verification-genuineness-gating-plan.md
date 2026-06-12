# Plan — Gate verdict confidence on genuineness ("a typed sheet must never read CERTAIN")

**Status: DEFERRED (parked 2026-06-13).** A real gap, but an edge case for our population (high-performing
students, not forgers) — lower priority than the immediate fixes in flight. Captured here so it isn't lost.
**Do not start without an explicit go-ahead** (run `Settings/_workflows/implementation-planning.md` to scope
the sprint when picked up). Owner steer: "edge case after all; there are other more immediate fixes."

Tracked as **TD-114**. Builds on the completed verification-assurance programme
(`verification-assurance-roadmap.md`, layers 1–3) — this is the layer-2 *hardening* that programme deferred.

---

## The finding (test account #16, 2026-06-13)
Every document #16 uploaded was a **typed sheet** (typed text / screenshots, no real card or official format).
Yet the cockpit verdict read **Identity Probable · Academic Probable · Pathway CERTAIN ✓ · Income CERTAIN ✓** —
two facts still green off forged-by-typing evidence. This is exactly the "a sponsor could brush aside our review"
risk the programme was meant to close.

### Live demo evidence (genuineness re-run on the 4 unscored covered docs, Gemini-only)
| Doc | Re-run verdict | Effect |
|---|---|---|
| STR | `low_confidence` (typed text snippet) | — |
| Birth certificate | `low_confidence` (typed, no JPN format) | — |
| Mother's IC (12 Jun, the one income uses) | `low_confidence` (text only, no card) | — |
| Mother's IC (06 Jun, older) | `likely_genuine` (a real MyKad) | — |
| **Income fact** | — | **CERTAIN → Probable** (capped `document_not_genuine`) ✅ |
| **Pathway fact** | — | **CERTAIN → still CERTAIN** ❌ |

Two lessons, both confirmed live:
1. **The engine is sound when it runs** — Income dropped the moment genuineness scored its docs, and it was
   discriminating (passed the one genuine card, flagged the typed one). Not blunt, not blanket-fail.
2. **Pathway stayed green** — because the offer letter is never fingerprinted. Backfilling alone can never
   close this; the structural rule below is required.

---

## Root causes
**Hole A — the check didn't run on covered docs.** Genuineness is computed *at upload only* and is **not
backfilled**. #16's STR / mother's IC / birth cert were uploaded in the window between the Sprint-1 and Sprint-2
deploys, so they sat permanently unscored — and the verdict treats "unscored" as "fine".

**Hole B — structural (the dangerous one).** Even with a perfect backfill:
- `offer_letter` and `salary_slip` are **deliberately un-fingerprinted** (too varied), so Pathway can reach
  CERTAIN off a typed offer letter, always.
- More fundamentally: **a fact reaches CERTAIN on field-match alone** (typed text matches the application) —
  it never requires that the *document is real*. Field-match and genuineness are two different questions, and
  CERTAIN today answers only the first. A typist (which is all a typed sheet is) passes.

---

## Approved design (owner chose "Gate CERTAIN on genuineness", 2026-06-13)
1. **Gate CERTAIN on genuineness.** A fact cannot be `verified` (Certain) unless a genuineness check **actually
   ran and passed** (`likely_genuine`) on its anchor document(s). Not-run / not-covered / fake → **`review`
   (Probable) at most**, never Certain.
2. **A confirmed fake bites harder than "unsure".** When an anchor doc is an affirmed typed/wrong-type fake
   (`low_confidence` / `wrong_type` / `not_an_ic`), cap the fact **below Probable** — to an *Unsure* level —
   not just one notch to `review`. (Today `_apply_genuineness_caps` only downgrades `verified`→`review`.)
   **Open design Q:** the engine has no distinct "Unsure" status today (`verified`/`review`/`recommend`/`gap`).
   Decide at build: introduce a status/band, or reuse `review` with a stronger, distinct caveat code. Map to the
   FE bands (Certain/Probable/Unsure/Can't-verify) deliberately.
3. **Cover the offer letter** (Pathway's blind spot) — add `offer_letter` to the genuineness docs with a
   best-effort, institution-varied prompt (lower bar than the standardised docs, but enough to catch a typed
   sheet vs a real letter). `salary_slip` stays best-effort/uncovered — but under rule 1 an unscored/uncovered
   salary slip can no longer leave **Income** at Certain on its own.
4. **Backfill command** — a one-off management command to re-scan already-uploaded covered docs (Gemini-only;
   respects the cost cap) so pre-feature uploads (like #16's batch) get scored instead of sitting silent.

### Anchor-doc map (to gate each fact)
| Fact | Anchor doc(s) for the genuineness gate |
|---|---|
| Identity | `ic` (already capped in `_verdict_identity`) |
| Academic | `results_slip` |
| Pathway | `offer_letter` (to be covered — rule 3) |
| Income | `str` / `parent_ic` / `epf` / `birth_certificate` (+ `salary_slip` best-effort) |

### Further open questions (resolve at planning)
- **Multiple anchors, mixed signals** (e.g. #16: one genuine mother's IC + one typed): does *any* fake anchor
  cap the fact, or only the doc the fact actually relies on? (Lean: the doc the fact relies on — the income
  route uses the latest/earner IC.)
- **"Not run" vs "not covered" vs "fake"** — three different reasons a fact can't be Certain; should they read
  differently to the officer (e.g. "genuineness not yet checked" vs "looks fake")? The earlier
  "silence ≠ pass" point argues yes — show a quiet "check not run" state so unscored is visibly not cleared.
- **Tightness vs over-blocking** — a genuine-but-poor scan can score `low_confidence`; Unsure (not red) is the
  right ceiling so we never hard-block a real student over photo quality. Keep SOFT (reviewer is authority).

---

## Scope (one reviewable sprint; no migration)
- `verdict_engine.py` — the gate (rule 1) + the harder cap (rule 2) + extend `_FACT_GENUINENESS_DOCS` with
  `pathway:[offer_letter]` and the identity/pathway anchors.
- `vision.py` — add `offer_letter` to `_GENUINENESS_DOCS` (best-effort prompt); wire into
  `run_field_extraction_for_document` (already flag-gated).
- New management command — backfill genuineness on existing covered docs.
- i18n — any new caveat / "not-checked" copy (en/ms/ta).
- Tests — typed anchor → Unsure; unscored/not-covered anchor → Probable not Certain; genuine anchor → Certain;
  **#16's exact folder as a regression** (must NOT yield any Certain).
- Flag — reuse `DOC_GENUINENESS_CHECK_ENABLED` (the gate only tightens when genuineness is on).

## Verification
`python -m pytest apps/scholarship` (new gate tests + golden verdicts intact); replay #16 → no Certain;
genuine-doc fixtures still reach Certain; i18n parity; `next build` clean.

## Not in scope
Hard-blocking / money-gate (still owner-deferred); forgery-proofing (out of threat model); re-fingerprinting
salary slips (too varied — name cross-checks + interview carry them).
