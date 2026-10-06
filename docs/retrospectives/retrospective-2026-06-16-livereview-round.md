# Retrospective — Live-review round (2026-06-16)

A single working session of live-review fixes + profile improvements, run as small-change-lane
work. 10 commits (`c6bc963` → `611e6b1`), all deployed. Followed the reviewer-access close earlier
the same day.

## What Was Built
- **i18n hygiene:** TD-118 (removed 6 dead api-client fns + 29 orphaned `admin.scholarship` keys) and
  TD-120 (77 more orphaned keys), plus a **dynamic-aware orphan/parity guardrail test** so the class can't regrow.
- **Cockpit polish:** Decision/profile copy tweaks ("Sponsor profile (draft)", "Rate AI verification", "AI verdict",
  dropped colon), and **hid the redundant assignee filter** for reviewers (their list is already self-scoped).
- **AI profile — completeness & safety (the core of the round):**
  - Distils **all** student inputs that were collected-but-ignored (justification, fears, anything-else, top choices,
    other scholarships, help-wanted, deliberation).
  - Uses the **interest quiz** at last — accretive interest colour in the profile + an exploratory interview question
    when quiz interests diverge from the chosen pathway.
  - Feeds the OCR'd **Statement of Intent** letter (already extracted, never used by the profile).
  - **Grades summarised by GROUP** (no per-subject list) and **ethnicity-safe** — vernacular-language/literature
    subjects fold into generic groups, and ethnic/cultural specifics in the student's own narrative are generalised
    (motivation kept, label dropped).
  - **Prompt versioning** (`PROMPT_VERSION` + `SponsorProfile.prompt_version`, migration `0058`) + a version-aware
    backfill, so a stale draft is detectable by version and only stale drafts are regenerated.
- **Reviewer access:** built the missing **set-password page** so non-Google invitees can set a password (invite +
  reset links now point there); fixed **Kalai's** login (her reviewer record was on a yahoo email she never activated —
  repointed to her working gmail, revoked the dead yahoo account, preserved her assignment).

## What Went Well
- The **prompt-versioning + version-aware backfill** turned a recurring operational risk (stale drafts after a prompt
  change) into a self-checking system — the round's most valuable systemic outcome.
- Live DB investigation (Supabase MCP) made the Kalai and #4-vs-#18 diagnoses precise rather than guessed.
- Every billable regeneration and prod auth mutation was owner-gated; migrate-first kept the schema change safe.

## What Went Wrong
1. **A stale AI draft (#18) sat in production undetected until the owner compared two profiles.**
   - *Symptom:* #18 was in the old (pre-redesign) format — section headers, real name, clichés — while #4 was correct.
   - *Root cause:* no way to tell which prompt produced a draft; the auto-generate sweep is idempotent ("has a draft →
     skip") and the earlier backfill only covered then-assigned applications, so a later-assigned app kept its old draft.
   - *System change:* **PROMPT_VERSION stamped on every profile + a version-aware backfill** — staleness is now a
     version check, not a date guess, and re-running the backfill refreshes only stale drafts. (Candidate: schedule it.)
2. **The TD-118 cleanup over-deleted a live key (`finalProfile.title`).**
   - *Symptom:* deleting the whole `finalProfile` i18n object removed `title`, which the cockpit still renders.
   - *Root cause:* deleted a parent object when only 6 of its 7 leaves were orphaned — didn't verify each leaf.
   - *System change:* caught before deploy; lesson recorded (verify each leaf, not the parent); the TD-120 pass then
     used a per-leaf dynamic-aware scan + a guardrail test that would catch this class.
3. **A raw subject key (`B_TAMIL`) leaked into a profile — non-deterministically.**
   - *Symptom:* one draft printed `B_TAMIL`; a re-generation tidied it — same data, different luck.
   - *Root cause:* a partial hand-rolled subject-label map (`_GRADE_LABELS`) drifted from the canonical subject list,
     so unmapped keys were shouted raw into the prompt.
   - *System change:* stopped enumerating subjects entirely — emit **groups**, with an "other subjects" fallback, so a
     raw key can never reach the prompt. (Also satisfied the owner's "summarise + hide ethnicity" asks.)
4. **Mis-sized the Statement-of-Intent work as a feature before checking the pipeline.**
   - *Symptom:* flagged it as needing OCR/extraction (a sprint); it was actually a small change.
   - *Root cause:* estimated before inspecting — the OCR already existed (`read_text_document` → `vision_fields.text`).
   - *System change:* reaffirmed the existing lesson — inspect the pipeline before sizing the work.

## Design Decisions (see decisions.md)
- Prompt versioning over date heuristics for staleness.
- Grades by GROUP (not per-subject) — readability + ethnicity safety + structural leak-prevention in one.
- Generalise ethnicity in the narrative (keep motivation, drop label) rather than strip or expose.
- Set-password via the recovery flow (client PKCE) as the robust path; reused the existing `generate-profile` endpoint.

## Numbers
- 10 commits; 1 migration (`scholarship/0058`, migrate-first via MCP); prompt at `2026-06-16.2`.
- Backend **2442** pytest (+9), web **322** jest (+2); scholarship suite 1277 green.
- 8 sponsor profiles regenerated onto the current prompt; 0 ethnicity mentions; 8/8 version-tagged.
