# Retrospective — `/scholarship/application` redesign, Sprint 2 ("Your story") — v2.4.1, 2026-05-27

Second sprint of the Step-4 redesign. Plan: `docs/scholarship/application-redesign-plan.md`. Commit `738e104`;
migration `scholarship 0012` (migrate-first).

## What Was Built
The "story" tab went from 4 generic textareas to a **guided two-card section** — *About your family* + *About you*
— forming the statement-of-intent basis. Trimmed to high-signal, mostly-optional prompts (per the signal-vs-burden
review): family = first-in-family tick, parents' occupation, optional siblings-studying + family-situation; you =
aspirations + plan (required for completeness) + optional daily-life + optional worries/support. Visible BM/EN/Tamil
invite + Statement-of-Intent pointer. 5 additive narrative fields + migration `0012`; details serializers + tests;
**story-complete = aspirations + plans** (was aspirations + justification). No profile data re-asked.

## What Went Well
- **Subagent delegation held up again** under deep main-thread context: tight spec → fresh-context build →
  orchestrator reviewed the diff + migration, applied `0012` migrate-first via the Supabase MCP, re-built, deployed
  both services, verified live. The api build also auto-resynced the `release-decisions` job (S1's SyncReleaseJob).
- **Caught the promised cleanup:** the reworked section still carried the old inner "2. Tell us about yourself"
  double-heading; removed it so the card title is the sole heading (the plan said S2/S3 would).
- Migrate-first 0012 verified (5 columns, correct types/NOT NULL, migration row) before the push, so the new api
  code never met an old schema.

## What Went Wrong
1. **Self-inflicted build failure: ran `next build` concurrently with a screenshot subagent's `next dev` on the same
   `.next`.**
   - *Symptom:* my verification build threw `PageNotFoundError: /_document` (a Pages-Router artifact) and exited
     non-zero, despite "Compiled successfully" — a scary false failure mid-deploy-prep.
   - *Root cause:* I parallelised my build with a subagent task that runs a dev server, both writing the same `.next`
     directory — the known build-vs-dev `.next` corruption, caused by concurrency I introduced.
   - *System change:* lesson added — never run a build (or a second dev server) against a project's `.next` while a
     subagent is doing a dev-server/Playwright screenshot there; serialise them (wait for the screenshot task to kill
     its dev server first), or isolate the screenshot task in its own worktree.
2. **Subagent deleted its screenshots before I could review them.**
   - *Symptom:* had to send a follow-up asking it to regenerate + keep them, costing a round-trip.
   - *Root cause:* the delegation spec said "delete `.playwright-mcp` artifacts" without "keep the screenshots for
     orchestrator review".
   - *System change:* lesson/spec note — when delegating build+screenshot work, instruct the subagent to SAVE
     screenshots to a named path and NOT delete them (delete only the preview route + dev server).

## Design Decisions
In the plan doc (story-complete = aspirations + plans; narrative fields additive, old fields retained). Nothing new
architectural.

## Numbers
- 12 files; migration `0012` (5 additive AddField, migrate-first). Full backend pytest **1114**; full frontend jest
  **111**; i18n parity **1190**.
- Both services deployed (web `halatuju-web-00214-kr4`, api `halatuju-api-00167-lzl`); api health 200; v2.4.1;
  verified live.
