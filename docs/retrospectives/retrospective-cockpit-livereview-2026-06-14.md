# Retrospective — Cockpit live-review + verification-accuracy round (2026-06-14)

**Shipped & live on `main`:** `245facd` → `8b307c8` → `51c17d3` → `97a7793` (4 commits, NO migration). A live-testing
pass over the officer cockpit + the income/document verification engine, driven by the owner reviewing real applicants
(#72, #54, #37).

## What Was Built
1. **Cockpit review round 8** (`245facd`): the **final sponsor profile now runs on Gemini 2.5 Pro** (the conclusive
   sponsor-facing doc; drafts stay on Flash) and the refine prompt now folds in the **four-fact verdict + written
   conclusion + recommended assistance** (`_render_officer_decision`); **Approve** is gated on a recommended assistance
   amount; **"Suggest interview questions"** returns **3 at a time** with a **"Generate more"** that appends, and the
   generator is fed the academic record + verification verdict + pre-interview flags + answered Check-2 items; the
   academic Check-2 queries now name the missing subjects + the grades page.
2. **Brand restyle** (`8b307c8`, web-only): the cockpit's ad-hoc `blue-600`/`indigo` accents folded into the brand
   `primary` (#137fec); softer cards (`rounded-2xl`, `p-5`); stronger section headers. Structure unchanged.
3. **Weighted address matcher** (`51c17d3`): `vision.address_match` (found/unconfirmed/mismatch) — **house number
   anchors, street confirms the road, postcode OR city confirms the town**, abbreviations normalised both sides. Fixes a
   whole class of false "address miss" (Port↔Pelabuhan Klang, Skudai↔JB, Georgetown↔P.Pinang, JLN/SG abbreviations,
   postcode-absent bills). Cohort scan: 15 bills flagged, **none a genuinely different home**; recomputed all 15 to green
   via MCP (no billable calls).
4. **Route-aware income genuineness cap** (`51c17d3`): a suspect **optional** doc (future-dated EPF on the STR route)
   no longer downgrades INCOME green→blue. Only the route's **required** proof can cap (STR→STR, +BC when earner=mother).
   The suspicion still raises the officer "document not genuine" flag.
5. **EPF mining** (`97a7793`): the KWSP Penyata Ahli now yields **avg monthly contribution** (mean of all CARUMAN months;
   the income estimate drives off this), **contribution_status** distinguishing a genuine **zero** ("no formal salary")
   from an **unreadable** table, the **statement date**, and the member **address**.

## What Went Well
- **Investigate-then-fix as a class.** Each owner-flagged case (#72 address, #72 income tile, #54 salary slips, #37
  EPF mis-slot) was traced to root cause in prod data before any code, then fixed as a *class* (cohort scans), not a
  one-off. #72's 15-bill false-positive class was sized and recomputed cohort-wide.
- **Checked an assumption before building.** For #54 I was about to add a "gross == net → suspicious" salary-slip flag;
  the owner's "both parents retired" note revealed gross==net is *normal* for pensions — so the flag would have
  false-flagged every pension. Not building it was the right call.
- **No-cost backfills.** Address verdicts (#72 class) and the matcher refresh were recomputed from already-extracted
  text via MCP — zero billable OCR/Gemini calls.
- **Graceful degradation.** The FE address tone maps legacy `not_found` → amber, so the false-red cleared cohort-wide
  the moment the deploy landed, even before the recompute.

## What Went Wrong
- **Pushed onto another agent's branch by accident.** *Symptom:* `git merge --ff-only` + `git push origin main` run in
  the primary checkout advanced the *other agent's* branch `td-sprint0-cleanup` (and applied my files to their worktree)
  and reported "Everything up-to-date" — my commit hadn't reached `origin/main`. *Root cause:* the primary checkout's
  branch had been switched to the other agent's branch since my earlier rounds; I assumed it was still on `main` and
  didn't check `git branch`/`git status` before the git ops. *Fix:* recovered by pushing via refspec
  (`git push origin epf-mining:main`) and leaving their branch+WIP untouched; **lesson added** — when another agent
  shares the repo, verify the current branch (and do all git ops in your own worktree) before merge/push.
- **EPF averaging needs a re-parse for existing statements.** *Symptom:* the new avg/zero/address/statement-date fields
  are blank on already-uploaded EPFs. *Root cause:* they require the caruman rows, which aren't in the stored extracted
  fields — only a re-OCR/Gemini re-run repopulates them (billable). *Fix:* shipped with a graceful fallback (the income
  estimate uses the latest-month figure for old records); logged as TD for a targeted re-run when wanted.

## Design Decisions
See `docs/decisions.md`: weighted (house-anchored) address matcher; route-aware income genuineness cap; Gemini 2.5 Pro
for the final profile only; EPF income from the *average* contribution.

## Numbers
1231 scholarship pytest · 306 jest · `next build` clean · i18n parity 2672×3 · 4 commits · 0 migrations · both Cloud
Builds SUCCESS (web 200 / api 401).
