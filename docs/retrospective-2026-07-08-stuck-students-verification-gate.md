# Retrospective — B40 stuck-students investigation + verification-gate alignment (2026-07-08/09)

A live-review round driven by real shortlisted applicants who could not submit. It started as
individual cockpit tweaks and became a systematic "why is each stuck student stuck?" investigation
that exposed several places where the submission gate was **stricter than, or contradicted, the
verification verdict** — silently violating locked principles.

## What Was Built

**Cockpit / reviewer surface**
- QC can override the red-fact floor with a recorded reason (was super-only).
- Recommendation card attributes reviewer + QC separately ("Interviewed and recommended by … ,
  accepted by …"); new `recommended_by` (migration `0095`), stamped at QC-accept; the "accepted by"
  clause shows only a real QC, never the reviewer (fixed a legacy fallback misattributing to Rohini).
- AI final profile foregrounds extenuating circumstances for above-B40 recommended cases.
- Apply wizard "Save & continue" advances to the next step when complete.

**Verification-gate systemic fixes (the heart of the round)**
- **One clean cluster is enough** (salary route): once one earner is fully + coherently documented,
  other members' missing docs / mismatches become soft Check-2 items, not submission blockers (#19).
- **STR precedence in the gate** (STR route): a valid dispositive STR makes income-doc person-
  mismatches soft — the route-agnostic twin of one-clean-cluster (#28).
- **Grade mismatch is soft**, not a hard block: the slip is authoritative and the officer sees the
  exact diff; identity (name) reds still hard-block. Gopal now names the subject ("KIMIA: you entered
  G, but your slip shows E") and deep-links to `/onboarding/grades` (#48).
- **Offer gate follows the PATHWAY verdict band** ("blue and above"), not the raw
  `offer_official_status` — so a reporting-bonus-lifted Certain offer is accepted (#56). Unknown/
  unscored offers still never block.
- **Patronymic derived from the verified IC** when the typed name lacks the A/P connector — a typing
  habit no longer overrides a verified document and silently drops a dispositive-STR household to
  Unsure (#88).

**Diagnostics + coach honesty**
- `consent_blockers` exposed on the admin API + `stuck_report` management command (read-only "why
  can't this student submit?"), used throughout the round.
- Gopal no longer claims "your application isn't blocked" when the gate blocks.
- OCR name-guard: a header fragment fused into a name ("RAJAANMALAYS") reads as unreadable, not a
  confident wrong name.

**Data corrections (owner-directed):** #16 → shortlisted (test); #88 STR earner → father; the 4
genuine QC-accepts attributed to Suresh.

## What Went Well
- The `stuck_report` tool turned "why is X stuck?" from eyeballing into an authoritative per-student
  answer, and immediately caught two cases my data-reconstruction had wrong (#48 academic, not ready;
  #5 extra mismatches).
- Every gate change was validated on live prod data before shipping; cohort-wide re-banding audits
  (e.g. patronymic fix touches exactly 2 apps) kept blast radius known.
- Six near-miss students unblocked (#19, #28, #48, #56, #88, #126) by fixing systems, not tagging cases.

## What Went Wrong

1. **"Verified live" masked that the deploy never happened.** For #56 and #88 I ran my *local* code
   against *prod data* and reported them "READY live" — but the Cloud Build webhook did not fire for two
   pushes (`a5cd592`, `9fe52e72`), so the actual service was never updated. The build-watch for
   `a5cd592` returned empty and I moved on instead of confirming a build had triggered.
   - **Root cause:** conflating "my code gives the right answer on prod data" with "the deployed
     service runs my code" — and not treating "no build appeared" as a failure.
   - **Fix:** after every push, confirm a build actually **triggered AND succeeded** before claiming
     "live". If no build appears within ~60s, manually trigger (`gcloud builds triggers run`). Added to
     lessons.md.

2. **Guessed #28's mechanism twice before tracing the code.** I proposed "mislabelled earner", was
   corrected, proposed a second wrong story, then finally ran the engine — which showed the mother's IC
   cross-checked against the father's STR.
   - **Root cause:** reasoning from summary field-dumps for a *verdict* question instead of running the
     actual engine path.
   - **Fix:** for any "why is the verdict/gate X" question, run `stuck_report` or a shell diagnostic
     FIRST; never narrate a mechanism from raw fields. Added to lessons.md.

3. **Locked principles were enforced in the verdict path but not the parallel submission gate.** STR
   precedence and "trust the verdict card" lived in `verdict_engine`, but the consent gate used raw,
   divergent checks (`offer_official_status`; a salary-only suppression); and the patronymic used the
   weaker typed name while the verified IC sat unused. Each was a silent violation of a stated
   principle — the same class as the earlier "tally vs paint keep-in-sync" drift.
   - **Root cause:** a decision made in one code path is not automatically mirrored in every path that
     makes the same decision.
   - **Fix:** when a principle is locked, grep every code path that makes that decision and align them;
     prefer routing the gate through the *same* helper the verdict uses (e.g. `_fact_band`,
     `income_established`, `student_name_for_link`) rather than a parallel check.

## Design Decisions
See `docs/decisions.md`: one-clean-cluster / STR-precedence in the submission gate; offer gate follows
the pathway verdict band; patronymic-from-verified-IC; grade mismatch soft-not-blocking.

## Numbers
- 2224 scholarship pytest (+ jest unchanged); all live-verified on prod data.
- Migrations: `0095_recommended_by` (additive, migrate-first via MCP).
- 6 shortlisted students unblocked by systemic fixes; cohort re-banding audits confirmed minimal blast
  radius per change.
