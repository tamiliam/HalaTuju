# Retrospective — Offer letter auto-settles an undecided pathway

**Shipped 2026-06-12** (commit `d849510`, branch `feature/offer-pathway-autofill` merged + deleted).
No migration. Both Cloud Builds SUCCESS; web 200 / api 200.

## Problem
The officer cockpit showed a student as *"CHOSEN PROGRAMME — / still-deciding: exploring"* even when
they'd uploaded a **verified offer letter** confirming a place (real case: #25 SWETHA — a Form-6 offer
at SMK Tun Hussein Onn, identity-matched). The Pathway *verdict* was already green; only the stored
`chosen_*` fields were stale, because they were only ever written when a student answered the
`pathway_confirm` query — which never fires when there was nothing to confirm (the undecided→decided
case, as opposed to a genuine clash).

## What shipped
`apps/scholarship/offer_pathway.py` (pure `detect_pathway_type` / `parse_stpm_stream` / `is_pre_u` +
a **conservative** catalogue resolver) and `services.autofill_pathway_from_offer`, run on offer-letter
upload + admin re-run (event-driven, never in the dashboard GET — TD-079). It mirrors the apply form's
**own two storage shapes**:

- **Pre-U (STPM/Matrik):** `chosen_pathway` + `pre_u_institution` (school, free text) + `pre_u_track`
  (stream, only if the offer prints it) — no catalogue id, exactly as the apply form stores pre-U.
- **Tertiary (Diploma/Asasi/Degree):** `chosen_programme` with a canonical `course_id` **only on a
  confident, unique** subset-token match against the course catalogue, else plain labels — never a
  fabricated id. (`_name_aligns` = subset-either-direction, so offer-letter code prefixes like
  "DAC - DIPLOMA PERAKAUNAN" still align with catalogue "Diploma Perakaunan".)

It also clears `pathway_certainty → 'sure'` (the cockpit hides the "still-deciding" lines when sure),
and **deliberately does not stamp `pathway_confirmed_at`** — that field short-circuits the verdict
before the clash check, so stamping would mask a later genuinely-different offer.

**Guards:** skips wrong-person (name/IC clash), unreadable offers, genuine clashes (a *specific*
declared programme vs a different offer → still the `pathway_confirm` query's job), and already-locked
precise picks. Idempotent.

`backfill_offer_pathways` (dry-run default) applied the same logic to existing offers.

## Outcome (prod backfill)
**19 of 38** offer-holders settled — all the *undecided* ones. The genuine clash (#16 *Asasi Perubatan*
vs *ASASIpintar*) and the already-decided tertiary students (who locked a `course_id`) were correctly
left untouched (`source` stays null on those; `offer_letter_auto` only on the 19). #25 → STPM · SMK Tun
Hussein Onn; #57 picked up its `sains_sosial` stream; #62 resolved to a real catalogue `course_id`
(POLY-DIP-016) — proving the conservative resolver works on live data.

## Decisions
- **Clash → confirm, undecided → silent** (owner's call). The mismatch query stays for a real change of
  a stated decision; the offer-settles-a-blank case never asks.
- **Resolve to `course_id` else labels** (owner's call) for tertiary — accuracy over coverage; a wrong
  id is worse than no id.

## Gates
1135 scholarship pytest (+17 `test_offer_pathway.py`), `next build` clean, no migration.

## Notes / follow-ups
- The cockpit still keeps `pathway_confirm` as an **officer** review item (it's `source='system'`,
  hidden from the student Action Centre). Surfacing the one-tap confirm to students remains an open,
  separate decision (see the session discussion).
- #12 settled with an institution-only offer (programme didn't OCR) → `pathway_certainty='sure'` with an
  empty programme. Thin but harmless (a real UTM place; the programme is an OCR gap, not indecision).
