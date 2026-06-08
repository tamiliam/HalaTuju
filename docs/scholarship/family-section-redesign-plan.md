# "About your family" section redesign — build plan

**Status:** Design approved (owner, 2026-06-08). Stitch mockup approved — "About Your Family - Form Card",
node-id `dd948b9b4fe14e14920f94984683fc0c` (project `10844973747787673276`). **Decision: PHASE IT** — build the
structured family roster + sibling merge now; leave the income "who works" wizard as-is but design the roster so it
can feed income earners later (Phase 2).

## Problem (root cause of the downstream issues)
Family data is captured in **four overlapping fields across two tabs** that can contradict each other:
`first_in_family` (toggle, Story) · `siblings_studying_count` (legacy combined, Story) · `siblings_in_school` +
`siblings_in_tertiary` (steppers, **Income** tab) · `parents_occupation` (free text, Story). Consequences in code:
anomaly_engine `first_in_family_with_siblings_studying` (a contradiction that only exists because they're separate
inputs), check2_queries `sibling_level_unknown` email, profile_engine has to gate/hedge unverifiable claims.

## Target (one structured source of truth; derive the rest)
Single "About your family" card in the **Story tab**:
1. **Parents/guardians** — Father (Name as in IC + Profession ▾ + if-Other text), Mother (same). Plus an
   elective-subjects-style **pool**: stacked member rows `[Relationship ▾ Brother/Sister/Guardian][Profession ▾][×]`
   with a dashed **"+ Add a family member"** button below the rows.
2. **Brothers & sisters** — two steppers: "In primary or secondary school", "In college or university (now or
   before)". A **derived** read-only green note "✓ You'd be the first in your family to go to university" when the
   uni count is 0. **No toggle** — first-in-family is computed, can't contradict.
3. **Anything else…** — `family_context` free text (kept) + "Need ideas?".

## Data model (migration `0048`, additive — no data loss)
New on `ScholarshipApplication`:
- `father_name` CharField(200, blank) · `father_occupation` CharField(40, blank) · `father_occupation_other` CharField(120, blank)
- `mother_name` CharField(200, blank) · `mother_occupation` CharField(40, blank) · `mother_occupation_other` CharField(120, blank)
- `other_family_members` JSONField(default=list) — `[{role, occupation, occupation_other}]`, role ∈ brother/sister/guardian

Kept / repurposed:
- `siblings_in_school`, `siblings_in_tertiary` (already exist, 0040) — UI **moves to Story**; tertiary relabelled "now or before".
- `first_in_family` (KEEP column) — **derived on save**: `(siblings_in_tertiary or 0) == 0`. Downstream readers unchanged.
- `parents_occupation` (KEEP column) — **derived on save** as a summary string from the roster (e.g. "Father: Own
  business; Mother: Homemaker; Brother: Odd jobs"), so profile_engine keeps working until it's updated to read structured.
- `siblings_studying_count` — retired from the UI; column kept for back-compat (stop writing it).

**PROFESSION_CHOICES** (code → label): `gov` Government / public sector · `private` Private company employee ·
`self_employed` Own business / self-employed · `odd_jobs` Odd jobs / daily wage / gig · `farmer` Farmer / fisherman /
smallholder · `homemaker` Homemaker · `retired` Retired / pensioner · `unemployed` Unemployed · `deceased` Passed away ·
`no_contact` Not in contact · `other` Other (specify). Single source in `lib/familyRoster.ts` + a Python mirror.

## Backend changes
1. `models.py` — 7 new fields + `PROFESSION_CHOICES`; pure helpers `derived_first_in_family(app)` and
   `parents_occupation_summary(app)`.
2. Migration `0048` (additive ALTER, migrate-first via MCP).
3. `serializers.py` — `ApplicationDetailsUpdateSerializer`: accept new fields (validate occupation ∈ choices;
   `other_family_members` shape/length cap, ≤6). `ApplicationReadSerializer`: expose them.
4. `services.save_application_details` — write new fields, THEN derive `first_in_family` + `parents_occupation`
   (single source; the toggle/free-text columns become outputs, not inputs).
5. `anomaly_engine.py` — **retire** `_detect_first_in_family_with_siblings_studying` (impossible by construction).
6. `check2_queries.py` — **retire** `sibling_level_unknown` (the split is always captured now).
7. `profile_engine.py` — prefer structured occupations (father/mother + roster); **fall back** to raw
   `parents_occupation` when structured empty (grandfathered apps). first-in-family stays gated (now reliably derived).
8. `submission_review.py` — ledger emits structured father/mother occupation + sibling split; `first_in_family`
   verified by construction (tertiary == 0).
9. `serializers_admin.py` — expose the structured fields for the cockpit Family card.

## Frontend changes
1. `lib/familyRoster.ts` (NEW) — `PROFESSION_OPTIONS`, member roles, `derivedFirstInFamily(tertiary)`, node-tested.
2. `ScholarshipNextSteps.tsx` Story "About your family" card — rebuild per mockup (parents + pool + steppers +
   derived note + family_context).
3. `ScholarshipDocuments.tsx` income wizard — **remove** the `siblings_in_school`/`tertiary` steppers (they move to
   Story). Income wizard otherwise unchanged (phased).
4. Admin cockpit Family card — show structured occupations + roster + sibling split (replaces free-text line).
5. i18n en/ms/ta — profession options + section copy + member-pool copy + derived-note copy.

## Migration of existing data
Additive; the ~12 in-flight apps keep their `parents_occupation` free text (structured fields null). profile_engine
falls back to it. No backfill (free text isn't reliably parseable); students re-enter structured on next edit.
Grandfathering keyed on structured-empty.

## Tests
Backend: derive logic (first_in_family from tertiary; occupation summary) · serializer accept/validate ·
anomaly contradiction retired · check2 `sibling_level_unknown` retired · profile_engine structured + fallback ·
ledger structured. Frontend: `familyRoster` helpers (jest) + `next build`. Gate: full scholarship pytest + jest + i18n parity.

## Phase 2 (noted, NOT in scope)
The roster (father/mother + `other_family_members` professions) is the future single source for income earners:
an earning profession auto-flags an earner; the income wizard would then collect only IC/salary **proof**, dropping
its own "who works" multi-select. Larger change to a recently-shipped flow — deferred.

## Sizing
~15-18 files, one additive migration, FE + backend. One focused sprint (or split: S1 backend model+migration+engines+
serializers; S2 form rebuild + cockpit display). UI already Stitch-approved.
