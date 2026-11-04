# RUN_STATE — HalaTuju autonomous run

## Grant
Owner, 2026-11-04 (second grant, given to lead session "Release"; extends the first): "finish T5c (part 5 after I
approve the Stitch design), release v3.1.0, then run the full audit from your plan as a run. Ask me before each deploy."

- Scope, in order: (1) T5c P5; (2) release v3.1.0 (tag + release notes); (3) the full audit — code health,
  completeness, redundancy, speed, security — then its fix sprints, most important first (TD-465 money bug on top).
- No new features during the audit (freeze, like the September code-health arc). No T5d, no offer S7.
- Every deploy is asked first. A push deploys, so nothing is pushed to main without the owner's yes.
- The audit follows `Settings/_workflows/project-audit.md` (owner: "yes to project-audit.md", 2026-11-04; written
  and pushed, workspace b292ac9). Audit commit = the v3.1.0 tag.
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
- BEFORE THE FIRST PUSH: Cockpit session pushed TD-473 (479b3d1e) to main on 2026-11-04. Check its build is GREEN,
  then merge origin/main into t5c and re-run gates. Session python-da has no HalaTuju work (confirmed 2026-11-04).
- This run claims TD-500..TD-519.

## P5 progress
- S1 server BUILT 2026-11-04 (8c798203, not pushed): `GET admin/scholarship/my-programmes/`
  (`views_admin/my_programmes.py`); Overview `?programme=` 404 for a non-every-gift caller with no case there;
  new matrix list `t5c_p5_added_cells` (not EXPECTED_CHANGES). Builder interpretation to confirm: QC treated as
  admin-shaped (full list + counts; its scope is already 'all'). Opus adversarial review: SHIP (no leak; 3 lows).
  QC card RULED by owner 2026-11-04 ("a"): QC gets the admin card with counts, as built. Record in decisions.md.
- In progress (parallel, same worktree, api-only vs web-only paths): S1b server (Opus: ?intake= side door, grouped
  queries + query budget, mentor ?programme= filter, v2 key + door) and S2 web (Opus: landing page, nav split,
  i18n, mobile gates). Neither edits CHANGELOG/RUN_STATE; the close agent writes CHANGELOG for S1b + S2.
- S1b DONE 2026-11-04 (00c12611): ?intake= door closed; grouped queries + 4 `_admitted` budgets; mentor filter
  `admin/mentor/students/?programme=<int>` (no match / other org = 200 empty; non-int = 404); NO v2 key for the
  landing (every staff login opens it) — door `programmes_landing` with no key + LandingContent tests. Needs review.
  RISK: `test_org_fence.py::test_no_stale_classifications` fails under `-n auto` (view discovery by subclass; file
  not touched) — check at full gates; if it fails, fix in this sprint (never skip). TD-500 to record (close agent):
  mentor list one alias query per mentee (`mentoring.is_the_student`, identity-sensitive).
- S2 web BUILT 2026-11-04 (f9d99859 nav split moves-only; 8576762e landing): gates pass (jest 414/6477, mobile 70/70
  green, new cells 0/0/0/0) EXCEPT bundle-budget: median 144.893 vs 145 (room 0.107 < 0.25 required) and
  /scholarship/application 205.918 vs 206 (room 0.082; growth not from S2). Builder hit 154k -> S2b fresh builder
  trims weight. Tell owner: Overview page no longer shows the gift cards (moved to Programmes); super still lands
  on /admin. `.worktrees/t5c/halatuju-web/.env.local` copied from main (gitignored) — delete with the worktree.
- S2b DONE 2026-11-04 (0bafbb84): bundle median 144.705 (room 0.295); /scholarship/application passes near-line;
  cause = runtime chunk map (+2 lazy chunks); fix = folded lazy imports into named chunks ad/sp/sd/mi/bt; 7 test
  guards changed to accept the chunk-name comment (reviewer to confirm not loosened). npm run gates pass.
  Throwaway baseline worktree removed (junction first).
- Review of 00c12611..0bafbb84: FAIL (medium: 7+1 lazy-load test guards loosened by 0bafbb84; no leak). Lows: vacuous
  door for the landing (OWNER RULED "a" 2026-11-04: always-open page, no v2 key; exception written into
  halatuju_api/CLAUDE.md by the lead, uncommitted — commit with S2c), stale comments, archived reviewer card may open the general overview. S2c (Sonnet) fixing all + CHANGELOG
  + TD-500. Then: re-review S2c, full gates (Haiku), phone check, deploy ask.
- Updated phone-check summary (S2 review): + mentors tapping a programme see just those students; + reviewer
  "not found" also by intake year; + programme cards (New, Change code, Delete) moved off Organisation Overview onto
  Programmes, Overview keeps its counts; super still opens on the platform page.
- Owner phone-check summary (from the S1 review): everyone opens on one Programmes page; admins, finance and QC see
  every programme of their org (finance no numbers); reviewers only programmes with a case of theirs (open or done);
  mentors only programmes of current mentees; a reviewer opening another programme's overview gets "not found";
  partners, sources, stopped mentors, switched-off staff still kept out; no other org, no other page changed.
- S2 must also add: `?programme=` filter on `admin/mentor/students/` (mentor card link); a v2 key in CATALOGUE_V2
  + a door in `_doors` for the landing page.
- T5c changes permissions. The owner's phone check comes before it goes live.
- Debt numbers: parallel sessions have collided on TD numbers. Claim the TD range in the first announce message.

## Worktree note
- `.worktrees/t5c/halatuju-web/node_modules` is a JUNCTION to the main checkout's node_modules. Delete the junction
  (`rmdir`, not `rm -rf`) BEFORE any `git worktree remove`.
