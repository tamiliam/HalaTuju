# Brief — TD-161: unify pathway reconciliation (offer vs the student's declaration — present, different-type, or absent)

**Status:** BACKEND SLICE DONE + TESTED (2026-07-18); FE + PISMP picker hand-off REMAINING. NOT
deploy-ready alone (see below). Own sprint; NO migration. System-handled (no officer gate) — owner
decision 2026-07-18. Live test case: **#43** (STPM-declared, PISMP-confirmed).

## Implementation status (2026-07-18)

**DONE (backend, +2719 scholarship pytest green):**
- `offer_pathway.pathway_family` (poly≡diploma, university≡degree — only a cross-FAMILY change counts
  as a switch) + `offer_pathway.infer_pismp_aliran` (SPM BT→SJKT, BC→SJKC, else SK).
- `verdict_engine._verdict_pathway`: raises **`pathway_type_switch`** when a genuine offer is a
  different FAMILY than the declared `chosen_pathway`, **even after `pathway_confirmed_at`** (carries
  `declared_pathway`/`offer_pathway`, + `aliran_hint` for PISMP).
- `services.confirm_pathway`: on "yes" adopts the offer's type into `chosen_pathway` and drops the
  now-stale `pre_u_track`/`pre_u_institution` (same-family confirms are a no-op).
- `check2_queries._PATHWAY_QUERY_KINDS` += `pathway_type_switch` (synced to the student queue like
  `pathway_confirm`); `views` resolve routes its "yes" → `confirm_pathway`.
- Tests: verdict detection (fires when confirmed), confirm handler (adopts type + clears pre-U),
  same-type no-op, aliran inference; the public-switch (poly≡diploma) regression is guarded.

**REMAINING (before deploy — do NOT ship the backend alone):**
- **FE Action-Centre card** for `pathway_type_switch` + register it in `actionCentre` KNOWN_CODES, else
  the synced query is INVISIBLE to the student (an open task nobody can answer → #43 stuck). This is the
  blocker that makes backend-only unsafe to deploy.
- **i18n** en/ms/ta for the new card (Tamil first-draft).
- **PISMP picker hand-off** (§3/§5): after a switch to PISMP, route the student to the profile
  Aliran/Bidang picker (pre-selected via `aliran_hint`) to pin `(aliran,bidang)` → `course_id` link —
  today the TYPE reconciles but the specific course/link is not yet forced.

## Framing — one reconciliation, three inputs (owner 2026-07-18)

The real question is always the same: *"Your genuine offer says X — is X your pathway?"* Three inputs
feed it, and they should be ONE flow, not three branches:

1. **Different TYPE declared** — #43: declared STPM, offer PISMP. **NEW** (this is the TD-161 gap).
2. **Same type, different detail** — the existing within-type `pathway_confirm` (declared a specific
   course/stream, offer names another). Already live.
3. **Nothing declared** — #127: no pathway at all. Already live via `_no_declared_pathway` →
   resolvable/ambiguous fork. **Fold in as the "declaration = ∅" instance of the same model** (see §5).

All three resolve identically: on "yes" → reconcile `chosen_pathway` + `chosen_programme` (+ catalogue
link for a public programme); PISMP → the aliran-pre-inferred picker; private → red via the existing veto.

## Problem

A student declares pathway A at apply time, then uploads a **genuine, different-TYPE** offer letter
B (e.g. #43: declared STPM, offer is PISMP). Today:

- **`confirm_pathway` never writes `chosen_pathway`** — for anyone. On the student's "yes" it writes
  `chosen_programme` + `pathway_confirmed_at` (+ `reporting_date`), and for a *pre-U-declared*
  pathway it tidies `pre_u_institution` / `pre_u_track` — but the pathway **type** field is never in
  scope. (services.py `confirm_pathway`, ~1072–1157.)
- `autofill_pathway_from_offer` only **fills a blank** `chosen_pathway`; it never overwrites a
  declared one.
- The pathway verdict **suppresses the confirm once `pathway_confirmed_at` is set**
  (`verdict_engine._verdict_pathway`, the `chk['pathway']=='mismatch' and not confirmed` guard), so
  after the student confirmed offer B **no query re-fires** and the record sits contradictory:
  `chosen_pathway=stpm` / `pre_u_track=sains_sosial` next to a confirmed PISMP `chosen_programme`.

This was deliberate ("a pathway-TYPE change, NOT auto-coerced" — reclassifying STPM→PISMP changes
funding/eligibility), flagged as **TD-161** for an explicit decision. Owner's decision now: **let the
system handle it** via the existing Check-2 confirm flow, extended to the type mismatch.

## What already exists (reuse — do NOT rebuild)

- **The resolvable-vs-ambiguous fork** in `_verdict_pathway` (owner 2026-07-15): a genuine offer with
  no declared pathway routes to either a **one-tap `pathway_confirm`** (`offer_is_resolvable(prog,inst)`
  true → a pre-U stream / unique catalogue course) OR a **`pathway_undeclared`** query that sends the
  student to the **profile Aliran→Bidang picker** (the code's own ambiguous example is *"a PISMP offer
  with no SK/SJKT/SJKC aliran"*). This is exactly the shape we want.
- **The PISMP picker** — `AliranPicker` (SJKT/SK/SJKC/SKPK) → `ProgrammePicker` (bidang) on `/profile`,
  wired to `courses.pismp_taxonomy`; picking a course yields a `course_id` (the catalogue **link**) and
  the `pathway_undeclared` item auto-resolves.
- **Catalogue linking** — `offer_pathway.resolve_catalogue_course(prog, inst)` (used by autofill) for a
  confident PUBLIC tertiary match → `course_id`.
- **The private-arm veto** — a private/IPTS offer already scores `not_official` → red card + can block
  (`offer_not_official`); no new red-path needed.
- **The Check-2 sync + lifecycle** — `check2_queries.sync_check2_queries` runs only while submitted AND
  not `querying_locked`, i.e. **awaiting-review (`profile_complete`) + interviewing**, and locks from
  `interviewed`/decided onward (unless reopened). `_sync_pathway_confirm` mirrors verdict pathway
  queries and is NOT `may_ask`-gated, so it already fires across both those stages. The new confirm
  inherits this window and idempotency for free (re-evaluated every pass).

## Design (system-handled, no officer gate)

### 1. Detection (verdict_engine `_verdict_pathway`)
Raise a confirm when the offer's detected **TYPE** differs from the declared `chosen_pathway` TYPE —
**even when `pathway_confirmed_at` is set** (that's the new bit; the current guard only compares
within-value and only when not confirmed). Compare at the type family level via
`offer_pathway.detect_pathway_type(prog, inst)` vs `chosen_pathway`. Keep the invariant **at most one
pathway query at a time** (type-switch takes precedence over / is exclusive with `pathway_confirm` /
`pathway_undeclared`). Genuine-official offers only (a fake/suspect/private offer is already
flagged/red — never ask "is this where you're going?" about it).

Decide the code shape: either a distinct `pathway_type_switch` code, or reuse `pathway_confirm` with a
`type_switch` param + a `declared_pathway`/`offer_pathway` payload. Prefer a **distinct code** so the
FE copy can name the switch ("You told us STPM, but your offer is PISMP — is PISMP right?") and so it
doesn't collide with the within-type confirm.

### 2. Confirm handler (extend/adjacent to `confirm_pathway`)
On "yes":
- **Public + resolvable** → set `chosen_pathway = offer type`; write `chosen_programme` from the offer
  and **link `course_id`** via `resolve_catalogue_course`; **clear the now-irrelevant `pre_u_track`**
  (an STPM stream doesn't apply to PISMP) and reconcile `pre_u_institution`.
- **PISMP (aliran-ambiguous)** → set `chosen_pathway = pismp` and hand off to the **profile
  Aliran→Bidang picker** by leaving/raising the `pathway_undeclared`-style item (reuse the existing
  route), so the student pins the exact `(aliran, bidang)` → `course_id`, which auto-resolves.
- **Private** → no special handling; the existing `not_official` veto keeps the card red.

### 3. PISMP aliran — a SEPARATE step, aliran PRE-INFERRED (owner 2026-07-18)
The offer letter does not state the aliran, and a catalogue course needs `(aliran × bidang)` — so the
aliran alone can't produce the link. Do NOT cram a multi-choice into the one-tap confirm. Instead:
- Reuse the existing `pathway_undeclared` → profile Aliran/Bidang picker (separate step).
- **Pre-infer the likely aliran** from the student's SPM vernacular subject so the picker opens on the
  probable answer: SPM **Bahasa Tamil → SJKT**, **Bahasa Cina → SJKC**, else **SK** (mirror the
  eligible-PISMP subject logic already in `pismp_taxonomy` / the courses engine). #43 almost certainly
  took BT → SJKT. This gives the tightness of "within the question" (a sensible default, minimal taps)
  without losing a real catalogue link.

### 5. Fold in the undeclared case (#127)
The "nothing declared" case is just this same reconciliation with the declaration set to **empty**, and
it *already* routes through the resolvable/ambiguous fork we're reusing (`_no_declared_pathway` →
one-tap `pathway_confirm` / `pathway_undeclared` → picker). So unify the detection into a single
predicate — **"the genuine offer's (type, programme) does not agree with the student's declaration
(present, different-type, or absent)"** — with the shared resolvable/ambiguous/private handling. Do NOT
keep three parallel branches drifting apart.
- Keep the CURRENT live #127 behaviour intact (it works) — the unification must be behaviour-preserving
  for undeclared: resolvable → one-tap + link; PISMP-ambiguous → picker (now with the §3 aliran
  pre-inference upgrade, which also benefits #127); private → red.
- The only genuinely NEW trigger is case 1 (different TYPE, even after `pathway_confirmed_at`); the
  other two are re-expressed through the same unified detector, not rebuilt.

### 6. Surfaces / i18n
- **FE:** an Action-Centre confirm card for the type-switch (copy names both types); reuse the existing
  PISMP picker for the hand-off — no new bespoke widget. en/ms/ta (Tamil first-draft).
- **Officer:** none required (system-handled). The existing "Switched" cockpit banner
  (`offer_pathway_switch`) already informs the reviewer.

## Scope / cost

- Backend: verdict detection + confirm handler + check2 sync wiring + aliran inference helper.
- FE: one Action-Centre card + copy; picker reused.
- Migration: **none** expected (reuses `chosen_pathway`/`pre_u_track`/`chosen_programme` + the existing
  `pathway_undeclared` route). Bump nothing model-versioned.
- Tests: verdict detection (type mismatch even when confirmed), confirm handler reconciliation
  (public-link / PISMP-handoff / private-red), aliran inference, idempotency + stage-window (never on
  a decided case).

## Edge cases / guards
- **Do not double-fire** with `pathway_confirm` / `pathway_undeclared` (one pathway query at a time).
- **Re-detection after confirm:** the mismatch is `chosen_pathway` type vs the confirmed
  `chosen_programme`/offer type — must survive `pathway_confirmed_at` being set (unlike today).
- **Funding reclassification** is the real effect (PISMP ≠ STPM funding) — that's the whole point; it
  only lands on the student's explicit confirm, within the review window, never on a decided case.
- **Idempotent:** the student may keep changing their programme; the verdict re-evaluates each pass and
  the confirm re-raises / auto-resolves accordingly.

## Definition of done
One unified detector reconciles a genuine offer against the declaration across all three inputs —
**different-type (new, #43), same-type-detail (existing), and undeclared (existing, #127)** — raising a
system confirm in the awaiting-review/interviewing window only. On the student's "yes" the record
reconciles `chosen_pathway` + `chosen_programme` (+ catalogue link for public), clears the stale
`pre_u_track`, and for PISMP hands off to the aliran-pre-inferred picker that lands a linked course;
private stays red; nothing fires on a decided case; #127's current behaviour is preserved. Tests cover
detection (all three inputs) / handler (public-link / PISMP-handoff / private-red) / aliran inference /
idempotency / stage-window. **#43 is the live validation case.**
