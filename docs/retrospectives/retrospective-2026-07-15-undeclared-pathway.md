# Retrospective — Confirm-or-complete an undeclared pathway (2026-07-15)

Owner live-review off #127 (VIJHAY): a genuine PISMP offer, but the student declared no pathway at
all, read silently **Certain** with the offer's Pathway chip grey and no Check-2 query. The owner
wanted: don't be green until the student confirms/completes it — ask them, filling the course tree
when we can and sending them to the profile to pick when we can't (PISMP's SK/SJKT/SJKC streams
aren't on the offer). Probable until matched.

## What Was Built

- **`verdict_engine._verdict_pathway`** — a new branch for a **genuine official** offer + a **true
  non-declaration** (`_no_declared_pathway`): band → Probable, and raise a student query.
  **Resolvable** offer (pre-U stream / unique catalogue course, `offer_pathway.offer_is_resolvable`)
  → the one-tap `pathway_confirm`; **ambiguous** → the (previously dormant) `pathway_undeclared`,
  now a live student query linking to the profile page.
- `check2_queries._sync_pathway_confirm` generalised to mirror both pathway student queries;
  `pathway_undeclared` removed from the system `CODE_TO_TICKET` so it's a student query, not a hidden
  system item.
- **Action Centre**: `pathway_undeclared` → an "Update on your profile" link (auto-resolves once a
  real course lands); `pathway_confirm` copy made neutral. i18n en/ms/ta.

## What Went Well

- **`pathway_undeclared` already existed** — registered, in `KNOWN_CODES`, with copy — just dormant
  (never raised). Reviving it was far less work than inventing a new query type.
- **Investigation caught two scope errors before deploy.** (1) The first trigger (`chk['pathway'] ==
  'unknown'`) was too broad — it broke 4 tests because it also fired on students who declared a
  pathway *type*. Narrowing to `_no_declared_pathway` (a TRUE non-declaration) fixed it and matched
  the owner's #127 case. (2) Quantifying the live set revealed 3 of the 5 candidates had *fake/
  suspect* offers — asking a student to "confirm" a fake letter is wrong, so a `offer_official_status
  == 'genuine'` gate scoped the re-band to the 2 real cases (#127, #133).

## What Went Wrong

- **I under-quoted the blast radius twice.** I first told the owner "~8 apps," then the broad trigger
  would have hit far more (breaking 4 tests), then the accurate genuine-only set is **2**. **Root
  cause:** I estimated the re-band from a rough SQL proxy instead of the actual verdict predicate +
  the genuineness gate. **Fix (system):** for any verdict-band change, quantify against the REAL
  predicate (run/trace the exact condition, incl. genuineness) before quoting a number, and re-check
  after each scope refinement. Captured as a lesson.

## Design Decisions

- **Fire only on a genuine official offer + a TRUE non-declaration.** A type/specific declaration is
  left as the offer settling it (verified); a fake/suspect offer is left to the genuineness flags —
  never ask "is this where you're going?" about a letter that isn't a real offer. See decisions.md.
- **Revive `pathway_undeclared` as a student query, not a system item.** Removed from `CODE_TO_TICKET`
  (which would hide it as `source='system'`) and routed through Check-2 (`source='check2'`) like
  `pathway_confirm`, so the flag governs it + it rides the query email.

## Numbers

- +4 tests (offer_is_resolvable, undeclared ambiguous/resolvable, fake-offer-not-asked); 2567
  scholarship pytest; jest 552; i18n parity; NO migration.
- Re-band = 2 live apps (#127, #133). 1 deploy (api+web, `c01ccc04`).
