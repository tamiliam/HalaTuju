# Brief — PISMP offer: confirm PISMP + bidang, then aliran (use the letter, don't infer)

**Status:** DONE (code) 2026-07-18 — backend + FE, **2803 scholarship pytest + 592 jest green**,
tsc-clean. NO migration. Owner gates the push; the one-time **#43 data reconcile is deferred** until
the Supabase MCP is back. Follow-up to TD-161, off two live bugs on **#43** (a Bahasa Tamil PISMP offer).

## Shipped
- `pathway_engine.student_offer_check` surfaces **`bidang`** (aliran left as a soft hint only).
- `offer_pathway.pismp_courses_for_bidang(bidang)` (reverse-match, `requirement__source_type='pismp'`,
  `(ALIRAN)`-suffix strip + strict distinctive-token equality) + `resolve_pismp_course(bidang, aliran='')`.
- `_verdict_pathway`: every PISMP pathway item carries `bidang` and — when the bidang pins a UNIQUE
  course — `course_id`/`course_name`/`aliran`; else `aliran_hint`. A unique-bidang undeclared offer is
  now RESOLVABLE (one-tap confirm, not the picker).
- `services.confirm_pathway`: pins the resolved PISMP `course_id`+name → the cockpit links the right
  PISMP course and drops the stale STPM track (Bug 2).
- FE: `localiseParams` shows the resolved course / bidang instead of the generic "…(PISMP)"; the card
  routes to the aliran picker ONLY when the bidang is multi-aliran (`course_id` absent) — a resolved
  bidang is a plain one-tap confirm. Rendered #43 card: *"…your offer letter is for PISMP (Bahasa Tamil
  Pendidikan Rendah (SJKT) at IPG Tuanku Bainun)…"* → one-tap, course pinned.
- Tests: `TestPismpBidangResolver` (unique/multi/collision/blank) + a verdict+confirm bidang test.

## Carry
- **#43 data reconcile** (MCP): set `chosen_pathway='pismp'`, clear `pre_u_track`, pin
  `chosen_programme.course_id=50PD04TA` (Bahasa Tamil SJKT). Clears the redundant question + fixes the
  Academic box. (Or the student simply taps the new one-tap confirm — `confirm_pathway` now does it.)
- Refinement: the multi-aliran picker could pre-fill the bidang (known from the offer) and ask only the
  aliran; today it routes to the full profile picker with the aliran pre-inferred.

## Problem (from #43, live)

1. The switch/confirm **re-asks and would send the student to a blind aliran picker** even though the
   offer letter **states the bidang** — because the pipeline drops the bidang and matches only the
   generic "PISMP" programme string.
2. The cockpit **Academic box is internally inconsistent** — programme name "…PISMP" but the
   `(Sains Sosial)` track + a "Tingkatan Enam Sains Sosial" link — because #43's record is stale
   (`chosen_pathway=stpm`/`pre_u_track=sains_sosial` next to a PISMP `chosen_programme`, from a
   pre-fix confirm).

**Root causes:**
- `pathway_engine.student_offer_check` surfaces `stream` but **drops `bidang_pengkhususan`** (and the
  soft `aliran`) — both ARE captured in `vision_fields.fields` (verified on #43's snapshot).
- `offer_pathway.offer_is_resolvable` reads only the generic `programme` → PISMP never resolves →
  always "ambiguous → picker".
- **The aliran is NOT on the letter.** #43's `aliran="…(SJKT)"` was **Gemini-inferred** from the
  bidang (`capture: ai`) — unreliable, and for **Bahasa Inggeris (3 alirans) / Bahasa Melayu (4) /
  Maths etc.** the bidang maps to *several* alirans, so it can't be derived at all.

## Design (owner 2026-07-18)

Trust only what the letter reliably states — **PISMP** (title/programme) + **bidang** (`BIDANG
PENGKHUSUSAN`). Ask, then confirm the aliran only when genuinely needed:

1. **First confirm names what we know:** *"Your offer is for **PISMP — {bidang}** at {IPG}. Is this
   your pathway?"* No aliran assumed.
2. **On "yes" → the aliran, scoped + often skippable:** match the bidang against the catalogue to get
   the aliran set that **exists for that bidang**:
   - **one** aliran (Bahasa Tamil→SJKT, Bahasa Cina→SJKC) → **auto-pin the course, no question**;
   - **many** (English/BM/Maths) → a one-tap aliran pick **scoped to that bidang's set**, default
     pre-selected from the student's SPM vernacular subject; the pick pins the exact `course_id`.
3. **Drop the inferred `aliran` as a source of truth** — the bidang (literal) is the key; the
   **catalogue** is authoritative for the aliran set + the course.

## Changes

**Backend**
- `pathway_engine.student_offer_check`: add `bidang` (from `fields.bidang_pengkhususan`); keep `aliran`
  only as a soft hint (not authoritative).
- **NEW `offer_pathway.pismp_courses_for_bidang(bidang)`** → `[{course_id, course_name, aliran}]`:
  `Course.objects.filter(source_type='pismp')`, strip the `(ALIRAN)` suffix (reuse
  `courses.pismp_taxonomy.aliran_of` for the aliran), match the bidang by distinctive-token overlap
  (mirror the FE `bidangForAliran` shape). Returns the aliran variants for that bidang.
- **PISMP resolvability:** a PISMP offer whose bidang maps to **exactly one** course → resolvable
  (auto-pin). `offer_is_resolvable` / the verdict use this instead of the generic
  `resolve_catalogue_course`.
- `services.confirm_pathway`: for a PISMP confirm, **pin the resolved `course_id` + name** into
  `chosen_programme` (from the bidang when unique; else from the aliran the student picks) — this is
  what fixes the display (Bug 2): a pinned `course_id` makes the cockpit link to the right PISMP course
  and drop the STPM track.
- The pathway hearing item (`pathway_type_switch` / undeclared `pathway_undeclared`) carries `bidang`
  (+ the resolved course when unique) in params so the copy can name it.

**Frontend (`halatuju-web`)**
- The confirm card **names PISMP + bidang** (from params). When the bidang is unique → the existing
  one-tap confirm (now naming the course). When ambiguous → after the confirm, show the **`AliranPicker`
  scoped to the bidang's aliran set** (via `bidangForAliran`/`pismpAlirans` off the eligible payload),
  default pre-selected (`aliran_hint`), then `ProgrammePicker` collapses to the single bidang → pins it.
- Reuses `AliranPicker` / `ProgrammePicker` / `PathwayPicker`; no new widget. i18n en/ms/ta for the
  bidang-named copy (Tamil first-draft).

**Data (one-time, when Supabase MCP is back)**
- Reconcile **#43**: `chosen_pathway='pismp'`, clear `pre_u_track`, pin `chosen_programme` to the
  SJKT "Bahasa Tamil Pendidikan Rendah" course (`course_id` + name + institution IPG Tuanku Bainun).
  Clears the redundant question AND fixes the Academic box.

## Tests
- `pismp_courses_for_bidang`: Bahasa Tamil → one (SJKT); a multi-aliran bidang (e.g. Bahasa Inggeris)
  → the full set; a nonsense bidang → []. (Uses `Course` fixtures with `source_type='pismp'` names.)
- `student_offer_check` surfaces `bidang`.
- verdict: a PISMP switch/undeclared carries `bidang`; a unique-bidang offer is resolvable (auto-pin),
  a multi-aliran one is not.
- `confirm_pathway`: a PISMP confirm pins the resolved `course_id` and clears the STPM track.
- FE: the card names the bidang; the aliran step shows only when ambiguous.
- Full `pytest apps/scholarship` + `jest` green.

## Verification
- A matrix/demo over: Bahasa Tamil (auto-resolve), Bahasa Inggeris (aliran pick), a non-PISMP switch
  (unchanged) — driving `build_verdict` + rendering the card copy; delete after.
- Live (MCP): after the #43 reconcile, the cockpit shows PISMP consistently and the switch question is
  gone.

## Out of scope / notes
- No migration. Gemini's inferred `aliran` stays extracted but is demoted to a hint; a future
  extraction tweak could stop asking Gemini to guess it.
- The earlier aliran-inference + `/profile?aliran=` picker (TD-161) remain the fallback for a truly
  aliran-less offer; this adds the bidang-first fast path.
