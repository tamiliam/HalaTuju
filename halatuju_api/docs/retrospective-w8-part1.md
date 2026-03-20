# Retrospective — W8 Part 1: Institution Modifiers Sprint

**Date:** 2026-03-20

## What Was Built

- Management command `derive_institution_modifiers` that populates `urban` (boolean) and `cultural_safety_net` ("high"/"low") on all institutions from state and address data.
- Applied to 838 production institutions: 171 urban, 438 high safety net.
- Activates 3 previously inert quiz signal pathways in the ranking engine.

## What Went Well

- Pure data population — no ranking engine code changes needed. The modifier consumption logic existed since v1.3 but had no data.
- Queried production Supabase to verify institution types and addresses before writing the lookup tables. Caught that most IPTA addresses are empty — the city-in-name fallback handled it.
- Added Penang as a fully urban state after noticing USM's address ("Minden") wouldn't match any city keyword.

## What Went Wrong

Nothing significant. Clean sprint.

## Design Decisions

- **Penang as fully urban state**: Rather than listing Penang cities individually, classified the entire state as urban. Penang is Malaysia's most densely populated state — even "rural" Penang is urban by national standards.
- **State-based safety net, not institution-level**: Used state as the granularity for cultural safety net rather than trying to measure per-institution Indian population. Simpler, defensible, and matches how community networks actually operate (state-level Tamil organisations, temples, schools).
- **SQL direct-apply to production**: Applied modifiers via SQL rather than running the Django command against production. The command is for local/testing use; production data was populated in one batch.

## Numbers

- Tests: 966 → 997 (+31)
- Files created: 2 (command + tests)
- Production institutions updated: 838/838 (100%)
- Urban: 171 (20.4%)
- High safety net: 438 (52.3%)
