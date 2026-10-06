# Retrospective — Check-2 / Interview-Stage redesign, Sprint 1

**Date:** 2026-06-13 · **Branch:** `check2-check3-s1` (`747d5fd`, not merged/deployed)

## What Was Built
Structural split of the officer cockpit's "Outstanding" box. It previously merged student-facing Check-2
tasks (resolution items) with interview content (pre-interview flags + AI gaps) and the "Suggest interview
gaps (AI)" button. Now:
- **"Check 2 — Outstanding"** holds only student tasks — count + empty-state keyed to resolution items
  alone; added subtitle "Student tasks to clear before review".
- **"Interview Stage"** (renamed from "Interview findings") owns the agenda (flags + AI gaps, already paired
  with the reviewer's note/verdict), the moved Suggest-gaps button, and an In-progress/Submitted status pill.

Presentational only — no data, model, or behaviour change.

## What Went Well
- Worktree isolation off `origin/main` kept the work clear of the concurrent course-selector agent (two of
  its worktrees `spm-catalogue`/`uptvet-coverage` were live throughout).
- The existing interview section already combined anomalies + gaps, so the "move" was mostly relocating the
  button + rename — minimal new code.
- Verified clean first time: jest 306, `next build` exit 0, i18n parity 2854×3.

## What Went Wrong
- **A mid-edit was interrupted, leaving the file with unbalanced JSX for one turn.** Symptom: after two of
  three Outstanding edits applied, the third (removing the flags/gaps block) was declined, so the box briefly
  had an opened `<ul>` with the old closers still present. Root cause: I split one structural change across
  three sequential edits, so an interruption between them left invalid intermediate state. Fix/learning:
  surface the half-applied state immediately (done) and offer continue/revert; for a single structural
  collapse, prefer one atomic edit of the whole block over three partial ones where practical.

## Design Decisions
Captured in `docs/scholarship/check2-check3-roadmap.md` (5 decisions: officer-decides+AI-hint; auto-draft
once at handoff; "Interview Stage" name; column order; single querying control in Outstanding only) and
`docs/decisions.md`.

## Numbers
jest 306 pass · `next build` exit 0 · i18n parity 2854×3 · 6 files (1 tsx, 3 i18n, CHANGELOG, roadmap doc).
