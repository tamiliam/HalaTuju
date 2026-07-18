# Brief — TD-161: unify the pathway reconciliation (offer ↔ declaration), band-aware, one detector

**Status:** SHIPPED (code) 2026-07-18 — commits `917d43cc` + `ad2d33ac` (initial confirmed-only slice)
then `6bf2660e` (the unified, band-aware rewrite). NO migration; no `MODEL_VERSION` bump. **Unpushed —
owner gates the deploy** (push = deploy). Live test case: **#43** (STPM-declared, PISMP-confirmed).

## Problem

When a student declares pathway A at apply time then uploads/confirms an offer for a *different*
pathway, the record was left contradictory and misclassified. Root causes:

- **`confirm_pathway` never wrote `chosen_pathway`** — for anyone. On "yes" it wrote `chosen_programme`
  + `pathway_confirmed_at`, and (for a pre-U-declared pathway) tidied `pre_u_*` — but never the pathway
  **type**. So #43 sat `chosen_pathway=stpm` next to a confirmed **PISMP** `chosen_programme`.
- The pathway verdict **suppressed the confirm once `pathway_confirmed_at` was set**, so after the
  student confirmed the offer no query re-fired — the type mismatch was invisible.
- The three pathway-hearing branches were **inconsistently gated on genuineness**: the clash arm
  (`pathway_confirm`) fired even for a **fake** offer; the undeclared + type-switch arms were
  `== 'genuine'` and so **excluded suspect**.

## Owner policy (2026-07-18)

Genuineness is **three bands** (`genuineness/bands.py`): `genuine` ≥0.70, `suspect` 0.35–0.70, **fake**
<0.35 (stored `not_offer_letter`); plus `unknown` (unscored). The single rule:

> **A pathway hearing fires iff the offer is a SCORED, non-fake offer — `genuine` OR `suspect`.**
> **Fake and `unknown` get NO hearing** (fake is flagged + submission-blocked; unknown waits until scored).

## The design — ONE band-aware, mutually-exclusive detector

`verdict_engine._verdict_pathway`: the identity/presence checks stay outside the gate; the three hearing
branches collapse into one block, `if offer_hearing_ok(offer):` then `if/elif` (at most one, and the
type switch suppresses the generic confirm):

1. **Case 2 — TYPE switch** (declared family ≠ offer family, e.g. STPM→PISMP/Matric, #43): raise
   `pathway_type_switch` **regardless of `pathway_confirmed_at`**. Carries `declared_pathway`/
   `offer_pathway` (+ `aliran_hint` for PISMP).
2. **Case 3 — within-family clash** (same family, institution/stream differs — the #117 case): the
   generic `pathway_confirm` (kept `not confirmed` — a minor drift isn't re-asked post-confirm).
3. **Case 1 — nothing declared** (#127): `offer_is_resolvable` → one-tap `pathway_confirm`; ambiguous
   (a PISMP offer with no aliran) → `pathway_undeclared` → the profile picker (+ `aliran_hint`).

## Reused / new helpers (backend)

- **NEW `pathway_engine.offer_band(doc)` / `offer_hearing_ok(doc)`** — read
  `vision_fields['authenticity']['status']` through the existing three-way `bands.canonical_status`
  → `genuine`/`suspect`/`not_offer_letter`/`''`; `offer_hearing_ok = band in ('genuine','suspect')`.
  `offer_official_status` (binary) is **unchanged** — the submission gate / promotion /
  `resolution.doc_match_verdict` keep asking the different "official enough?" question.
- **`offer_pathway.pathway_family`** — now normalizes ALL vocabularies (detect codes, the 8
  apply-form `chosen_pathway` codes, AND legacy labels: `Matriculation≡matric`, `university≡degree`,
  `poly≡diploma`) to one funding family, and returns `''` for an unrecognised value so it can never
  spuriously differ from a known family (the switch requires BOTH sides to resolve to a known family).
- **`offer_pathway.infer_pismp_aliran`** — SPM Bahasa Tamil→`sjkt`, Bahasa Cina→`sjkc`, else `sk`
  (LOWERCASE codes matching the FE `PismpAliran` / storage). A picker default the student confirms.
- **`services.confirm_pathway`** — the shared "yes" handler for both `pathway_confirm` and
  `pathway_type_switch`: adopts the offer's family into `chosen_pathway` and clears the now-stale
  `pre_u_track`/`pre_u_institution`; same-family confirms are a no-op.
- `check2_queries._PATHWAY_QUERY_KINDS` includes `pathway_type_switch`; `views.py` routes its "yes" to
  `confirm_pathway` and skips the relevance judge for it.

## Frontend (`halatuju-web`)

- `components/ActionCentre.tsx`: a non-PISMP switch → one-tap "Yes, I've switched" (→ resolve
  'confirmed' → `confirm_pathway`); a **PISMP** switch **and** `pathway_undeclared` → the profile
  Aliran/Bidang picker via the pure **`actionCentre.profilePickerHref`** (`/profile?aliran=<hint>`).
- `components/PathwayPicker.tsx`: **pre-selects the aliran from the `?aliran=` URL param** (reads
  `window.location.search`, no extra Suspense boundary) when it's an eligible school type.
- `localiseParams` renders the `declared_pathway`/`offer_pathway` codes as labels via
  `scholarship.actionCentre.pathwayName.*`; i18n en/ms/ta for the card + button copy (Tamil first-draft).

## Verification (done)

- **Backend: 2725 scholarship pytest green.** New: `TestOfferBand`; suspect-undeclared-asks;
  unknown-no-hearing; not-confirmed-type-switch-suppresses-generic. Several verdict fixtures aligned to
  same-family / scored where they test a within-family clash (their `chosen_pathway='Matriculation'`
  label vs a `Tingkatan Enam` offer had been an accidental cross-family case).
- **Frontend: 591 jest green** (incl. `profilePickerHref` + the KNOWN_CODES↔copy parity + pathway-label
  localisation); `ActionCentre`/`actionCentre`/`PathwayPicker` tsc-clean.
- **4-case × 4-band matrix demo** (temp, deleted) confirmed the full grid: **fake + unknown silent;
  genuine + suspect ask;** undeclared-preU/within-clash → `pathway_confirm`, undeclared-PISMP →
  `pathway_undeclared`, type-switch → `pathway_type_switch`; **both PISMP paths → picker with
  `aliran=sjkt` pre-inferred.**

## Carry / deferred
- **Live Supabase data sanity (read-only) — deferred (MCP was down):** re-check #43 raises
  `pathway_type_switch`, and scan for the cohort where `chosen_pathway` family ≠ the confirmed
  `chosen_programme` family — this "scored + family-aware" logic now catches a real set of
  declared-A/offer-B students who will start seeing the switch hearing. Worth eyeballing before deploy.
- Tamil review of the first-draft `pathway_type_switch` / `pathwayName.*` strings.
