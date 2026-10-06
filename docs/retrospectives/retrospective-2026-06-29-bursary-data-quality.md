# Retrospective — Bursary Data-Quality Sprint (2026-06-29)

Worktree `.worktrees/data-quality` (branch `feat/data-quality`), plus earlier commits on
`feature/doc-eval-harness`. 12 commits, all merged to `main` + deployed incrementally. No migration.

## What Was Built

1. **Verdict-aware recommended amount** (`b16b5ecd`). `award.proposed_award_amount` returns `None`
   (no amount) when the live verdict carries a *confident disqualifier* — `offer_not_official`
   (pathway not a genuine official public offer) or `income_above_b40_line`. Cockpit slider shows a
   "No amount — reason" state; a super may override; self-corrects when the disqualifier clears.
   Uncertain codes keep the standard amount.
2. **Continuing-STPM award = RM1,000** (`45b76d29`). An STPM student whose offer reporting date
   predates the cohort year (started a year ago) proposes RM1,000, not RM3,000. Automatic.
3. **Offer reporting-date now persists for confirmed-pathway students** (`a13afed5`). The normalised
   `reporting_date` write was gated behind the `if locked: return False` early-return; moved out so a
   locked (confirmed) student's date is stored too. Backfilled 5 prod rows.
4. **Pre-U standardisation, automatic via the offer autofill:** track → canonical vocabulary
   (Matrikulasi 4 / STPM 2, `b9f68355`); course name → "Program Matrikulasi" / "Tingkatan Enam"
   (`01174409`); institution → matric catalogue college / STPM casing-only (`8a6bb30a`). All run inside
   `autofill_pathway_from_offer` on every offer extraction, idempotently.
5. **Bursary ↔ recommender institution single source of truth** (`e0e113c5`, `d0c67e1f`, `36ea4256`).
   `offer_pathway.catalogue_institution` derives the institution from the recommender catalogue
   (`course_id`/virtual-course → `Institution`), ironing out offer-letter OCR variants. Conservative:
   a UNIQUE match only; it never swaps one institution for a different one (a conflict is surfaced, not
   overwritten). Disambiguates a multi-campus course against the offer's institution.
6. **Recommender catalogue normalisation** (`5db1a8fb`). `normalise_institution_names` expanded the 15
   matric abbreviations (`KM <State>` → `Kolej Matrikulasi <State>`, `KMK` → `…Kejuruteraan…`) and
   upper-cased 6 mis-cased acronyms — 21 rows, the single source of truth.
7. **TD-150** logged (`9b0d8f04`, `965b1b23`) — the course matcher assigning a wrong public `course_id`.

**Prod data fixes (read-only-verified, via the documented local→pooler pattern):** 5 reporting dates;
#62 stale RM1,500 → standard; #31 spurious private `course_id` cleared; 27 matric + 13 tertiary + 1
(#4 UKM) + 30 STPM institution standardisations; 21 catalogue renames; 4 continuing-STPM amounts → RM1,000;
#95 → placeholder Ungku Omar IT course; #80 → IPG Kampus Ipoh.

## What Went Well

- **Dry-run-before-apply caught real harm twice** — the STPM wrong-school matches and the
  course_id-vs-institution conflicts were spotted in a preview, never written.
- **Single-source-of-truth discipline** held: when my own offer-sourced institution drifted, the fix
  was to derive from the catalogue, not to hand-clean strings.
- **Idempotency** designed in — the autofill normalisation produces the canonical value directly, so a
  re-extraction never churns.

## What Went Wrong

1. **Re-extracted documents from a local checkout → corrupted #76 + #16 offer records.**
   *Symptom:* #76's offer verdict flipped from "Verified · Exact read" to `unreadable` (`error: 'no text'`).
   *Root cause:* a local checkout has **no Supabase Storage access**, so Vision/Gemini re-extraction read
   the blob as "no text" and overwrote the good `vision_fields`. The local→pooler pattern gives DB access
   only — not Storage.
   *Fix:* recorded as a durable lesson (`memory/halatuju_never_reextract_locally.md` + `lessons.md`):
   document re-extraction must run on the live service (cockpit "Re-run" / admin endpoint), never locally.
   Restored both via the cockpit Re-run.

2. **STPM school catalogue-matching nearly re-assigned students to the wrong school.**
   *Symptom:* a dry-run would have set Swetha's "SMK Tun Hussein Onn" → "Bandar Tun Hussein Onn 2" and
   "SMK Pulau Sebang" → "SMJK Pulau Sebang".
   *Root cause:* an STPM bidang lists ~250 near-identically-named schools; distinctive-token matching
   drops the `SMK`/`SMJK` prefix as generic and subset-alignment treats a more-specific name as a match.
   *Fix:* excluded STPM from catalogue-matching entirely (casing-only standardisation instead) and added
   a **unique-match guard** to `catalogue_institution` (ambiguous → '' rather than a wrong campus).

3. **Wrongly concluded "matric colleges aren't in the catalogue."**
   *Symptom:* told the owner there was no source of truth for matric institutions; the owner corrected me
   with the `/course/matric-*` pages.
   *Root cause:* searched `Institution.institution_name` for "Kolej Matrikulasi" — but the catalogue stores
   them as "KM Selangor" and links them via the `matric-*` *virtual courses*, not by that name.
   *Fix:* investigate the virtual-course `CourseInstitution` links, not just an institution-name search,
   before declaring "no source exists".

4. **First institution backfill sourced from offer OCR (+ hand-cleaned acronyms) → drifted from the catalogue.**
   *Symptom:* stored `(UKM)` / `(UniMAP)` forms that didn't match the recommender.
   *Root cause:* used the offer text as the source instead of the catalogue (the actual SoT).
   *Fix:* `catalogue_institution` is the single source; the offer is only a disambiguation *hint*.

## Design Decisions

See `docs/decisions.md` (this sprint): verdict-aware no-amount; institution single-source-of-truth +
conservative conflict-surfacing; STPM schools casing-only; continuing-STPM RM1,000; pre-U normalisation
automatic-in-autofill.

## Numbers

- 12 commits, no migration. ~9 incremental deploys (each feature shipped + verified).
- Tests: **1815 scholarship pytest** (+~30 this sprint) — `test_award_rule`, `test_offer_pathway`,
  `test_reporting_date`. (Full combined suite incl. courses/reports run separately.)
- New commands: `backfill_reporting_dates` (extended), `backfill_pre_u_track`, `standardise_pre_u_course`,
  `align_institution_to_catalogue`, `standardise_stpm_institution`, `normalise_institution_names` (courses).
- Prod rows touched: ~100 (reporting dates, amounts, institutions, course names, tracks) — all read-only
  dry-run verified before apply.
