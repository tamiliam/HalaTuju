# Retrospective — request #31: a "Born in" state rule on an intake year (2026-10-08)

Sprint (analysis #78, 8.0 h quoted and accepted). Pushed `eac97911`. Migration
`0171_cohort_allowed_birth_states` (one `jsonb NOT NULL DEFAULT '[]'` column) applied migrate-first
by the lead through Supabase MCP on the owner's "go"; read back: jsonb, not nullable, default kept,
all 3 intake years `[]`, ledger 0169-0171 contiguous (171 rows).

## What was built
`ScholarshipCohort.allowed_birth_states` — the states a student must have been BORN in, read from
the IC's place-of-birth code (digits 7-8, full JPN list, `birth_state.py`). Empty = off. Born
abroad, code 82 or an unreadable IC fail closed. A failing student is `ineligible` (generic decline
email). Tick boxes on the Rules tab and the create-year form; a cockpit line "Born in: Sabah (IC
code 12)", red when the CURRENT IC fails the CURRENT rule.

Rulings (owner + BrightPath's Christi, 2026-10-08): the test is "born in", not "Sabahan"; MyKad is
the primary proof, a birth certificate only where in doubt (an existing cockpit request); abroad
fails; the two applications already in the Sabah intake are test records.

## What went wrong
1. **The analysis said "the MyKad check catches a false IC number". It did not, on one route.** The
   adversarial review showed a student could pass the gate with a typed Sabah code, be shortlisted,
   then change the IC to the real one; the real MyKad then MATCHES and auto-locks, and nothing
   re-checked the birth state. Why: the gate runs at submit only, and the IC stays editable until it
   is verified. Fix: the QC accept floor now carries a `birth_state` fact against the current IC
   (override only with a recorded reason), and the cockpit line turns red. A super's lock release on
   a `recommended` case still reaches funding without a re-check — TD-371.
2. **An old bug would have stopped the rule's own target students.** The profile IC validator
   accepted only codes 01-16 and 21-24, so a real IC with Sabah's 47/48/49 (or any 25-59) was
   refused at the profile step. Production had 677 ICs, all 01-16 — consistent with the others
   being turned away. Fixed (01-16, 21-59, 71, 72, 82) with drift tests holding the api list, the
   web's `ic-utils.ts` copy and the birth-state table together.
3. **`shortlist_reason` reached the student before the reveal.** It now holds the birth state and
   IC code; it was served on the student's own application payload and the submit response. No
   student screen read it, so it was removed from the student serializer.

## What went right
- Two review rounds by a reviewer who did not build it: round 1 SHIP AFTER FIXES (the three above),
  round 2 SHIP. The builder's tests caught four deliberate mutations (gate off, code 47 remapped,
  slice shifted, unknown keys trimmed instead of refused).
- No new email, two new UI strings only (bundle: `/scholarship/application` 273.797 of 274).

## Numbers
pytest 8121 -> 8177 passed / 3 skipped (`-n auto`) · jest 4149 -> 4177 / 255 suites · i18n 5449
keys · bundle ok, median 228.773 of 229. Debt raised: TD-371 to TD-375.
