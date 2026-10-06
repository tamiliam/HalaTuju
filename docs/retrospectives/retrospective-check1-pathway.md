# Retrospective — Check-1 Pathway (offer letter) + final-pathway confirmation + document reorg

**Date:** 2026-06-03 · **Branches:** `check1/academic`→ then `pathway/final-confirm` (`a0d997f`) + `ui/docs-reorg` (`ece0cec`) → `main` · **Deployed:** yes

## What Was Built
Three increments, all live:

1. **Pathway facts (differentiated).** The offer letter got the IC/slip clinical treatment. The Gemini `offer_letter` extraction was expanded (`+candidate_nric, issuer, offer_date, candidate_address`) with a prompt covering every Malaysian post-SPM offer type (university degree/diploma, polytechnic, matriculation, Form Six). New pure `pathway_engine.student_offer_check` is the single source for `OfferLetterChecklist` + Gopal: **Name + IC** as identity checks (IC is the strong one — names can coincide, the NRIC can't), and **Programme · Institution · Issued-by · Date · Address** as soft data points (a student may legitimately change plans, so those aren't hard-checked). Live-confirmed across all five real sample types.

2. **AI-raised final-pathway confirmation (no human officer).** When an offer's Name + IC match, the system auto-raises a `pathway_confirm` Action-Centre query — *"is this your final chosen pathway?"* — and the student answers **Yes** in place. That writes the offer's programme + institution to `chosen_programme` and stamps `pathway_confirmed_at` (migration `0038`, additive), flipping the Pathway verdict to **verified**. Deliberately **not a blocker** — a better offer just gets uploaded instead.

3. **Documents organised by the four facts.** Reordered Identity · Academic · Pathway · Income everywhere (tiles, Record panel, AI-suggestion, Documents drawer); moved the parent/guardian IC from Identity to **Income** in the officer grouping (the income docs are issued in a parent's name); regrouped the student Documents tab from Required/Optional into the five fact sections with status pills. Presentational only — no completeness change.

## Numbers
557 scholarship pytest · 231 jest · i18n 1843 (final) · 3 deploys, 1 migration (`0038`, additive, migrate-first).

## What Went Well
- The IC carried by every offer letter turned out to be a **stronger identity check than the name**, and Gemini read it cleanly across all five wildly-different formats once the schema asked for it — no python fallback needed.
- The confirmation rode the **existing ResolutionItem/Action-Centre rails** (system-raised, post-submission gated) instead of a new mechanism — only one genuinely new piece (the in-place affirmative button + the `confirm_pathway` write).
- The reorg produced a real invariant: **student sections == officer groups == verdict order**, all keyed off the same fact set.

## What Went Wrong
- **A schema change left already-extracted docs showing "Couldn't read".** *Symptom:* an offer letter uploaded *before* the Pathway deploy showed IC = "Couldn't read", because its stored extraction predated the new `candidate_nric` field. *Root cause:* doc-assist fields are extracted+stored at upload time; adding a field doesn't retro-extract old docs. *Fix:* none needed in code — a **Re-run** (or re-upload) re-extracts with the new schema; confirmed working. *System change:* lesson recorded — *when you add an extracted field, existing docs won't have it until re-run; surface "Couldn't read" honestly rather than "Not checked", and tell the user a re-run is the fix.*
- **A reordering touched five places, two of them hardcoded test assertions.** Caught by running the gates (`test_order_is_fixed`, `test_facts_order_fixed`). No process change — this is exactly what the gates are for; noting that "fixed order" is asserted in tests, so an intentional reorder must update them.

## Design Decisions
See `docs/decisions.md` → "Offer programme is surfaced, not gated", "Final pathway is confirmed by the student (AI-raised, no officer)", "Documents organised by the four verification facts".

## Carried Forward
- Richer pathway-aware Gopal (constrained by the help-engine data firewall — low priority).
- The **Income fact** Check-1 — the hard one: income amount + earner identity (parent IC) + **relationship establishment** (father auto-derivable via the student-IC patronymic; mother needs a **Birth Certificate** — a new doc type; guardian needs the guardianship letter) + utility bills as a soft hardship signal + the "income proof if available" policy question.
