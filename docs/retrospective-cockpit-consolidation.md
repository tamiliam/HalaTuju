# Retrospective — Officer cockpit consolidation

**Branch:** `feature/cockpit-consolidation` (off `main`, 2026-06-08). NOT merged/deployed at time of writing.
**Spec:** `docs/scholarship/cockpit-consolidation-plan.md` (owner-approved). Stitch mockup approved
("Officer Review Cockpit – Krishita Vinaasri", node-id `07d4a65ca1f04f5196713edfa2ad00e4`, project
`10844973747787673276`).
**Goal:** one cockpit, no duplicated questions, no lost signals. ~11 overlapping action panels (old Phase-C
panels layered under the verdict redesign) collapsed to ~7, with a clean two-column layout.

## What shipped (8 commits)

| # | Commit | Change |
|---|--------|--------|
| spec | `6cf92b6` | Approved consolidation build spec doc |
| 1 | `4a10d00` | Removed the Consent panel (record + gating untouched); Assign-a-reviewer viewer-hidden |
| 2 | `f05f90e` | **Backend dedupe** — `get_anomalies` drops `vision_nric_mismatch`/`vision_name_mismatch` (verdict tile + identity caveat own them) so Outstanding never double-asks. +1 regression test |
| 3 | `48c071b` | **Outstanding panel** — merged Caveats + Pre-interview flags into one card: "Student to-do" (Resolve/Ask) vs "Ask at interview" (flags + AI gaps). +6 i18n keys |
| 4 | `909e009` | Moved IC + parent-IC **OCR display into Documents** (reviewer reads evidence in Documents) |
| 5 | `0b08466` | **Decision panel** — merged Verify-&-accept into Record-your-verdict; audit→accept gate preserved verbatim. +1 i18n key |
| 6 | `3a51d57` | **Hide raw inputs** — Note/Story/Funding collapse behind a "Show the student's own words" reveal under the Sponsor profile. +1 i18n key |
| 7 | `7056ef2` | Relocated **Estimated need** (top of right col, beside Decision) + **Assign** (below Decision) |
| 8 | `df2379c` | **Reordered left column** to Verdict / Profile / Outstanding / Interview / Documents |

## Final layout

```
About the student — factual cards, always visible: Contact · Family · Academic · Support
Two columns (right sticky):
  LEFT                                   RIGHT (sticky)
  1. Verification verdict (tiles)        1. Estimated need
  2. Sponsor profile                     2. Decision (verdict audit → verify → accept)
     └ ▸ Show the student's own words     3. Assign a reviewer (viewer-hidden)
        → Note + Story + Funding
  3. Outstanding (caveats + flags)
  4. Interview findings
  5. Documents (+ IC/parent-IC OCR)
```

## Gone as standalone (functions preserved, merged elsewhere)
Pre-interview flags → Outstanding · Verify-&-accept → Decision · Record-your-verdict → Decision ·
the OCR display → Documents · Consent panel → removed (record + sponsor-share gating kept).

## Risks respected
- **Decision gate intact** — accept stays disabled unless the profile is complete AND every checklist box is
  ticked; the accepted/shortlisted/not-shortlisted branches + `doVerifyAccept`/`doReject`/`toggleMentoring`
  are byte-for-byte the originals, just re-housed.
- **No signal lost** — flags survive inside Outstanding; the dedupe removes only the two identity duplicates
  that already have a verdict/caveat home.
- **request-info** (the shared `infoNote` compose box that the Outstanding "Ask" buttons + Decision tools
  target) was deliberately KEPT (in the left column under Interview) — collapsing it would have broken those
  flows. It is no longer a headline panel.

## Gates
- `next build` clean; **276 jest**; **845 scholarship + (courses unchanged) pytest**; i18n parity **2134** × en/ms/ta.
- No migration. Backend change is one additive serializer filter + its test.

## Deferred / open
- **MyKad checkbox-into-fact-row collapse** (plan §Decision) — kept the 4-item checklist as-is inside Decision
  to preserve the accept gate exactly; the cosmetic collapse is a later polish.
- **request-info fold into Decision tools** — kept as the shared compose box; revisit if it reads as clutter.
- **STEP-4 refine without a formal interview** (plan open question) — unchanged; "Save verdict & generate
  final profile" still needs a submitted interview.
- **Tiered models** (cheap first cut / premium final) — parked, measure flash-vs-pro on a real student first.
- **Live click-through** of the new cockpit (TD-070) once deployed.

## Lessons
- Large cross-column block moves on a 1600-line page are the highest-risk edits; doing them as small,
  individually `tsc`/`next build`-verified commits (with a clean checkpoint commit before the riskiest one)
  kept every step recoverable via git.
- IIFE-local consts (`hasStory`, `fe`, `rmRange`) don't survive a relocation — recompute them locally in the
  new home (a small IIFE) rather than hoisting and risking shadow/unused-var lint.
- A content-anchored Python move (find-by-marker, slice, reinsert) is far safer than a 244-line exact-match
  Edit for relocating a big panel.
