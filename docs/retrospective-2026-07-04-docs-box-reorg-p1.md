# Retrospective — Officer Documents box reorganisation, Phase 1 (2026-07-04)

Plan: `.claude/plans/draw-up-the-roadmap-majestic-raccoon.md` (officer Documents box reorg + version
history, 3 phases). This is **Phase 1 — the frontend re-grouping only** (no backend, no migration,
independently shippable).

## What Was Built

The cockpit "Documents" box now groups into IDENTITY / ACADEMIC / PATHWAY / INCOME / ADDITIONAL /
OTHER, with INCOME split into STR ROUTE (route-gated) / SALARY ROUTE (always) / UTILITY (always).
The core new logic is `incomeSubSections(app, incomeDocs)` in `lib/officerCockpit.ts`, which reuses
the existing `incomeDocLayout` slot builders (`relationshipDocFor`, `workingMembers`, the
placeholder-slot model) and partitions income docs so that — per the owner's worked example — an STR
mother's STR/IC/BC sit under STR while her and the father's salary slips, the father's IC, and both
EPFs sit under SALARY. `docTypeToFact` was remapped (semester_result→academic; intent/photo/leaving-
cert→additional; income_support/bank/reference→other). i18n gained the sub-section heads +
`bank_statement` label.

## What Went Well

- Reuse over rebuild: `incomeSubSections` delegates to the same slot helpers the gate/wizard use, so
  the box can't disagree with what the student is asked for. `incomeDocLayout` was kept intact (its
  jest still passes) rather than mutated.
- The exact-tag-over-blank preference for the STR earner IC pre-empts the #63 mis-attribution at the
  display layer (a blank-tagged father IC no longer masquerades as the earner's).

## What Went Wrong

- **Removing the flat Required/Optional labels orphaned two i18n keys** (`docsDrawer.required`/
  `.optional`). Symptom: the `admin-scholarship-i18n` orphan guard failed. Root cause: the new
  sub-section render uses different heading keys, leaving the old labels unreferenced. Fix: deleted the
  two keys from en/ms/ta (after grepping for any remaining source ref). The guard test did exactly its
  job — this is the intended safety net, not a regression.
- **Parallel jest reported 3 phantom suite failures on the 8 GB box** (0 test failures); a single-worker
  run (`--runInBand`) was clean at 432. Consistent with the known 8 GB memory-contention pattern —
  trust the single-worker result for the go/no-go.

## Design Decisions

- SALARY sub-section always visible, STR only on an STR route with an STR doc (owner decision) — a
  household is not strictly one route. This is display-only in P1; the verdict still follows the single
  `income_route` until Phase 3.
- Kept `incomeDocLayout` rather than deleting it — lower blast radius, and its tests stay as a
  regression anchor while `incomeSubSections` is the live path.

## Numbers

- 432 jest (+6: grouping remap + `incomeSubSections` visibility/partition + the #63 exact-tag case).
  tsc clean for the touched files. No backend, no migration. i18n en/ms/ta parity held (2 keys removed,
  5 added per locale).

## Next

Phase 2 (document version history — retain replaced docs, migration 0093, the read-site audit) then
Phase 3 (enforce shared-IC + STR-overrides-route verdict, re-banding-gated).
