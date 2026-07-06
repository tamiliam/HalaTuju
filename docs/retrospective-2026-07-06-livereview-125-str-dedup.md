# Retrospective — Live-review batch #125 (2026-07-06)

Three fixes off a live review of applicant #125 (a second batch the same day, after the header
dates/timeline sprint). All FE/BE, no migration; prod backfill for the STR dedup.

## What Was Built
1. **STR dedup → household-level.** STR is one recipient per household, but `dedupe_income_proof` keyed
   it per member, so the same screenshot re-uploaded under a different member tag (mother vs blank #125;
   mother vs father #45 — both literally the same file) survived as two live copies. Now STR collapses
   across all members of the application (salary/EPF stay per-member); the kept copy inherits the
   recipient tag if blank. Backfilled the two live cases.
2. **No more interview "carried-over" echoes.** `interview_agenda_full` folded every open Check-2 query /
   doc-request into a generic "Carried-over query — confirm at interview" line. The owner deleted them
   every time — a pending upload isn't an interview talking point, and the generic label carried no
   content. Removed; Check-2 Outstanding stays the single home for open items.
3. **Detailed STR request copy.** `str_not_current` now spells out the two MySTR tabs to capture (Semakan
   Status with Nama/MyKad/Status = Lulus, AND Maklumat Pembayaran with recent payment dates), member-neutral,
   so a dateless "Lulus" screenshot no longer reads as enough.

## What Went Well
- **Traced each to a root cause before touching data.** #125's "duplicate STR" wasn't a display glitch — a
  DB read showed two live rows with different member tags, pinpointing the per-member dedup key as the bug.
- **The fix generalised and caught a second case (#45) the owner hadn't flagged** — a sweep for "apps with
  >1 live STR" found #45 (mother+father tags on one screenshot); the same backfill fixed it.
- **Backfill mirrored the deployed ranking exactly** (genuine → dated → newest id + member inheritance), so
  prod matches what a fresh upload would now produce.

## What Went Wrong
- **The dedup shipped 2026-07-05 with a scope bug that the same-day cohort backfill couldn't have caught,
  because the duplicates were cross-member.** Root cause: STR was lumped into a per-member dedup
  (`_DEDUP_DOC_TYPES`) without accounting for its household-level nature — a household proof tagged
  inconsistently defeats a per-member key. Fix: type-specific dedup scope (household for STR, per-member for
  salary/EPF) + a guard test with mismatched member tags. Lesson recorded.

## Numbers
- Jest 463 · scholarship pytest 2103 (+1 STR cross-member dedup test). No migration. Backfill: 2 apps
  (#45, #125), each → one live STR.
