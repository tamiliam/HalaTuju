# RUN_STATE — HalaTuju autonomous run

## Grant
Owner, 2026-11-04 (second grant, given to lead session "Release"; extends the first): "finish T5c (part 5 after I
approve the Stitch design), release v3.1.0, then run the full audit from your plan as a run. Ask me before each deploy."

- Scope, in order: (1) T5c P5; (2) release v3.1.0 (tag + release notes); (3) the full audit — code health,
  completeness, redundancy, speed, security — then its fix sprints, most important first (TD-465 money bug on top).
- No new features during the audit (freeze, like the September code-health arc). No T5d, no offer S7.
- Every deploy is asked first. A push deploys, so nothing is pushed to main without the owner's yes.
- The audit needs a new workflow (`Settings/_workflows/project-audit.md`, proposed 2026-11-04). A workflow edit is on
  the stop list: write it only after the owner's yes.
- A new lead session resumes from this file alone.
- First grant (done): "continue as a run: T5c on your own. Ask me before each deploy."

## Done
- TD-481 live (main 307d204c; api halatuju-api-01249-zqp, web halatuju-web-01078-pgb).
- T5c part 1 (P1-P4) live 2026-11-04 (main ac68a361; api halatuju-api-01251-l9v, web halatuju-web-01081-957).
  Page doors open by v2 keys (`staff_tables.DOOR_KEYS`, `opens_door`); `admin/role/` serves `page_keys`. No access moved.
  Retrospective: `docs/retrospectives/retrospective-2026-11-04-team-tables-t5c-part1.md`.

## NEXT: T5c P5 = the Programmes landing
Owner rulings, 2026-11-04:
- Everyone on partner login lands on Organisation → Programmes.
- Admins see the other Organisation items, by keys.
- Reviewers and mentors see only Programmes under Organisation. A reviewer's or mentor's list shows ONLY the
  programmes where they have work: reviewer = every case assigned to them, open or done; mentor = scholars they
  mentor, current assignments.
- Stitch design APPROVED ("the design is fine"). Stitch project 10844973747787673276; nodes
  919496a7d36e407db96212baabb52eaa (admin), 40a623069cd64a7b898c6db1b1f0b8ad (reviewer),
  515f7bab8edf4dbc8e668ab89801f525 (phone), b370b2afe43142219f4f582927619249 (empty). Artifact:
  https://claude.ai/artifact/98mNFG2kkY55UsTXc47N2q

Design answers (lead defaults; the owner did not object):
- Admin card keeps today's counts (intake years, applications, awarded).
- Reviewer card: one count, "Cases assigned to you".
- Mentor card: "Scholars you mentor". Its link opens My students filtered to that programme, NOT Programme Overview
  (owner option 1).
- No new "My work" nav group.
- Archived programmes are shown to a reviewer only if they had work there (grey "Archived" pill).
- A person who is both reviewer and mentor: the list is the union. A programme with cases opens Programme Overview
  (their own cases); a mentoring-only programme opens My students filtered.

Lead rulings:
- A reviewer opening the overview of a programme with no work gets 404.
- "Work" = all assigned cases (open or done).

### Plan (from the planner)
- **S1 server (Opus):** a narrowed programmes read, e.g. `GET admin/scholarship/my-programmes/`:
  - admin: today's counts, by keys;
  - reviewer: assigned count per gift, plus the archived flag;
  - mentor: scholars per gift.
  Add the 404 rule on the overview. Tests per role and an org fence. The permission matrix gains the new route's
  cells (EXPECTED_CHANGES lines for the reviewer and mentor shapes).
  Facts: the card grid is `components/admin/GiftProgrammes.tsx`, fed by `AdminProgrammeListView`
  (`views_admin/gift_programmes.py:60`, ROLES org_admin only). Overview: `views_admin/overview.py:21` and
  `programme_overview.SECTIONS_BY_ROLE`. Reviewer → gift via `ScholarshipApplication.assigned_to` + `.programme`.
  Mentor → gift via `MentorAssignment` (`mentor_desk.current_assignments`).
- **S2 web (Sonnet, or Opus):** `app/admin/organisation/programmes/page.tsx` becomes a real page (today a redirect);
  new `ProgrammesLanding.tsx`; `navigation.ts` rows and `defaultRoute` (keep the reviewer incomplete-profile →
  /admin/profile rule); i18n en / ms / ta. `navigation.ts` is 675 lines, AT its size cap: split it first. Lazy-load
  GiftProgrammes' mutation dialogs to keep the bundle median (headroom only ~0.1 kB).
- **S3 gates:** pageWidth, mobileStandard, mobile-check ledger, bundle-budget, code-standards.json.
- Fresh review after each phase. Opus adversarial review on S1 and S2.
- Owner's phone check (P5 DOES change access for reviewers and mentors), then deploy approval.

## Stops waiting on the owner
- **P5 phone check and deploy approval** (asked before each deploy; P5 changes reviewer and mentor access).
- **TD-487 and TD-488 rulings** (from the TD-481 adversarial review).
- **TD-497: Mentors list key ruling.**
- **TD-496: graduation list** (owner's call).
- **TD-499: finance + QC pairing question** (owner's call).

## Open risks
- T5c changes permissions. The owner's phone check comes before it goes live.
- Debt numbers: parallel sessions have collided on TD numbers. Claim the TD range in the first announce message.

## Worktree note
- `.worktrees/t5c/halatuju-web/node_modules` is a JUNCTION to the main checkout's node_modules. Delete the junction
  (`rmdir`, not `rm -rf`) BEFORE any `git worktree remove`.
