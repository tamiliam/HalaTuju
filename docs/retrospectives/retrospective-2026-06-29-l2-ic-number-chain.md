# Retrospective — L2-1: the IC-number chain (cross-document earner verification)

**Date:** 2026-06-29
**Commits:** `c1fa3066` (item B — extraction robustness), `63a56a61` (item A + chips C/D/E)
**Deploy:** pushed to `main` `f8094760..63a56a61`; both Cloud Builds SUCCESS; live as
`halatuju-api-00548` + `halatuju-web-00502`. No migration.

## What Was Built

The first real **Layer-2** (cross-document) capability for B40 document recognition. Layer 1 judges
each document on its own (genuineness + field extraction); Layer 2 links documents to each other.

**The insight (owner-driven):** the **IC NUMBER is the strong cross-document join key.** A romanised
Malaysian name transliterates a dozen ways, but an IC number does not. The **Birth Certificate carries
the parents' IC numbers**, and every income proof (STR recipient / salary slip / EPF) carries the
recipient's NRIC. So an earner can be verified by chaining **BC-child = student → BC-parent-IC =
proof-IC**, *independent of the physical parent_ic card uploaded in that slot.*

- **`income_engine.chain_verified_earner(application, member)`** — the centrepiece. True when a
  Layer-1-genuine BC (child = student) carries a parent's IC number matching the income proof's
  number — exact, or **one-digit OCR drift when the parent NAME corroborates** (the JPN guilloche
  makes single-digit misreads common). Mother/father only (a normal father chains via the patronymic,
  which needs no number). It only ever turns a would-be **red into a verified green**; it never
  asserts a mismatch, and a positively-suspect BC cannot anchor it (`_bc_anchorable`).
- **Wired in lockstep** through every status producer — `student_income_ic_check`,
  `student_income_proof_check`, `student_str_check`, `student_bc_check` — plus
  `resolution.doc_match_verdict` and both `verdict_engine` income paths. The cockpit chips, the
  Action-Centre per-doc verdict, and the submission gate therefore can never disagree.
- **The one hard block survives:** a proof whose name AND number both contradict, with no chain
  corroboration, still blocks (the wrong-person-no-corroboration case).
- **Cockpit (C/D/E):** EPF/salary chips now show **IC No** beside Name (hidden on a salary slip that
  carries none — the strong earner key, mirroring the STR chip); the parent-IC chip shows a soft amber
  **"Wrong card"** caveat when the chain verified the earner but the uploaded card is a different
  family member's (the clear, soft wrong-document signal — never a block).

## What Went Well

- **The eval harness caught a real logic bug before deploy.** Building app 9 through the cached-snapshot
  eval showed the BC still red after the first cut — the fix was wrong in a way unit tests hadn't
  exercised (see below). The harness paid for itself.
- **#9 fully green, #5 stays red** — both verified on real cached data, exactly as the owner specified.
  A bonus #30 (STR number one digit off) also cleared via the near-match path.
- Net effect on the eval: false-positives 10 → 8, with every remaining FP/FN explained (stale labels,
  Item-B extraction frozen in old snapshots, or other-layer pre-existing gaps) — no new regression.

## What Went Wrong

1. **First re-anchor cut left the BC mother-row red on a wrong card.**
   - *Symptom:* app 9's `parent_ic`/`str`/`epf` went green but `birth_certificate` stayed `mismatch`.
   - *Root cause:* I re-anchored `student_bc_check` against the *income proof* identity with an
     `or` fallback (`p_name or mic_name`). When the STR recipient *name* hadn't been read (`''`), the
     `or` fell back to the **wrong card's** name (the father's) → a name mismatch. The number had
     already settled identity, but I re-ran an exact name compare against the wrong reference.
   - *Fix / prevention:* when the chain confirms the earner, **set the identity status to `match`
     directly — never re-compare against a card that may be the wrong person's.** Applied uniformly
     across all three re-anchor sites. Lesson logged: *a chain that verifies by NUMBER must not be
     re-litigated by an exact NAME/number compare that the same OCR drift fails.*

2. **The local eval DB was missing recent migrations.**
   - *Symptom:* `eval_doc_recognition --auto-ok` returned `OperationalError: no column closure_reason`
     for every app (335 ERRORs masquerading as "0 genuine").
   - *Root cause:* the eval builds fixtures in the local sqlite via `rolled_back()`; that DB hadn't been
     migrated after the post-award S2–S6 column additions.
   - *Fix / prevention:* `python manage.py migrate` before an eval run. (Worth a one-line note in the
     eval README — the harness should fail loud on a migration gap, not silently report 0 genuine.)

## Design Decisions

- **Chain gates on Layer-1, but leans permissive on "indeterminate".** `_bc_anchorable` blocks only a
  *positively*-suspect BC (`suspect` / `not_birth_certificate`); a BC with no genuineness signal yet is
  treated as indeterminate and may still anchor. Rationale: the chain only ever DEMOTES a red to a
  verified green, so erring toward the strong number corroboration is safe, and the reviewer remains
  the authority. A forged BC is still caught independently by its own genuineness cap.
- **Force `match` on chain, don't re-compare.** (See What Went Wrong #1.) The number is authoritative;
  same IC number ⇒ same person, so a name discrepancy under a matching number is an OCR/transliteration
  artefact, not a different person.
- **Kept the four checks + verdict in lockstep rather than deduping (TD-110 stays open).** One shared
  `chain_verified_earner` called from each site, not a refactor of the duplicated red/unreadable logic —
  smallest blast radius on a live pipeline.

## Numbers

- +10 backend chain tests (`TestIcNumberChain`), +4 cockpit chip tests. Full suite **1691 pytest green**.
- Eval (cached snapshots, free replay): genuine 326, false-positives **8** (was 10), all remaining
  explained. #9 → all `ok`; #5 → correctly `mismatch`.
- 11 files; +340 / −7 lines. No migration. i18n added EN/MS/TA (`docsDrawer.fact.wrong_card`).
