# Retrospective — B40 Phase E/F Sprint 10: Student in-programme + graduation relay (frontend, F9b)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — deploy owner-gated; ships dark behind `SPONSOR_POOL_ENABLED`)
**Migration:** none (frontend-only)

## What Was Built

The student/sponsor UI for F9a's backend.

- **New page `/scholarship/in-programme`** ("My progress"), Stitch-approved, shown once `status='sponsored'`. Three cards
  in the apply/onboarding style: **Semester results** (live progress pill + past results + inline Add-result form with
  CGPA validation + "graduating" checkbox), **Sharing your story** (the 18+-only `promotional_use` toggle, greyed for a
  minor from the server's `is_minor`), **Thank your sponsor** (compose box; a `blocked` submit shows an amber banner
  naming the scan-caught identifier fields so the student edits + resends; status chip pending → approved).
- **Sponsor `/sponsor`** gains a "Messages from students you supported" section — staff-approved notes shown anonymously
  against the student's `ref` only.
- New api-client functions + types for all F9a endpoints; trilingual `scholarship.inProgramme.*` +
  `sponsorPortal.graduationMessages.*` (+48 keys, parity 2399).

## What Went Well

- **The Stitch node-id recovery worked first try (again).** The `generate_screen_from_text` call timed out (the
  documented behaviour); the owner pasted the persisted preview URL's node-id, `get_screen` resolved it, and the
  downloaded screenshot (=w1100 to a Windows temp path) matched the prompt — built faithfully against the render. The
  ASCII-mock-in-AskUserQuestion + node-id dance is now a reliable, low-friction gate (lessons #149/#151/#153).
- **Reused the existing primitives, no new components.** The promo toggle is the shared `@/components/Toggle`; the page
  is the established `AppHeader`/`AppFooter` + `useT` + `useAuth` shell; the sponsor section mirrors the approved S8
  My-students card. Nothing bespoke to maintain.
- **Dark-safe by construction.** Both new client calls (`getSponsorGraduationMessages`, and the in-programme reads)
  degrade on the flag-off 404 to an empty/"not available" state, so shipping with the flag off shows nothing new — the
  same one-flag-lights-both-tiers property as the rest of the pool (lesson #109).
- **i18n parity held via a single script** (write-file, not heredoc — lesson #135), so en/ms/ta moved in lockstep and
  the parity check passed on the first run.

## What Went Wrong

- **The approved Stitch design included an optional results-slip upload control I did not build.** *Symptom:* the
  shipped Add-result form has semester + CGPA + graduated, but no file upload, so it deviates from the signed-off mock.
  *Root cause:* the document-upload pipeline here is a three-step flow (sign-upload → PUT to storage → create-doc), and
  wiring it into this form was disproportionate to its value — the CGPA/`graduated` values are what actually drive the
  sponsor-facing band; the slip is optional myNADI-only evidence. *System change:* logged it explicitly as **TD-104**
  (don't silently drop an approved-design element — record the deviation + the reason so it's a conscious carry, not a
  forgotten gap) rather than leaving the omission undocumented. A dark, held sprint is the right place to defer it.

## Design Decisions

- **Kept the project's `AppHeader`/`AppFooter` nav, not the Stitch bottom tab-bar.** The Stitch render included a
  decorative mobile bottom-nav; the real app navigates via the header, so the tab-bar was treated as visual filler, not
  a spec. (Routine — noted here, not in decisions.md.)
- **Progress pill is derived client-side to mirror the server band** (same thresholds as `pool.derive_progress_state`)
  rather than adding a band field to the results payload — the student page already has the raw `cgpa`/`graduated`, so
  recomputing the label avoids a second source of truth. The authoritative band a sponsor sees is still the server's.

## Numbers

- **Frontend:** `next build` clean (`/scholarship/in-programme` 2.9 kB, 299 kB first-load); `tsc --noEmit` clean for the
  changed files; **283 jest** (unchanged — the pages are render-only, covered by build typing not jest, lesson #47).
- **i18n:** parity **2399** ×en/ms/ta (+48; Tamil first-draft, TD-105).
- **Backend:** untouched (no migration; the F9a endpoints were already in).
- **Files touched:** 6 (in-programme page [new], sponsor page, api.ts, 3 message files).
- **Deploys:** 0 (held; ships dark). **Carried:** TD-104 (slip-upload control deferred), TD-105 (F9b Tamil refine).
