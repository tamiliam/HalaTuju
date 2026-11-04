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

## P5b — ONE page (owner ruling 2026-11-04, after the live phone check found two "Programmes" rows)
- Live defect: old Overview row kept its label "Programmes" (`admin.orgPage.nav`); the new landing row is also
  "Programmes". Local hotfix d8b5be0c (relabel to Overview + duplicate-label test) is NOT pushed — superseded by P5b.
- Owner: "Earlier, both the overview section (top) and programmes section (bottom) were on the same page. It was
  useful... We could call it overview. Except the stat cards should be different for different users. And, they
  should be focused on the work that is pending, if any, for the respective users. There should not be two menu
  items, whatever you call them."
- So: ONE menu row "Overview", ONE page: per-role stat cards on top (pending work for THAT person), programme cards
  below (the P5 per-person list). The other route redirects. Stitch first (new per-role cards), owner approves, then
  build (Opus server for any new per-person counts), review, gates, phone check, deploy ask. Release waits for P5b.
- Planner (Opus) plan, 2026-11-04: keep route /admin/organisation/programmes, row label "Overview" (key
  admin.orgPage.nav, chord V, match also /admin/organisation + /admin/administration); delete the administration row;
  /admin/organisation -> redirect; fix GIFT_DOOR (useGiftGate.ts:52, live bug: points at the old page). New server read
  `GET admin/scholarship/my-pending/` (new apps/scholarship/my_pending.py) from attention() / mine() / qc_queue() /
  next_step_for / mentor_desk / sponsors pending / invitations.open_only; a card the caller may not see is ABSENT;
  org_read door guards cards, not the page. Cards: admin = unassigned, overdue (+due soon), awaiting QC, sponsors to
  vet (+ small: invitations, payment runs, requests); finance = payment runs for your step, wallet credits to sign
  (NEW: pull step check out of sign_admin_credit), sponsors, invitations (no application numbers); QC = awaiting your
  check (NEW: drop qc_separation-barred), oldest days; reviewer = open, due soon, overdue; mentor = current mentees,
  not yet met, asked for help. Stat strip INSIDE ProgrammesLanding's lazy chunk (no new chunk). S1 server Opus, S2 web,
  S3 gates. d8b5be0c folds into S2. Owner Qs (defaults): zero cards stay muted + one all-clear line; mentor gets only
  "not yet met" (no invented threshold); drop the People tile.
- Stitch timed out (5 edits, nothing landed). Design mock as an artifact instead (memory stitch_mcp_workflow: an
  approved artifact mock meets the rule): https://claude.ai/artifact/3SW6oWsmgzZeozYEGeW4Wm (5 tabs + Q1-Q3).
  OWNER "approved" 2026-11-05 (defaults taken for Q1-Q3: muted 0 + all-clear line; mentor "not yet met" only; People
  tile dropped). S1 server (Opus) + S2 web (Sonnet) run in parallel on a fixed contract; then review, S3 gates.
  Contract: GET /api/v1/admin/scholarship/my-pending/ -> {"cards":[{"key","count", optional "due_soon",
  "oldest_days"}]}; keys admin: unassigned, overdue(+due_soon), awaiting_qc, sponsors_to_vet, invitations,
  payment_runs, requests; finance: payment_runs, wallet_credits, sponsors_to_vet, invitations; qc: qc_awaiting
  (+oldest_days); reviewer: my_open, my_due_soon, my_overdue; mentor: mentees, not_met, asked_help. Absent = may not see.
- S2 web DONE (9f13e12e): one "Overview" row (chord V); old Overview + Administration rows gone, both routes
  redirect; GIFT_DOOR fixed; pending strip in the existing lazy chunk; bundle median 144.145 (room 0.9); jest ~5160
  targeted pass. To check: wallet_credits links to /admin/sponsors (no credits page — builder's guess); mentor sandbox
  surface has no pending mock; old Overview page content + tests deleted.
- S1 server DONE (7bf77b8e; builder hit 160k): my-pending route; shared door my_programmes.lands; new
  credit_steps.step_refusal (sign_admin_credit + card share it); qc_separation.barred_ids; pending_sponsor_count();
  16 tests; budgets 11/9/10 constant. Risks: wallet_credits finance-only though admins also sign; super pooled
  payment_runs one lookup per org; mentor cards one query per mentee (TD-500 family). NEXT: Opus adversarial review
  + full gates in parallel.
- Opus review: SHIP after M1 (mentor label said "recently") - FIXED eedc20f4 (en/ms/ta "Not yet met"). Lows for the
  audit / owner: admins+org admins get no wallet_credits card (finance only); finance sees sponsors_to_vet but read-only;
  Admin-General sees org-wide awaiting_qc; invitations card needs org_read (page needs team_read); multi-gift
  payment_runs round trip; mentor/super pooled paths have no query budget (no N+1 found).
- Gates GREEN: pytest 12422 passed / 3 skipped; npm gates 417 suites / 6519 tests; bundle median 144.148 (room 0.9);
  mobile 775 passed (was 781; m8-organisation surface removed). Label fix eedc20f4 landed after the gates (strings
  only). NEXT: owner yes -> push t5c:main (gh switch), watch both builds, owner phone check, then v3.1.0.
- P5b LIVE 2026-11-05 (main f2efa6b0; api halatuju-api-01254-9vx, web halatuju-web-01083-smc; both builds SUCCESS).
  NEXT: owner phone check -> P5b CHANGELOG + short close -> v3.1.0 release.
- Owner phone check 2026-11-05: three asks. (1) Remove sublines (due soon, Nothing waiting). (2) Unassigned = only
  ready to assign: profile_complete + unassigned + is_ready_for_assignment (owner OPTION A = reuse the Assign rule).
  The programme overview tile changes too. (3) Cards link to filtered action pages: ?ready=1, ?band=overdue|due_soon
  on the applications list; payment_runs/wallet_credits/mentor cards unchanged (to the audit list).
  P5c builders (Sonnet): server (ready helper + parity test, attention(), ?ready ?band) + web (sublines, URL filters
  on /admin/scholarship with chip, hrefs). Then Sonnet review, full gates, deploy ask.
- P5c web DONE 38144e07 (bundle 144.147; qc_awaiting / invitations / sponsors_to_vet unfiltered - no filter on those
  pages). P5c server DONE 7ce8de9c (queries_sla.ready_to_assign / assignable_now, per-org query_answer_days, parity
  test; review_sla.in_band; attention(organisation=); 260 targeted pass; SQLite only). Review + gates running.
- P5c review (Sonnet): SHIP + 2 medium. M1 my_open card counts AWAITING_VERDICT but ?assigned=me lists all the
  reviewer's cases -> add band=open (awaiting verdict) and link ?assigned=me&band=open, with a parity test. M2 card
  links carry no ?programme= -> verify whether my-pending counts are gift-scoped; add only if they are. Lows: in_band
  id list (fine at size), double EXISTS annotate. Fix AFTER the running gates finish (mobile-check uses the tree).
- P5c gates: pytest 12432 PASS, mobile 775 PASS, bundle 144.149 OK; jest 2 FAIL (title= on chip button; page.tsx 657).
- P5c follow-up 2b618fc8: band=open for my_open + parity test; M2 parity already holds (cards are all-gifts counts,
  no change); title= dropped; ApplicationUrlFilters.tsx extracted (page.tsx 599). Full pytest 12433 PASS; jest 6525
  with 1 fail (eslint-disable reason) fixed, affected suites 507 PASS; bundle 144.147. NEXT: owner deploy yes.

## Stops waiting on the owner
- **P5 phone check and deploy approval** (asked before each deploy; P5 changes reviewer and mentor access).
- **TD-487 and TD-488 rulings** (from the TD-481 adversarial review).
- **TD-497: Mentors list key ruling.**
- **TD-496: graduation list** (owner's call).
- **TD-499: finance + QC pairing question** (owner's call).
- **Invite gift tag (owner raised 2026-11-04):** no invite takes a gift; NULL gift = "every gift"; the reviewer gift
  only narrows offered cases, not a fence (`reviewers.py:98-103`); mentors have no gift (from mentees); the gift is set
  later via `POST admin/reviewers/<pk>/programme/`, which has no web caller. OWNER RULED "b" 2026-11-04: fix AFTER
  v3.1.0 as the FIRST fix sprint (before other audit fixes): reviewer invite must choose "one gift" or "every gift";
  admins + mentors unchanged; permission change -> Opus build, adversarial review, owner phone check. TD-501.

- **Login sandbox (owner raised 2026-11-04):** "we need to set up a sandbox properly, in future". Today: the design
  sandbox `/sandbox` (2026-07-28, flag NEXT_PUBLIC_SANDBOX, invented data, no logins) is complete for its purpose; there
  is NO way to sign in as a reviewer / mentor / finance / QC to check a change (TD-194: console cannot run locally).
  Lead proposed: a test organisation on live with invented students and one test login per role, kept out of stats,
  emails and billing. Feed into the audit (completeness lens) and the fix roadmap; needs the owner's word (freeze).

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
- S2c DONE (2e0e6b98); origin/main (TD-473) merged 7633b618; fresh review PASS (2 lows, cosmetic). FULL GATES GREEN
  2026-11-04: pytest 12402 passed / 3 skipped (stale-classifications OK under -n auto); npm run gates pass (jest
  415/6487); bundle median 144.706 (room 0.3); mobile-check 781 passed.
- T5c P5 LIVE 2026-11-04 (owner "yes"; main 1c21ecaf; api halatuju-api-01253-gcr, web halatuju-web-01082-t9w; both
  builds SUCCESS). Sprint CLOSED (t5c 31f06292 local, not pushed: changelog, retro, decisions, TD-501, Next Sprint;
  memory cec86c4 + workspace da4d5fc pushed). wat_lint 0 FAIL (warns: 13 small changes await Consolidation Review ->
  fold into the audit; code-health reading skipped -> audit takes it). WAITING: owner phone check. NEXT: v3.1.0 tag
  (release.md) after the phone check OK; the docs commit rides with the release (ask before that push).
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
