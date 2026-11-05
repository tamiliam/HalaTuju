# HalaTuju project audit, 2026-11-05

**Audit commit:** tag v3.1.0 / `442b21f4` (every lens read this commit).
**Workflow:** `Settings/_workflows/project-audit.md`. Five lenses (code health, completeness, redundancy, speed, security), then a fresh Opus verification of every high, security and money finding.
**New debt entries:** TD-512 to TD-523 (range claimed after the highest number found on main and all open branches, TD-506, with a gap of five left for Lane B).
**Status:** report written, awaiting the owner's ranking (step 6). The freeze is on: security fixes, live-defect hotfixes and operations only.

## Summary (ten lines)

1. 74 findings stand after verification: 1 high, 45 medium, 28 low. Three claims were rejected outright and several high ratings came down to medium.
2. The one high is money: an accepted STPM case with an unknown start year gets RM3,000 automatically (TD-465). Part (1) is fixed on branch money-a and under review; part (2) is still open.
3. Top of the security list is SEC-01: a student can register another student's stored file (offer letters are guessable inside one organisation). Medium today, high once bursary agreements exist. A hotfix is built on branch sec-a.
4. SEC-02: a user-writable field decides who may claim an invited staff row. The code flaw is real; it can only be used if Supabase "Confirm email" is OFF. The owner is checking.
5. SEC-10 is a quick win: two version bumps (DRF 3.18.2, pyjwt 2.15.0) close an unauthenticated memory blow-up and an auth-path 500.
6. The Next.js "critical" (SEC-15) cannot be reached in our set-up (Linux, image optimiser off); what is left is denial of service. The Next 15 upgrade is still the first fix sprint.
7. Live harm today: recording a verdict is slow (17 of 23 real calls over 30 s in 30 days, worst 51.9 s). This is the cause of org request 61.
8. The partner CSV export of NRIC, income and disability has no audit line and no spreadsheet-formula guard (SEC-04).
9. There is no way to withdraw an award once it is out (CO-09 / TD-198). The money is stuck, not lost.
10. The debt register reads 219 open, not the 137 its index claims; 44 entries can be merged and 1 closed. The Consolidation Review is overdue (CH-02). The code-health FAIL (bundle ratchet) is accepted: it comes from the owner-approved Next 14.2.35 security patch (`442b21f4`).

## Live facts (read 2026-11-05)

- SPONSOR_POOL_ENABLED = true. BILLING_USAGE_ENABLED = true. BURSARY_AGREEMENT_ENABLED not set (OFF). SPONSOR_MOCK_DONATIONS_ENABLED not set (OFF; production also refuses to start with mock money against a real database).
- The offer-lapse job is live, daily at 09:00. The earlier "unscheduled" claim (TD-252) is out of date.
- record-verdict: 17 of 23 real calls took over 30 s in the last 30 days, maximum 51.9 s.
- reprocess-ic-vision runs hourly: median about 200 s, 5 runs hit the 300 s timeout.
- Release notes line 50 is stale (it says Next 14.2.0 and "1 critical and 5 high").
- Not known: how many cases were already awarded under the TD-465 fault (a count of STPM cases at RM3,000 with no start year is still to be taken, counts only).

## Ranked findings

Severity is the verifier's, which overrides the lens where they differ. "Not re-checked" means the lens rating stands because the item was low, register-only, or not about money. Size: S, M, L.

| # | id | claim | final severity | size | status |
|---|----|-------|----------------|------|--------|
| 1 | TD-465 | An STPM accept with unknown start year is auto-awarded RM3,000; the QC "absolute stop" (`award.py:58-66`) has no caller. | **high (money)** | S | Part 1 fixed on money-a (`b0bedd54`, in review). Part 2 open. |
| 2 | SEC-01 | Document record accepts any client storage path; same-org letters are guessable; Remove deletes any path. | medium now, high once agreements exist | S | Confirmed. Hotfix on sec-a (in progress). |
| 3 | SEC-10 | DRF 3.18.1 and pyjwt 2.14.0 have fixed advisories on the unauthenticated and auth paths. | medium (near high) | S | Confirmed. TD-516. |
| 4 | SEC-02 | `user_metadata.email_verified` (user-writable) decides the staff first-login link. | medium (conditional) | S | Code flaw confirmed; exploitable only if Confirm email is OFF. Hotfix on sec-a. |
| 5 | SP-01 | record-verdict makes two paid Gemini calls inline (org request 61). | medium (live harm) | M | Reproduced on live logs. TD-517. |
| 6 | SEC-04 | Partner CSV export: no audit line, no formula guard. | medium | S | Confirmed. TD-515. |
| 7 | SEC-18 / TD-467 | Uploads may overwrite (`x-upsert: true`); bucket has no type or size limit. SEC-07 folds in here. | medium | S | Confirmed. |
| 8 | SEC-15 / TD-506 (and CO-15) | Next 14.2.35 advisories; criticals unreachable here, DoS highs remain. | medium | M | Partly confirmed. Fix sprint 1. |
| 9 | CO-09 / TD-198 | No way to withdraw an award once out. | medium (money) | M | Confirmed. Owner decision. |
| 10 | SEC-17 / TD-501 | Reviewer invite takes no gift; NULL means every gift (inside one organisation only). | medium | M | Confirmed. Owner ruled: first fix after v3.1.0. |
| 11 | SEC-19 / TD-487 | A decline below AWAITING QC gets no QC check (API only; the cockpit sends only `contractual`). | medium (owner's call) | S | Confirmed. |
| 12 | SP-02 | reprocess-ic-vision runs near the 300 s limit. | medium | M | Confirmed. TD-518. |
| 13 | TD-459 | Usage meter misses Gemini "thinking" tokens (about 3-5x under-count); matters because BILLING_USAGE_ENABLED is on. | medium (money) | S | Confirmed. |
| 14 | SEC-16 | Pillow, pypdf and pillow-heif advisories on student uploads. | medium | M | Confirmed; already registered (TD-506). |
| 15 | CO-05 | Sponsor money is still a mock (TD-075) and not tied to the signed agreement (TD-142). | medium | L | Partly confirmed (see rejected). Owner or business items. |
| 16 | SP-03 / SP-04 | Document upload (p50 11.6 s, max 57 s) and assign (p50 about 13 s) do heavy work in the request. | medium | M | Confirmed. TD-519. |
| 17 | SP-05 to SP-07 | Interview submit, income coach GETs and applicant detail are slow. | medium | M | Not re-checked. |
| 18 | CO-01 | No real sign-in per role on a local stack; sandbox returns canned JSON. | medium | M | Facts confirmed. TD-521. |
| 19 | RD-01 | The income rule lives in about eleven places; web mirror unguarded. | medium | L | Partly confirmed; baseline out of date. TD-262. |
| 20 | RD-10 | Organisation-resolver helper has five copies (past its own trigger). | medium | S | Not re-checked. TD-412. |
| 21 | SEC-03 | Throttle key is client-settable; lifts anonymous limits only. | low | S | Confirmed. TD-514. |
| 22 | RD-02 / CO-02 / CO-03 | Debt index, roadmap and flag table are stale. | medium | S | TD-522. |
| 23 | CH-02 | Consolidation Review overdue; `wat_lint` FAILs. | medium | M | Process. |
| 24 | SP-08 / SP-12 | No minimum instance; build minutes high. | medium | S-M | Owner's call. TD-523. |
| 25 | SP-09 / CH-01 | Bundle headroom thin; ratchet FAIL. | medium | M | Accepted (see code health). |

The rest are listed in the lens sections below.

## Security lens

Verifier results first; items not listed there keep the lens rating and are marked.

| id | claim | final | note |
|----|-------|-------|------|
| SEC-01 | Any client storage path accepted at document record | medium (high later) | Fence missing at `views.py` ~1099; `scholar_money.own_path` exists unused. Hotfix sec-a. |
| SEC-02 | email_verified fallback to user metadata | medium (conditional) | `supabase_auth.py:156-157`; hotfix sec-a. |
| SEC-03 | Spoofable throttle key | low | `throttling.py:20-35`. Anonymous limits only. |
| SEC-04 | Partner CSV: no audit, no formula guard | medium | `views_admin.py:483-531`. |
| SEC-05 | One shared CRON_SECRET opens every job | low | Not re-checked. |
| SEC-06 | Django admin on the API host, no login throttle | low | Not re-checked. |
| SEC-07 | Upload type and size trust client values | low | Folded into SEC-18. |
| SEC-08 | Claim-code counter race | low | Spot-checked (`profile_claim.py:249-256`). |
| SEC-09 | Email address in a WARNING log | low | Spot-checked (`views.py:1418`). One-line fix. |
| SEC-10 | Dependency advisories (DRF, pyjwt, others) | medium | Own pip-audit reproduced. |
| SEC-11 | Public read policy on `partner_organisations` | low | Not re-checked; USING clause not inspected. |
| SEC-12 | Thin security headers | low | Not re-checked; not tested on the live response. |
| SEC-13 | Anonymous sign-ins skip the NRIC gate | low | Not re-checked; no harmful door found. |
| SEC-14 | 15 deny-all tables lack a service_role policy | low | Harmless today. |
| SEC-15 | Next.js advisories | medium | Same as CO-15. Criticals unreachable here. |
| SEC-16 | Pillow, pypdf, pillow-heif on uploads | medium | Confirmed. |
| SEC-17 | Reviewer invite NULL gift | medium | Confirmed. |
| SEC-18 | Upsert and bucket limits | medium | Confirmed. |
| SEC-19 | Decline below AWAITING QC | medium | Confirmed, owner's call. |
| SEC-20 | Known leftovers TD-488, 496, 497, 499, 503, 504; no role sandbox | low | Registered. |

Checked and fine: DRF denies by default; JWT checks pin algorithms and audience; production refuses an insecure SECRET_KEY and wildcard CORS; the Twilio webhook fails closed; cron and Vircle routes use `hmac.compare_digest`; student per-pk views are scoped to their owner; the secret scan of tracked files found only the public Supabase anon key; the Security Advisor shows no ERROR-level lints.

## Money and live-harm items (outside the security lens)

TD-465 (high), CO-09 (medium), TD-459 (medium), CO-05 (medium), SP-01 and SP-02 (medium, live). See the ranked table.

## Completeness lens

| id | claim | final | note |
|----|-------|-------|------|
| CO-01 | Local role sign-in gap | medium | Lens said high: a testing-tool gap, no harm on the live site. |
| CO-02 | `docs/roadmap.md` stale (last updated 2026-03-20, says v2.0) | medium | Not re-checked. |
| CO-03 | About 24 flags default OFF, no table of live values | medium | Not re-checked. |
| CO-04 | In-app signing (BURSARY_AGREEMENT_ENABLED) built but blocked | low-medium (counted medium) | Lens said high. The claimed register contradiction is rejected. Dark, with TD-347, TD-140 and TD-152 as real blockers. |
| CO-05 | Sponsor money is a mock | medium | See rejected. |
| CO-06 | Phone sign-in is a "coming soon" stub (TD-043) | medium | Not re-checked. |
| CO-07 | "Coming soon" screens (billing card, sponsor portal, trust hub, guide) | low | Not re-checked. |
| CO-08 | WhatsApp STOP inert until Twilio webhook set (TD-318) | medium | Owner action. Not re-checked. |
| CO-09 | No award withdrawal | medium (money) | Confirmed. |
| CO-10 | Document-reading gaps (corpus brief, S7 frozen, TD-114, TD-399) | medium | Not re-checked. |
| CO-11 | About 92 plan files, most with no Status line | medium | Not re-checked. |
| CO-12 | Vocabularies that are not yet a gate | medium | Not re-checked. |
| CO-13 | 25 owner-decision TDs waiting | medium | Not re-checked. |
| CO-14 | Debt "never walked in a browser" | low | Not re-checked. |
| CO-15 | Release leftovers | medium | Repeats SEC-15, SEC-16, SEC-17; merged. |
| CO-16 | Deprecated bank-details code still shipped | low | Not re-checked. |
| CO-17 | Old roadmap leftovers | low | Not re-checked. |

Clean: i18n has 0 missing and 0 extra keys; no TODO cluster; the sandbox safety test exists.

## Redundancy lens

| id | claim | final |
|----|-------|-------|
| RD-01 | Income rule in about eleven homes | medium (partly: the 2026-09-19 baseline is out of date; F1, F4, F5, F10 fixed) |
| RD-02 | Open Items Index says 137, real count 219 | medium |
| RD-03 | Two permission systems coexist | medium |
| RD-04 | Cross-app reach-ins both ways | medium |
| RD-05 | Logic imported sideways from the view layer | low |
| RD-06 | 41 web mirrors without a drift guard | medium |
| RD-07 | Two dead web files (`ScholarshipReferee.tsx`, `error-i18n.ts`) | low |
| RD-08 | API routes with no web caller | low |
| RD-09 | "Typed name equals actual name" in three copies | low |
| RD-10 | Organisation resolver in five copies | medium |
| RD-11 | Test-only or offline files in the API | low |

### Debt register triage

Register at the tag: 503 ids defined, 219 open by the project's counter. Verdicts: keep 174, close 1, merge 44. Only the items marked "code" were checked against the code; the rest are "no evidence to close".

- **Close:** TD-413 (the FAQ file is now 479 lines). TD-252: the scheduling half is done (live daily); only withdrawal remains, which is TD-198, so close TD-252 into TD-198.
- **Merge** (target stays open): 420, 367, 365, 368, 382, 348, 351 into TD-383; 179 into TD-262; 041 into TD-076; 117 into TD-116; 094, 097, 105, 108, 132, 170, 180, 183 into TD-091; 092, 112, 184, 196 into TD-070; 357, 358, 359 into TD-355; 339, 343 into TD-338; 384 into TD-414; 433 into TD-427; 464, 466, 469, 471, 472, 480, 489, 490 into TD-450; 493, 494, 495 into TD-492; 496, 498, 499 into TD-497; 451 into TD-452.
- **Keep, checked in code:** 321, 341, 346, 361, 387, 412 (escalate), 415, 444, 064, 084, 173, 043, 187 (weak, re-test), 212, and 058, 075, 140, 142, 152 (owner or outside party).
- **Schedule first:** TD-465, TD-459, TD-506, TD-501, TD-427.
- Closing entries and merging is the win here, not the open count, which will rise with the 12 new entries.

## Speed lens

| id | claim | final |
|----|-------|-------|
| SP-01 | record-verdict slow (inline Gemini) | medium (live harm); 17 of 23 over 30 s, max 51.9 s |
| SP-02 | reprocess-ic-vision near 300 s | medium |
| SP-03 | Document upload slow (p50 11.6 s, p95 27.2 s, max 57.4 s) | medium; all 201 calls succeeded |
| SP-04 | Assign slow (email inline, heavy reply) | medium |
| SP-05 | Interview submit, qc-decision, resolution-items slow | medium (not re-checked) |
| SP-06 | Income coach GETs call a model (p95 14-21 s) | medium (not re-checked) |
| SP-07 | Applicant detail p50 2.5 s, p95 5.1 s (query count hides round trips) | medium (not re-checked) |
| SP-08 | No minimum instances; heavy cold start | medium (owner's call) |
| SP-09 | Bundle headroom 0.4 to 1.2 kB | medium |
| SP-10 | Budget does not count layouts, CSS, lazy chunks (TD-304) | low |
| SP-11 | 33 scheduled jobs, 13 at hourly or */15 | low |
| SP-12 | Build minutes high (15-27 min, about 30 builds in 2.5 days) | medium |
| SP-13 | N+1 on mentor and pending cards (TD-500, TD-505) | low |
| SP-14 | 300 s timeout applies to the whole service | low |

All speed highs came down to medium: none of them failed requests. SP-01 stays at the top of the speed list because a real person on the other side was affected.

## Code-health lens

Readings this run against the last (bea7111, 2026-11-04): fix% 51 (was 50, WARN); hot#1 vision.py 32.4 (same); big files 13 (was 14); long functions 15 (same); dup 4; xapp 85 (was 83); supp 92 (was 91); skip 0; mirror 3; guard% 12; td_open 219 (was 203); unused 0; tsc 0; i18n ok; std FAIL (ratchet).

- **CH-01 (FAIL, accepted).** The bundle budgets loosened (/profile 193 to 195, /scholarship/application 206 to 209, /scholarship/apply 187 to 189, median 145 to 146.5 kB). The cause is the owner-approved Next 14.2.35 security patch, commit `442b21f4`. Accepted with that reason; the Next 15 upgrade re-measures.
- CH-02 (medium): Consolidation Review overdue; 14 pending small changes; `wat_lint` FAILs (20 code commits since 2026-10-28 neither sprint work nor logged). Also flags `1a6f8cd1` (request 50) as sprint-sized and `bf79bea6` (new module).
- CH-03 (medium): fix ratio 51%, third-plus consecutive WARN; by the accept-three-times rule this becomes a TD, not another accept.
- CH-04 (medium): vision.py is still the hotspot (14 fixes, 2316 lines); next are officerCockpit.ts 28.2, scholarship/views.py 22, verdict_engine.py 21.1.
- CH-05 (low): 13 files over 1000 lines. CH-06 (medium): 15 functions over 150 lines, worst `calculate_fit_score` 333 and `engine.check_eligibility` 294. CH-07 (low): duplicated function names in three homes.
- CH-08 (medium): 3 web mirrors with no drift test, all in `incomeWizard.ts`.
- CH-09 (low): cross-app coupling grew. CH-10 (low): suppressions 92. CH-11 (medium): debt up 203 to 219. CH-12 (low): register near-misses to tidy by eye.

## Rejected or merged findings

| claim | reason |
|-------|--------|
| TD-252 "lapse job unscheduled" (redundancy lens) | Out of date. The job is live, daily at 09:00 (`halatuju-lapse-expired-offers`). Only withdrawal remains (TD-198). |
| CO-04: register contradicts deployment.md | The lens misread which flag TD-347 calls live. TD-347 means `needs_parent_call`; the same entry says signing is OFF in production. |
| CO-05: mock money could be minted in production | Impossible by construction: production refuses to start without a real database, and mock mode needs "no managed database". |
| SP-01 "40% over 30 s" | The lens figure could not be reproduced in the verifier's sample. The lead's own 30-day query gave 17 of 23, which is used here. |
| CO-15 / SEC-15 "critical" | Next criticals are a Windows RCE (we run Linux) and Image Optimizer RCEs (switched off). Rated medium; CO-15 merged into SEC-15. |
| RD-01 "eleven homes, sixteen disagreements" | A 2026-09-19 baseline. Several fixed since; rated medium, not high. |
| SEC-07 | Folded into SEC-18. |
| CO-01, SP-01 to SP-03, RD-01 as "high" | Re-rated medium: no harm on the live site, or nothing failed. |

## For the owner to rank: fix-sprint candidates

Security and money first. Each is a proposal; none starts without the owner's order.

1. **Finish the sec-a hotfix** (SEC-01 and SEC-02; TD-512, TD-513). Owner action first: tell us the Supabase "Confirm email" setting.
2. **TD-465 part 2** (STPM unknown start year; wire the QC stop; count already-awarded cases, counts only). Part 1 is on money-a, in review.
3. **SEC-10 dependency bumps** (DRF 3.18.2, pyjwt 2.15.0; TD-516). Two version bumps, then the rest of the list.
4. **#61 async verdict** (TD-517): record the verdict at once; run refine and blurb in the background. Live harm.
5. **Next 15 upgrade** (TD-506, SEC-15): fix sprint 1; re-measures the bundle and clears CH-01.
6. **TD-501 reviewer-invite gift choice** (SEC-17): owner ruled it the first fix after v3.1.0.
7. **SEC-04 CSV audit and formula guard** (TD-515).
8. **SEC-18 / TD-467 upsert and bucket limits**: stop overwrite after read; add type and size limits to the bucket.
9. **CO-09 / TD-198 award withdraw**: owner decision needed on the withdrawal rule.
10. **SEC-19 / TD-487**: owner's call on the decline check below AWAITING QC.
11. **TD-459** usage meter under-count (billing is on).
12. **Slow paths** (TD-518, TD-519): reprocess batch size, upload, assign.
13. **Consolidation Review (CH-02)**: promote clusters (My activity, request 50/53 pairs), clear the `wat_lint` FAIL, and convert the repeating fix classes into guardrails.
14. **Register and docs tidy** (TD-522): regenerate the index, apply the 44 merges and the closure, refresh the roadmap and flag table.
15. **Lower priority:** TD-514, TD-520, TD-521 (role sandbox), TD-523 (cold start, owner's call on cost), RD-10 (org resolver, five copies).

## Owner rulings

(None yet. To be added at step 6.)

## Closing section

(To be written when the fix roadmap is done.)
