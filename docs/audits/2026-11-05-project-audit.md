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
10. The debt register reads 219 open, not the 137 its index claims. A code check of all 219 on 2026-11-05 gave: 143 open, 47 waiting on the owner, 12 fixed, 6 stale, 7 to merge, 4 unsure (Appendix A). The Consolidation Review is overdue (CH-02). The code-health FAIL (bundle ratchet) is accepted: it comes from the owner-approved Next 14.2.35 security patch (`442b21f4`).

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
| 15 | CO-05 | Sponsor money is still a mock (TD-075) and not tied to the signed agreement (TD-142). | medium | L | Partly confirmed (see rejected). Owner or business items. Status 2026-11-08 (A1.13): waits on the lawyer, the entity and TD-140; unchanged in A1.13. |
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

All 219 open items from before the audit were checked against the v3.1.0 code on 2026-11-05 by six read-only agents (one table each; no id appears twice). Verdicts: **OPEN 143, OWNER 47, FIXED 12, STALE 6, MERGE 7, UNSURE 4** (total 219). This replaces the earlier first pass (keep 174, close 1, merge 44): the sweep confirms 7 of the 44 proposed merges; the others were not confirmed and stay as they are until someone looks at them again. Every row is in Appendix A.

**Proposed to close (FIXED or STALE).** These are closed in the register only after a second check in fix sprint 0.

- TD-104 (FIXED): bursary slip upload now built
- TD-252 (FIXED): lapse job live; withdrawal is TD-198
- TD-326 (FIXED): Matric/Asasi/Poly results route built
- TD-382 (FIXED): assignment re-read under row lock
- TD-413 (FIXED): FAQ file now 479 lines
- TD-440 (FIXED): resend no longer resets password
- TD-470 (FIXED): process polyfill removed; entry closed
- TD-471 (FIXED): sandbox surfaces cover all four pages
- TD-473 (FIXED): pre-U letter now mismatches degree
- TD-479 (FIXED): flaky test fixed, entry closed
- TD-481 (FIXED): awaiting-QC decline now refused (400)
- TD-482 (FIXED): interview drafter now counted in QC
- TD-278 (STALE): roadmap already marks target unreachable
- TD-394 (STALE): owner ruled keep as is
- TD-405 (STALE): both parents now compulsory in form
- TD-427 (STALE): median headroom now 2.35 kB
- TD-433 (STALE): budget raised; 1.18 kB room
- TD-468 (STALE): quiz has Malay and Tamil sets

TD-252 and TD-198: the lapse job is live (daily 09:00), so TD-252 closes; only withdrawal remains, which is TD-198 (waiting on the owner). That note from the first pass still holds.

**Proposed merges** (source into target; the target stays open):

- TD-076 into TD-041
- TD-348 into TD-383
- TD-351 into TD-383
- TD-365 into TD-383
- TD-367 into TD-383
- TD-368 into TD-383
- TD-420 into TD-383

**Waiting on the owner (47).**

- TD-043: pay about RM12 a month for WhatsApp sign-in, or stay Google-only
- TD-066: keep or remove the temporary help box (which phone number)
- TD-068: give contractual declines their own email wording?
- TD-075: real sponsor money: needs lawyer review and payment account
- TD-091: Tamil review of sponsor landing
- TD-094: Tamil review of award/onboarding text
- TD-096: declare sponsor emails English-only, or add locales
- TD-097: Tamil review of reviewer-profile text
- TD-105: Tamil review of in-programme text
- TD-108: Tamil review of invite-a-friend text
- TD-114: paid re-read of old uploads to score them?
- TD-116: one paid re-read for old EPF (with TD-117)
- TD-117: same paid re-read as TD-116
- TD-128: widen the MBPK gate beyond physical disability?
- TD-130: ask Brevo for List-Help (code part done)
- TD-132: copy pass on sponsor portal EN/TA
- TD-133: trust hub needs registered entity, auditor, trustees
- TD-140: bursary agreement needs lawyer and legal entity
- TD-141: parent surety by link: Phase 2, rides TD-140
- TD-142: tie payments to signed agreement (waits on TD-140)
- TD-143: leave header-cropped birth cert, or floor at suspect
- TD-152: accepted interim; novation on incorporation
- TD-156: Google Admin Quick Access for Meet host
- TD-166: accepted: consent panel shows current wording
- TD-170: sign off two ms/ta brand-token strings
- TD-179: one attribution signal for partner students: which
- TD-180: copy pass on partner-email screen ms/ta
- TD-183: copy pass on sponsor admin ms/ta
- TD-184: walk the credit chain by hand
- TD-196: walk the sponsor-terms wizard (go-live test)
- TD-198: who may withdraw an award, and how
- TD-208: tighten DMARC and set Workspace DKIM
- TD-211: choose option a, b or c for the Reporting Date tick
- TD-215: write ms/ta donor pitch wording
- TD-225: supply a dark-mode logo
- TD-260: widen self-service reclaim, or build a support tool
- TD-262: yes/no on option 4 (add income_support_doc)
- TD-265: finance summary: programme column or header
- TD-318: set the Twilio webhook URL in the console
- TD-328: ruled; ends with first live agreement template
- TD-353: on hold until a second organisation joins
- TD-366: on hold until bursary signing is finalised
- TD-386: platform email templates: per-org overrides or super-only
- TD-399: OpenAI fallback parked ("not now"); revisit if outages recur
- TD-417: how supplier tax is spread onto tenant charges
- TD-472: where the console language control goes (menu or Profile)
- TD-503: who sees the wallet-credits and sponsors-to-vet cards

**Unsure (4).** What would settle each:

- TD-127: a look at the production data (PISMP descriptions)
- TD-129: a look at the production requirement data
- TD-395: run the entry SQL on production (count first)
- TD-478: a second sighting of the flake

**Open by area** (verdict OPEN only; areas grouped from the sweep's area column):

| Area | Open | High | Medium | Low |
|---|---|---|---|---|
| Sponsors, billing, money | 26 | 4 | 7 | 15 |
| Officer console and QC | 24 | 0 | 5 | 19 |
| Documents and vision | 22 | 0 | 9 | 13 |
| Staff, permissions, identity | 15 | 0 | 4 | 11 |
| Student application | 14 | 0 | 4 | 10 |
| Language and mobile | 12 | 0 | 0 | 12 |
| Infra, tests, tooling | 11 | 1 | 2 | 8 |
| Partners and requests | 10 | 0 | 1 | 9 |
| Eligibility and courses | 6 | 0 | 1 | 5 |
| Other | 3 | 0 | 0 | 3 |
| **Total** | 143 | 5 | 33 | 105 |

Schedule first: TD-465, TD-459, TD-506, TD-501, TD-383 (with TD-367). Closing and merging is the win here, not the open count, which will rise with the 12 new entries.

## Speed lens

| id | claim | final |
|----|-------|-------|
| SP-01 | record-verdict slow (inline Gemini) | medium (live harm); 17 of 23 over 30 s, max 51.9 s |
| SP-02 | reprocess-ic-vision near 300 s | medium |
| SP-03 | Document upload slow (p50 11.6 s, p95 27.2 s, max 57.4 s) | medium; all 201 calls succeeded |
| SP-04 | Assign slow (email inline, heavy reply) | medium |
| SP-05 | Interview submit, qc-decision, resolution-items slow | medium (fixed in code 2026-11-08, A2.4: 334/333/319 to 41/51/37 queries; prod p95 not re-measured) |
| SP-06 | Income coach GETs call a model (p95 14-21 s) | medium (fixed in code 2026-11-08, A2.4: cached by prompt hash, no model call on a repeat) |
| SP-07 | Applicant detail p50 2.5 s, p95 5.1 s (query count hides round trips) | medium (reduced 2026-11-08, A2.4: 38 to 33 queries; prod p95 not re-measured) |
| SP-08 | No minimum instances; heavy cold start | medium (owner's call) |
| SP-09 | Bundle headroom 0.4 to 1.2 kB | medium |
| SP-10 | Budget does not count layouts, CSS, lazy chunks (TD-304) | low |
| SP-11 | 33 scheduled jobs, 13 at hourly or */15 | low |
| SP-12 | Build minutes high (15-27 min, about 30 builds in 2.5 days) | medium |
| SP-13 | N+1 on mentor and pending cards (TD-500, TD-505) | low (fixed in code 2026-11-08, A2.4) |
| SP-14 | 300 s timeout applies to the whole service | low |

All speed highs came down to medium: none of them failed requests. SP-01 stays at the top of the speed list because a real person on the other side was affected.

## Code-health trend

| Reading | Last audit (bea7111, 2026-11-04) | This audit (v3.1.0) | Better / worse / same |
|---|---|---|---|
| fix% | 50 | 51 | worse |
| hot#1 | vision.py 32.4 | vision.py 32.4 | same |
| big files | 14 | 13 | better |
| long functions | 15 | 15 | same |
| dup | 4 | 4 | same |
| xapp | 83 | 85 | worse |
| supp | 91 | 92 | worse |
| skip | 0 | 0 | same |
| mirror | 3 | 3 | same |
| guard% | 11 | 12 | worse |
| td_open | 203 | 219 | worse |
| unused | 0 | 0 | same |
| tsc | 0 | 0 | same |
| i18n | ok | ok | same |
| std | ok | FAIL (ratchet) | worse |

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

Superseded on 2026-11-05 by the full fix roadmap, `docs/plans/2026-11-05-audit-fix-roadmap.md` (all readings targeted, every open TD placed). This short list is kept as the first ranking.

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
14. **Register and docs tidy** (TD-522): regenerate the index, re-check and apply the sweep's 12 fixed, 6 stale and 7 merge verdicts (Appendix A), refresh the roadmap and flag table.
15. **Lower priority:** TD-514, TD-520, TD-521 (role sandbox), TD-523 (cold start, owner's call on cost), RD-10 (org resolver, five copies).

## Owner rulings

- 2026-11-05: full TD sweep wanted (all 219 open items checked). Done; see Appendix A.
- 2026-11-05: the plan must improve every reading. The fix roadmap `docs/plans/2026-11-05-audit-fix-roadmap.md` is APPROVED. Wave 0 may start. Each deploy group needs its own yes. Owner wants an update at every sprint and wave.
- 2026-11-05: TD-066 (personal mobile number on the live site): remove the box. Done on branch td066; ships in G0.
- Owner decisions D1-D13 (roadmap section 3) are still open. None blocks Wave 0.

## Closing section

(To be written when the fix roadmap is done.)

## Appendix A: every open debt item (sweep 2026-11-05)

One row per item; verdicts copied from the six sweep tables. Evidence is shortened. TD-471 (batch 5 partly open, batch 6 fixed) is FIXED: the organisation index page is now a redirect and the programmes page is covered by `consoleM8Surfaces.tsx`. TD-472 (batch 5 owner, batch 6 open) is OWNER: the entry's fix is an owner decision on where the control goes.

| TD | Short title | Verdict | Evidence | Sev | Size | Moves | Area |
|---|---|---|---|---|---|---|---|
| TD-024 | Course name field is called course | OPEN | halatuju_api/apps/courses/models.py:64 course = models.CharField | low | L | none | eligibility engine |
| TD-041 | Settings page has no account options | OPEN | halatuju-web/src/app/settings/page.tsx: only language, theme, clear data, about (84 lines) | low | S | none | web settings |
| TD-043 | Phone/OTP login not built (Google only) | OWNER | web/src/app/login/page.tsx is now only a redirect to /; students sign in by Google only (lib/supabase.ts:46);… | - | - | - | auth |
| TD-058 | Prod lacks Django contenttypes/auth tables | OPEN | technical-debt.md:1380 status "MANAGED, not fixed"; migrations still applied by hand via MCP SQL | low | L | none | infra |
| TD-064 | Old is_super_admin kept beside role | OPEN | apps/courses/models_staff.py:162 field, :324 bridge, :294/:301 readers; admin.py:90 | low | M | none | staff permissions |
| TD-065 | Sponsor/admin screens lack component tests | OPEN | no test files in web/src/app/sponsor/login, register, pool/[id]; no DocumentHelpCoach test | low | M | guard | tests |
| TD-066 | TEMP help box with personal mobile live | OWNER | web/src/components/ScholarshipNextSteps.tsx:785,815 (TEMP tags); messages/en.json:1186 has 012-337 5709;… | - | - | - | application page |
| TD-068 | Contractual decline sends generic email | OWNER | apps/scholarship/emails/decline_mail.py:33 contractual falls back to generic decline; no reason field; same… | - | - | - | org requests / decline |
| TD-070 | Sponsor sign-in/vetting never click-tested | OPEN | CHANGELOG.md:24879 "Not click-tested"; no later live smoke recorded (verification gap, no code) | medium | S | none | sponsor |
| TD-074 | Pool detail keyed by raw id; no filters | OPEN | apps/scholarship/urls.py:289 sponsor/pool/<int:pk>/; part (b) leak scan already done | low | M | security | sponsor |
| TD-075 | Sponsor money still mock | OWNER | disbursement.py:94 reference='mock'; models/funding.py:15 mock donations; waits on lawyer review + payment… | - | - | - | billing / sponsor |
| TD-076 | Settings page thin | MERGE→TD-041 | same page; version half done (settings/page.tsx:67 appVersion()), account options still missing | - | - | - | web settings |
| TD-077 | Course names show bare # | OPEN | nothing in web/src strips or reads # in course names (only branding.ts:197, unrelated) | low | M | none | i18n / course display |
| TD-084 | Orphaned income fields + dead i18n | OPEN | earner_work_status / household_other_earners still in models/applications.py, serializers.py:593,736,… | low | L | none | income wizard |
| TD-091 | Sponsor landing Tamil first draft | OWNER | owner Tamil review of sponsorLanding in ta.json | - | - | - | i18n |
| TD-092 | Sponsor landing never walked in 3 languages | OPEN | no record of the click-through; verification gap | low | S | none | sponsor |
| TD-094 | Award/onboarding Tamil first draft | OWNER | owner Tamil review | - | - | - | i18n |
| TD-096 | Sponsor emails English only | OWNER | models/sponsors.py has no locale field; entry says declare English-only is the honest default; decision not… | - | - | - | sponsor emails |
| TD-097 | Reviewer-profile Tamil first draft | OWNER | owner Tamil review | - | - | - | i18n |
| TD-101 | No Donate-more / Withdraw-offer in sponsor portal | OPEN | no donate/withdraw UI anywhere in web/src; backend views exist; tied to TD-075 money | low | S | none | sponsor |
| TD-103 | CGPA typed, not read off slip | OPEN | no CGPA parsing in doc_parse*.py | low | L | none | vision/doc-recognition |
| TD-104 | Results form has no slip upload | FIXED | web/src/app/scholarship/bursary/page.tsx:97,171 slip File state + signed-URL upload (S4a) | - | - | - | in-programme |
| TD-105 | In-programme Tamil first draft | OWNER | owner Tamil review | - | - | - | i18n |
| TD-108 | Invite-a-friend Tamil first draft | OWNER | owner Tamil review | - | - | - | i18n |
| TD-111 | Anomaly flags not all routed to student questions | OPEN | check2_queries.py:36-48 CLARIFY_SPECS gained utility detectors (partial) but no coverage critic found | medium | M | guard | officer cockpit / check2 |
| TD-112 | Income route switch never click-tested | OPEN | no record of browser test; verification gap | low | S | none | income wizard |
| TD-114 | CERTAIN off unscored documents | OWNER | verdict half done (verdict_ladder._genuineness_unscored per register); remaining: old uploads not re-scored =… | - | - | - | vision/doc-recognition |
| TD-115 | No DB guard on document slot | OPEN | models/documents.py Meta (:156) has no UniqueConstraint on (application, doc_type, household_member) | medium | L | guard | vision/doc slots |
| TD-116 | Old EPF use rough estimate until re-read | OWNER | needs one paid re-read (with TD-117); fallback keeps outcomes correct | - | - | - | vision/doc-recognition |
| TD-117 | Old EPF uploads lack wrong-type check | OWNER | same paid re-read as TD-116 | - | - | - | vision/doc-recognition |
| TD-119 | Genuine docs wrongly flagged in test set | OPEN | register says 8 false-positive flags remain, explained not fixed; no later fix found | medium | M | guard | vision/doc-recognition |
| TD-121 | Eval scorecard ignores genuineness | OPEN | management/commands/eval_doc_recognition.py scores via doc_match_verdict only (eval/README.md:8) | low | M | guard | tests / eval |
| TD-124 | Contact messages email only | OPEN | only notify_contact_submissions.py cron + views.py intake; no admin messages page in web/src/app/admin | low | M | none | admin |
| TD-126 | Guide scheduling step no screenshots | OPEN | content/manual/role-reviewer.tsx:150-160 step has no img; public/reviewer-guide/scheduling-1..3-*.png exist… | low | S | none | docs / guide |
| TD-127 | Cloned PISMP descriptions | UNSURE | data lives in production DB; cannot prove from code | - | - | - | courses data |
| TD-128 | MBPK gate captures only physical disability | OWNER | engine.py:397-400 gates on student.disability only; broaden or not is an owner call | - | - | - | eligibility engine |
| TD-129 | SJKT PISMP extra BT language credit | UNSURE | requirement data in DB; harmless, needs production data look | - | - | - | courses data |
| TD-130 | Brevo unsubscribe on transactional mail | OWNER | Code shim done (emails/sending.py:61-74). Left: ask Brevo for List-Help | - | - | - | email/infra |
| TD-132 | Sponsor portal EN/TA copy unreviewed | OWNER | Owner copy pass; i18n guard test exists | - | - | - | i18n |
| TD-133 | Trust hub shows placeholders | OWNER | Needs registered entity, auditor, trustees | - | - | - | sponsor/trust |
| TD-140 | Bursary agreement needs lawyer + entity | OWNER | bursary.py:834 flag default OFF; legal gate | - | - | - | bursary agreement |
| TD-141 | Parent surety signs in-session only | OWNER | Phase 2 feature riding TD-140 (guarantor_method='link' unbuilt) | - | - | - | bursary agreement |
| TD-142 | Payments not tied to signed agreement | OWNER | Waits on TD-140 (register status 2026-09-30) | - | - | - | bursary/billing |
| TD-143 | Header-cropped birth cert scores not_type | OWNER | Owner's call (leave or floor at suspect); decisions.md:4515 | - | - | - | vision/doc-recognition |
| TD-152 | Agreement names personal donor until incorporation | OWNER | Accepted interim; novation on incorporation | - | - | - | bursary agreement |
| TD-155 | Partner Scholarship view not built | OPEN | navigation.ts has no partner scholarship row; no org-scoped bursary endpoint | low | M | none | scholarship views / partner |
| TD-156 | Meet "waiting for host" | OWNER | Needs Google Admin Quick Access; meeting.py:89-93 sets no accessType (optional hardening unbuilt) | - | - | - | infra/interviews |
| TD-166 | Consent panel shows current wording | OWNER | Accepted by owner; ScholarshipConsent.tsx:122-128 documents it | - | - | - | consent |
| TD-170 | Two ms/ta strings use brand token only | OWNER | Wording needs owner sign-off | - | - | - | i18n |
| TD-173 | HEIC request attachments not converted | OPEN | org_requests.py:57 allows .heic; conversion only in storage.py:266 for applicant docs | low | S | none | org requests |
| TD-174 | Email UsageEvent rows mostly org-NULL | OPEN | emails/shared.py:12-29 meters with source only; org from context else NULL; batch 3 left open | low | M | none | billing |
| TD-179 | Two attribution signals for partner students | OWNER | courses/views_admin.py:~164 still referred_by_org FK vs chip in partner_comms; needs owner ruling | - | - | - | scholarship/partner |
| TD-180 | Partner-email screen ms/ta draft | OWNER | Owner copy pass | - | - | - | i18n |
| TD-183 | Sponsor admin ms/ta draft | OWNER | Owner copy pass | - | - | - | i18n |
| TD-184 | Credit chain never walked by a human | OWNER | Owner smoke test; parked 2026-07-28 | - | - | - | sponsor |
| TD-185 | creditChain uses timestamps not status | OPEN | halatuju-web/src/lib/sponsorDetail.ts:50,59,66 done: !!…_at | low | S | guard | sponsor |
| TD-187 | Sidebar rail cannot scroll (chip) | OPEN | components/admin/Sidebar.tsx:208-212 no overflow by design; trigger (~20 rows) not reached | low | S | none | nav/IA |
| TD-190 | Sponsor tables sort/page client-side | OPEN | views_admin/sponsors.py:67 "full pagination deferred"; parked by owner | low | M | speed | sponsor |
| TD-192 | Sponsor vetting is a button | OPEN | models/sponsors.py:46 is_trusted default True; no identity/source-of-funds fields; decisions.md:13649 keeps… | high | L | security | sponsor |
| TD-196 | Sponsor-terms wizard not walked | OWNER | Owner go-live smoke test | - | - | - | sponsor |
| TD-198 | No admin route out of awarded | OWNER | Needs owner ruling on who may withdraw; sponsorship.py has only sponsor cool-off cancel (:708) | - | - | - | sponsor/money |
| TD-208 | Platform email in Spam | OWNER | SPF/DKIM/DMARC fine; left: DMARC tighten, Workspace DKIM | - | - | - | infra/email |
| TD-211 | Reporting Date tick has no cross-check | OWNER | fieldVerification.ts:166 sets tick from letter alone; options a/b/c await owner | - | - | - | officer cockpit |
| TD-212 | PartnerEmailTemplate misnamed | OPEN | models/comms_templates.py:15 still "partner" holds student/reviewer/invite kinds | low | M | none | org comms |
| TD-215 | Donor pitch English-only | OWNER | Needs owner-written ms/ta wording | - | - | - | i18n/sponsor |
| TD-216 | Interviewer label stamped by first click | OPEN | views_admin/interviews.py:87,181 _is_authoring; overall_note shared field (models/interviews.py:94); box… | medium | M | none | interviews |
| TD-225 | Logo vanishes in dark mode | OWNER | BrandLogo.tsx:24 single raster; needs artwork | - | - | - | brand/UI |
| TD-226 | Two cohort settings read by nothing | OPEN | models/programmes.py:378,384; no readers outside migrations | low | S | none | scholarship cohort |
| TD-227 | Unassigned rejection, no reason | OPEN | Register: no guardrail built; CHANGELOG lists not fixed | medium | S | none | scholarship lifecycle |
| TD-228 | ORGANISATION crumb filters little | OPEN | Requests narrowed (?org=); Sponsors/Sources still not; trigger (2nd org) not fired | low | M | none | console shell |
| TD-234 | 13 repair commands lack a door | OPEN | tests/test_repair_commands_have_a_door.py:42-56 NO_DOOR ledger still holds them | medium | M | none | infra/ops |
| TD-238 | Merchant count not watched | OPEN | spend_category.py:381-382 prints to stdout only; partly: model calls/tokens added; no alert | low | S | none | spending |
| TD-243 | AI reliability blends engine versions | OPEN | audit.py engine_versions caveat only; rate not split per version | low | M | none | audit/AI |
| TD-245 | "Spent nothing" vs "wallet not in export" | OPEN | spend_report.py:304,367 unseen_students; unmatched rows still discarded | medium | M | money | spending |
| TD-247 | Supplier bills reach ledger only by hand | OPEN | No cron door for import_invoices / sync_gcp_costs (absent from api/apps/scholarship/cron_health.py:35-70);… | low | M | none | billing |
| TD-252 | Unanswered award stays open for ever | FIXED | Lapse job scheduled daily 09:00 MYT (cron_health.py:54; register Status 2026-10-01); close card built by… | - | - | - | sponsor/awards |
| TD-260 | No verified contact: cannot reclaim account | OWNER | profile_claim.py:156-179 claim_channels still verified-only; no admin relink door. Owner picks widen… | - | - | - | identity/claims |
| TD-262 | Income rule: option 4 ruling outstanding | OWNER | Register status: only option 4 (add income_support_doc) + F8/W1 stand; owner yes/no needed (decisions.md 4515… | - | - | - | income wizard / eligibility |
| TD-265 | Finance summary sends unused programme column | OWNER | web/src/lib/admin-api/payments.ts:103-120 interface lacks programme; design call (column vs header) | - | - | - | finance/payments |
| TD-278 | Unreachable xapp import target on roadmap | STALE | docs/plans/archive/2026-09-18-code-health-roadmap.md:921-922 already annotates the target as unreachable; line 954… | - | - | - | code-health docs |
| TD-283 | Two central files exactly at size limit | OPEN | api/code-standards.json:637 serializers_admin.py 1006 (+20 allowance = 1026); file is 1026 lines.… | low | M | big | scholarship serializers/models |
| TD-318 | WhatsApp STOP needs Twilio console webhook | OWNER | Webhook built (api/apps/scholarship/urls.py:224); owner must set URL in Twilio console | - | - | - | comms/WhatsApp |
| TD-321 | Page images served at full size (no sharp) | OPEN | web/next.config.js:15 images: { unoptimized: true }; no sharp in package.json (fix waits on Next 15 upgrade) | low | S | speed | infra/web |
| TD-326 | Results page only SPM/STPM; Matric/Asasi/Poly | FIXED | Third results route S2a/S2b: CHANGELOG.md:4971, 5050; api/apps/courses/exam_questions.py:121-151 results_held… | - | - | - | eligibility / results |
| TD-328 | No-template gift pays default schedule | OWNER | api/apps/scholarship/default_schedule.py still used by payments.py:122; ruled behaviour, ends on first live… | - | - | - | billing/payments |
| TD-336 | Overview pools money for org-less super | OPEN | api/apps/scholarship/views_admin/overview.py:73-82: admin.is_super -> ALL_ORGS, no… | low | S | security | officer cockpit / overview |
| TD-338 | One programme, two open cohorts: dup choice, 409 | OPEN | api/apps/scholarship/services/intake.py:108-121 raises ambiguity per cohort; views.py:110-127… | low | M | none | apply intake |
| TD-339 | Choices drop inactive-programme rounds, resolver counts them | OPEN | services/intake.py:108 bare path filters no programme__is_active; views.py:122 _open_round_choices does | low | S | none | apply intake |
| TD-341 | ScholarshipBanner reads applications[0] | OPEN | web/src/components/ScholarshipBanner.tsx:28 | low | S | none | student scholarship UI |
| TD-342 | Abandoned Google sign-in returns to old gift | OPEN | web/src/components/AuthGateModal.tsx:258-262 writes pending action unstamped; only cleared at :209/:319;… | low | S | none | apply / auth |
| TD-343 | Intake failure: form names no gift, submits no code | OPEN | web/src/lib/useApplyGift.ts:163 .catch(() => setSettled(true)) | low | S | none | apply form |
| TD-345 | No local signed-in student smoke path | OPEN | Only seed_local_console (console); api/CLAUDE.md:139, docs/testing.md:10; no student recipe | low | M | none | tests/tooling |
| TD-346 | "More than one application" message says "open" | OPEN | web/src/messages/en.json:1998-2001 ("applications open"); ms/ta copies too | low | S | none | i18n |
| TD-347 | Sign-accept deadline lapses during parent call | OPEN | Owner ruled (decisions.md:3744) re-arm on call, not built: arm_sign_deadline only called from… | high | M | money | bursary signing |
| TD-348 | Two rounds submit at once pass in-play check | MERGE→TD-383 | Read-then-write, no lock; promoted into TD-383 (technical-debt.md:145; consolidation-log.md:260) | - | - | - | apply / concurrency |
| TD-350 | Embargoed decline: uploads 403 while shown profile_complete | OPEN | api/apps/scholarship/views.py:815-819 _current_application filters raw status, ignores decline embargo mask | low | S | fix% | student docs / embargo |
| TD-351 | Same-round double submit answers 500 | MERGE→TD-383 | api/apps/scholarship/views.py:302 create_application with no IntegrityError handling anywhere in… | - | - | - | apply / concurrency |
| TD-353 | Two-organisation applications blocked until M2-M4 | OWNER | Owner ruling 2026-10-06: ON HOLD until a second organisation joins (technical-debt.md:110) | - | - | - | multi-programme |
| TD-354 | Closed card offers "See programmes" when none open | OPEN | web/src/app/scholarship/application/page.tsx:175-185 link shown unconditionally; register says route now has… | low | S | none | student scholarship UI |
| TD-355 | Three decision emails sent after status visible, no retry | OPEN | api/apps/scholarship/services/decline.py:273 _send_decline_for result ignored in org_admin_reject (plus… | medium | M | fix% | decisions / emails |
| TD-356 | cancel_reopen turns any reopened interviewing into interviewed | OPEN | api/apps/scholarship/reopen.py:203-205 | low | M | fix% | officer cockpit / reopen |
| TD-357 | Failed decline send retried for ever | OPEN | services/decline.py:418-421 returns False, logs ERROR every cron run; no attempt cap | low | S | fix% | decisions / emails |
| TD-358 | Decline with no email released silently | OPEN | services/decline.py:415-417 only a logger.warning; no officer surface | medium | S | fix% | decisions / emails |
| TD-359 | Decline stamp lost if DB fails after Brevo accepts | OPEN | services/decline.py:441-445 send inside transaction.atomic(), stamp saved in same txn | low | M | fix% | decisions / emails |
| TD-361 | 17 files over 1000 lines (views.py, officerCockpit.ts) | OPEN | api/apps/scholarship/views.py = 2441 lines; web/src/lib/officerCockpit.ts = 1620; 13 non-test source files… | low | L | big | scholarship views / cockpit |
| TD-362 | Web mirror guard reads only src/lib and keyword comments | OPEN | web/src/lib/__tests__/codeStandards.test.ts:347, :504 (relpath.startsWith('src/lib/')) | low | M | mirror | tests / web mirrors |
| TD-363 | Closed-from status only in audit log line | OPEN | api/apps/scholarship/closure.py:209, :263 (log only; no DB field) | low | S | none | officer cockpit / closure |
| TD-365 | Close and sponsor fund can race | MERGE→TD-383 | fund_student unlocked; named in TD-383 (technical-debt.md:145) | - | - | - | sponsor / concurrency |
| TD-366 | Awarded student who stops answering cannot be released | OWNER | Owner ruling 2026-10-06: ON HOLD until bursary signing finalised; closure.py:82 refuses with "owner decision" | - | - | - | awards / closure |
| TD-367 | Payment run can pay a CLOSED student | MERGE→TD-383 | api/apps/scholarship/payments.py:495-535 complete never re-reads app status (PAYABLE_STATUSES only at maker… | - | - | - | payments |
| TD-368 | Interview times proposed/booked on finished case | MERGE→TD-383 | api/apps/scholarship/scheduling.py:288-318 propose_slots, :424-440 book_slot check no status | - | - | - | interviews / concurrency |
| TD-370 | Query-reminder dry run uses wrong clock | OPEN | management/commands/send_query_reminders.py:53 still tests elapsed-since-submit; live sweep… | low | S | none | org requests / queries |
| TD-378 | No cockpit button to re-verify IC at QC | OPEN | view.tsx:560 only calls verify-accept from the Recommend path; no AWAITING-QC action; decisions.md:17247… | low | S | none | officer cockpit |
| TD-382 | Role switch to Finance races assignment | FIXED | services/assignment.py:225-231 re-reads reviewer under row lock (_locked) and re-checks _can_review; code… | - | - | - | officer cockpit |
| TD-383 | Writers trust a status read earlier (choke-point) | OPEN | No choke-point helper exists. payments.py:495-540 complete never re-reads app status (TD-367);… | high | L | money | scholarship money / lifecycle |
| TD-384 | Private _staff_target_manageable imported across apps | OPEN | scholarship/staff_tables_admin.py:86 imports it from courses.views_admin (the named staff.py no longer does,… | low | S | xapp | staff lifecycle |
| TD-385 | fix% counts review-round fixes as field fixes | OPEN | Settings/_tools/code_health.py has no read of consolidation-log SHAs or review: prefix (only a comment at… | low | S | fix% | tooling (workspace) |
| TD-386 | Cross-organisation seams (templates, filters) | OWNER | (a)(b) done (CHANGELOG:5586). (c) platform-wide PartnerEmailTemplate editable by any org admin: needs owner… | - | - | - | sources / multi-tenant |
| TD-387 | Referral partners have no mark/unmark screen | OPEN | API exists (views_referral_partners.py) but app/admin/partners/page.tsx lists partner admins only… | low | S | none | sources / referrals |
| TD-388 | Hydration mismatch with stored ms/ta locale | OPEN | onboarding/grades/page.tsx:61,176,323 and settings/page.tsx:71 render locale; lib/i18n.tsx:163 initialiser… | low | S | none | i18n |
| TD-389 | Admin slice stays required after leaving console | OPEN | lib/messages.ts:211 requireSlice only adds to required, nothing releases; lib/messagesAdmin.ts:32 registers… | low | S | speed | i18n |
| TD-393 | Outage re-upload stays staged, never re-judged | OPEN | views.py:1251-1269 judge+promote still inline; services/read_retry.py:70-76 sweep selects live docs only… | medium | M | none | vision / doc-recognition |
| TD-394 | Deferred EPF/support letter not income evidence | STALE | Owner ruling 2026-10-25 "keep as is (option A)" recorded in the entry: money gate never passes on an unread… | - | - | - | income wizard / vision |
| TD-395 | Pre-fix Vision-outage rows left unreadable | UNSURE | Data-only clean-up in production DB via the entry's SQL; no production access allowed, no code to check | - | - | - | vision / doc-recognition |
| TD-396 | Deferred offer read: Pathway review has no reason line | OPEN | offer_not_read_yet appears nowhere in api or web src (grep nil across both) | low | S | none | officer cockpit / i18n |
| TD-397 | Check-2 hold stays frozen after sweep gives up | OPEN | read_errors.py:130-136 deferred_by_us ignores service_retry_until; check2_deferred.py:34-60 never checks the… | medium | S | none | Check 2 / vision |
| TD-398 | One deferred letter delays other live letter | OPEN | check2_deferred.py:56-60 holds if ANY live copy of the type is deferred; no "resolve on the live one" | low | S | none | Check 2 |
| TD-399 | OpenAI fallback for document reads | OWNER | Parked 2026-10-28 by owner ruling "No, not now" (privacy/DPA); revisit only if Gemini outages recur | - | - | - | vision / doc-recognition |
| TD-400 | Minor's consent checked against half-read parent IC | OPEN | parent_ic_service_down appears nowhere; ConsentView and bursary still answer mismatch on a deferred card | low | S | none | consent / identity |
| TD-405 | Living parent left off family form | STALE | services/completeness.py:170-193 _family_done makes both parents' occupation compulsory (name unless… | - | - | - | income wizard / STR |
| TD-406 | "Not checked" offer hold never clears | OPEN | resolution.py:531-534 sets hold via hold_for_officer; nothing on the upload path clears needs_officer_eye… | low | S | none | offers / Action Centre |
| TD-412 | Org-resolver helper copied across views | OPEN | _organisation_for still copied: views_admin/theme.py:81, org_config.py:57, overview.py:126; _org copies in… | low | S | dup | org settings / billing |
| TD-413 | FAQ one line from size limit | FIXED | content/manual/faq.tsx is 479 lines; reviewer FAQ already split to faq-reviewer.tsx | - | - | - | docs / manual |
| TD-414 | Scholarship/reports reach into course results rules | OPEN | No apps/courses/results_rules.py; 34 direct exam_questions imports in reports + scholarship | low | S | xapp | eligibility engine / reports |
| TD-415 | Cockpit test raises query at refused stage | OPEN | view.actions.test.tsx:163-165 still renders stage 'shortlisted'; fixture test/adminApplicationDetail.ts… | low | S | guard | tests |
| TD-417 | Supplier tax pooled onto tenant charge | OWNER | platform_cost.py:421-447 still spreads whole tax pool pro-rata; entry says changing it changes what a… | - | - | - | billing |
| TD-420 | Tranche release reads hold on a copy, no lock | MERGE→TD-383 | disbursement.py:106 is_on_hold on the view's row, no lock; entry itself says fold into TD-383 | - | - | - | scholarship money |
| TD-421 | IC typed in admin search lands in request logs | OPEN | views_admin/applications.py:102 request.GET.get('q'), scholars.py:100 search still in query string; no… | medium | S | security | officer cockpit / PII |
| TD-422 | Busy-meter guard is not per-tenant | OPEN | metered_usage.py:148-162 counts this org's events but metered_rows(period_month) is month-wide; latent until… | medium | S | money | billing |
| TD-423 | Failed receipt email only re-sendable by hand | OPEN | views_admin/invoices.py:294-299 actions are send/void/receipt only; email_receipt called only on record… | low | S | none | billing |
| TD-424 | Two date formats (owner ISO vs tenant day-first) | OPEN | InvoicePaymentPanel.tsx:116 placeholder "YYYY-MM-DD" for owner boxes; tenant box uses isoFromDayFirst (:59).… | low | S | none | billing |
| TD-425 | Skipped month strands a correction | OPEN | charge_adjustments.py:23 corrections_for matches exact period_month; no readiness warning or carried-forward… | medium | S | money | billing |
| TD-426 | hoursAnalysisId and closing_report duplicate rule | OPEN | web lib/requestStatus.ts:347 still picks the analysis; API serves no id; guard is hoursAnalysisDrift.test.ts | low | S | mirror | org requests |
| TD-427 | Median bundle 0.5 kB headroom | STALE | code-standards.json:230 median line 146.5; CHANGELOG:24 reads 144.147 kB (2.35 kB room). Original condition… | - | - | - | infra / bundle |
| TD-428 | Verification mail bare send_mail, unmetered | OPEN | courses/views.py:1369 from django.core.mail import send_mail in SendVerificationView | low | S | money | billing / emails |
| TD-429 | Signatures record proxy IP | OPEN | scholarship/views.py:543,624,2040,2414 all request.META.get('REMOTE_ADDR'); no signer_ip use in views.py | low | S | security | consent / sponsor |
| TD-430 | Weekly partner email counts cool-off decline as Rejected | OPEN | partner_comms.py:316-330 stage_counts tallies raw status | medium | S | none | sources / referrals |
| TD-431 | Sources Edit lock bypass by revoke + re-invite | OPEN | source_invite.py:83-87 has_joined is a live active-user count, not an "ever joined" stamp; accepted risk per… | low | S | security | sources |
| TD-432 | Source users have no Guide/FAQ | OPEN | web/src/lib/navigation.ts:310-315 guide and faq roles omit source_partner | low | S | none | org requests / sources |
| TD-433 | /scholarship/application near first-load line | STALE | web/code-standards.json:228 line is now 209 (build 207.82, 1.18 kB room) after owner-approved raise TD-506;… | - | - | - | infra / bundle |
| TD-434 | TVET pathway map first-category-wins | OPEN | API/apps/courses/apps.py:194-200 first category wins, fallback 'tvet'; test_tvet_doors.py:50 checks only the… | low | S | guard | eligibility engine / courses |
| TD-435 | Reviewer w/o review held on Profile | OPEN | API/apps/scholarship/reviewer_onboarding.py:42 gate is still the role only, no check of the review permission | low | S | none | officer cockpit / profile |
| TD-437 | Source Organisation card has no Website | OPEN | API/apps/scholarship/models/sources.py ReferralSource has no website column | low | S | none | org requests / sources |
| TD-438 | Header photo link expires in open tab | OPEN | web/src/components/admin/StaffAvatar.tsx:29 onError only sets broken, no refetch of admin/me | low | S | none | officer console / profile |
| TD-440 | Staff Resend resets own-login password | FIXED | API/apps/courses/staff_reinvite.py:61 _chose_own_password, :167 reissue_credential guard; views_staff.py:383… | - | - | - | staff invitations |
| TD-441 | Admin role on student/sponsor login side effects | OPEN | API/halatuju/middleware/supabase_auth.py:88 alias ignored for any PartnerAdmin;… | medium | M | none | identity / staff invitations |
| TD-442 | QC reject can leave case reopened | OPEN | API/apps/scholarship/views_admin/verdict.py:429-442 reopen_decision commits, then admin_reject may 400; no… | medium | S | none | officer cockpit / QC |
| TD-443 | staff_footprint misses most history | OPEN | API/apps/scholarship/staff_footprint.py:55-77 only payment runs, benefactors vetted,… | medium | M | none | staff lifecycle / identity |
| TD-444 | Staff invitations never record invited_by | OPEN | API/apps/courses/views_admin.py:225 reads request._inviting_admin; nothing sets it | low | S | none | staff invitations |
| TD-447 | Offer confirm keeps hostel line on stale course | OPEN | API/apps/scholarship/services/confirmation.py:408 letter_place(cid from stored pick) before re-pin at :245 | low | S | none | offer reader / confirmation |
| TD-448 | Bumi realign waits for re-read | OPEN | API/apps/scholarship/services/offer_sync.py:246 realign only inside autofill; no call from the genuineness… | low | S | none | offer reader |
| TD-449 | Offer check queries outside query budget | OPEN | API/apps/scholarship/tests/test_query_budgets.py has no offer-letter fixture | low | S | guard | tests / offer reader |
| TD-450 | M1 overlay and guard loose ends | OPEN | no shared Escape/overlay stack in web/src; admin drawer, mobile-check URL compare and guards not changed | low | S | guard | mobile / overlays |
| TD-451 | Short campus line crosses institution type | OPEN | API/apps/scholarship/offer_course_match.py:321 CampusReader has no type-prefix (KK/POLY) filter | low | S | none | offer reader |
| TD-452 | Hand-written town-word list | OPEN | API/apps/scholarship/offer_course_match.py:288 _TOWN_WORDS still hand-written | low | S | none | offer reader |
| TD-453 | Adopt hoverOnlyWhenSupported | OPEN | web/tailwind.config.ts has no future block | low | S | none | mobile / Tailwind |
| TD-454 | Google user w/o NRIC sees signed-out header | OPEN | web/src/components/AppHeader.tsx:54,92 keyed off isAuthenticated only | low | S | none | student header / auth |
| TD-455 | Saved toasts English-only | OPEN | web/src/app/saved/page.tsx:80,84,108 literal English showToast | low | S | none | i18n |
| TD-456 | Course pages/cards English labels, 9-11 px text | OPEN | web/src/app/course/[id]/page.tsx:114,165 English labels; web/src/components/CourseCard.tsx:221-222,248,262… | low | M | none | i18n / mobile |
| TD-457 | Compare sticky row assumes header height | OPEN | web/src/components/saved/SavedCompare.tsx:143 top-[calc(4.25rem+...)], no --header-height variable | low | S | none | mobile / saved |
| TD-458 | Shared phone leftovers after session end | OPEN | no pageshow/persisted handler in web/src; grades/profile localStorage still not owner-tagged (form half… | medium | M | security | auth / shared phone |
| TD-459 | Gemini meter omits thinking tokens | OPEN | API/apps/scholarship/usage.py:112-124 gemini_tokens returns prompt and candidates only; thoughts_token_count… | medium | S | money | billing / usage meter |
| TD-460 | Income wizard writes on open; silent save failure | OPEN | web/src/components/ScholarshipDocuments/IncomeWizard.tsx:155-158,180-182 failures swallowed ("soft"); mount… | medium | S | money | income wizard |
| TD-461 | Step wizard still 10 px icon tab bar | OPEN | web/src/components/ScholarshipNextSteps.tsx:827 text-[10px] tab labels | low | M | none | mobile / scholarship student |
| TD-462 | Bank-statement upload no early refusal | OPEN | web/src/components/scholarship/PostAwardTasks.tsx has no uploadRefusal call | low | S | none | scholarship student |
| TD-463 | Award payment schedule in English | OPEN | API/apps/scholarship/contracts.py:996-1005 schedule_summary_text ignores locale, fixed English text; used at… | low | S | none | i18n / award page |
| TD-464 | M4b: 36 px selects; mobile-check widest in fixed bar | OPEN | part 1 closed on phones (web/src/components/LanguageSelector.tsx:64, ThemeSelector.tsx:58 max-md:min-h-11;… | low | S | none | mobile / mobile-check |
| TD-465 | Course-start year sets award alone; QC/payments read reporting_date | OPEN | API/apps/scholarship/award.py:58 course_start_unknown has no non-test caller; award.py:84-100 amount from… | high | M | money | scholarship award / QC |
| TD-466 | M4c leftovers: sandbox 16 px gutter, grade picker | OPEN | web/src/app/sandbox/layout.sandbox.tsx:69 wraps in max-w-6xl px-4;… | low | S | none | mobile / sandbox |
| TD-467 | Private bucket no mime/size limit; upsert signing | OPEN | no allowed_mime_types/file_size_limit anywhere in repo; web/src/lib/api/documents.ts:369 and… | medium | M | security | storage / uploads |
| TD-468 | Quiz questions English in Tamil/Malay | STALE | API/apps/courses/quiz_data.py:16,116,216 hold en/bm/ta sets; web/src/app/quiz/page.tsx:47 maps ms to bm and… | - | - | - | i18n |
| TD-469 | M5: sponsor desktop has no language control | OPEN | LanguageSelector not used in sponsor portal; web/src/app/sponsor/(portal)/account/page.tsx only (phone);… | low | S | none | sponsor / i18n |
| TD-470 | /scholarship/apply near first-load line | FIXED | entry CLOSED 2026-11-03 (process polyfill removed, next.config.js defines); code-standards.json TD-470 note | - | - | - | infra / bundle |
| TD-471 | Four console pages no sandbox surface | FIXED | web/src/sandbox/consoleM8Surfaces.tsx; /admin/organisation index is a redirect, programmes page covered | low | S | guard | mobile-check / console |
| TD-472 | Console has no language control | OWNER | web/src/components/admin/AppShell.tsx has ThemeSegments only; entry says decision where to put it (account… | - | - | - | i18n / console |
| TD-473 | Pre-U letter ticks Pathway match on degree pick | FIXED | apps/scholarship/pathway_match.py:109 pre_u_letter_on_tertiary_pick; entry "Resolved 2026-11-04";… | - | - | - | vision/doc-recognition |
| TD-474 | STPM school then one-word town line joined | OPEN | apps/scholarship/offer_parse.py:207-218 _NOT_WRAP has address words and states only, no town list | low | S | none | vision/doc-recognition |
| TD-475 | Wallet credits still read finance ROLE | OPEN | apps/scholarship/payments_chain.py:104-118 credit_check_required filters role='finance'; used by… | medium | S | money | billing / permissions |
| TD-476 | Reopened case can strand ex-reviewer | OPEN | apps/scholarship/reopen.py:100-125 reopen_decision never checks the assignee still holds review | low | S | none | officer cockpit / permissions |
| TD-477 | Cockpit to adopt shared Prev/Next hook | OPEN | app/admin/scholarship/page.tsx:240 and [id]/view.tsx:179 still use halatuju_admin_scholarship_nav; no… | low | S | dup | officer cockpit |
| TD-478 | Doc-snapshot subtest flaked once | UNSURE | test_document_snapshot.py:304 exists; single sighting, no repro; entry itself waits for 2nd sighting | - | - | - | tests |
| TD-479 | page.gift.test flaked in a build | FIXED | Entry closed 2026-11-03 by 159e824f (test waits for prefill) | - | - | - | tests |
| TD-480 | M6b leftovers: native confirms, hover name | OPEN | app/admin/scholarship/[id]/view.tsx:402,436,463,469 window.confirm; view/CockpitHeader.tsx:114 hover-only… | low | S | std | officer cockpit / mobile |
| TD-481 | Awaiting-QC case declined past QC gate | FIXED | views_admin/applications.py:386-390 returns 400 awaiting_qc; entry CLOSED 2026-11-04 | - | - | - | officer cockpit / QC |
| TD-482 | Interview draft author not remembered | FIXED | qc_separation.py:46-47 REVIEW_VERBS includes interview_drafted | - | - | - | officer cockpit / QC |
| TD-483 | QC panel shows for a QC server refuses | OPEN | web view/QcPanel.tsx:45 hides only for current assignee; view.tsx:694 maps only self_verdict_qc_forbidden; no… | low | S | none | officer cockpit / QC |
| TD-484 | Delete and re-invite escapes QC separation | OPEN | apps/scholarship/staff_footprint.py counts assigned_to, slots, interviews, email stamps; no AssignmentEvent… | medium | S | security | officer cockpit / QC |
| TD-485 | Failed activity write drops QC evidence | OPEN | qc_separation.py:46 reads StaffActivity verbs only; staff_activity.record is best-effort by contract | low | S | none | officer cockpit / QC |
| TD-486 | Super cancel-reopen lands declined case at recommended | OPEN | reopen.py:206-216 infers origin from current status; verdict.py:256-275 submit-decline sets interviewed… | medium | S | security | officer cockpit / QC |
| TD-487 | /reject/ before AWAITING QC has no second check | OPEN | views_admin/applications.py:386 refuses only when status == 'interviewed'; interviewing/shortlisted still… | medium | S | security | officer cockpit / QC (owner's call) |
| TD-488 | Org admin can close an AWAITING-QC case | OPEN | views_admin/lifecycle.py:143-160 + closure.py:41 interviewed in closeable list; no qc_separation check | low | S | security | officer cockpit / QC (owner's call) |
| TD-489 | Mentor screens draw white cards on phone | OPEN | components/mentor/MyStudents.tsx and MyStudentFile.tsx: 0 uses of PHONE_SECTION / PHONE_CARD_XL | low | S | std | mobile / mentor (owner: later) |
| TD-490 | Overview charts paint desktop box first | OPEN | components/admin/charts/Charts.tsx:43 usePhoneWidth in useChartBox | low | S | std | mobile / overview |
| TD-491 | Scanned multi-page offer scored on page 1 only | OPEN | vision.py:1047 _pdf_first_page_png for scanned PDFs; roadmap still lists "Open: TD-491..495" (offer… | medium | M | none | vision/doc-recognition |
| TD-492 | Two-word non-institution line above closed-list name | OPEN | genuineness/offer_rulings.py:310 len(ln.split()) <= 2 and not _ORG_RE still passes short lines | medium | S | none | vision/doc-recognition |
| TD-493 | Agency lift misses private name w/o org word | OPEN | genuineness/offer_agency.py:329 closed_world_blocker; gap pinned in tests per entry, no capitalised-name test… | medium | M | none | vision/doc-recognition |
| TD-494 | Descriptor excuse can hide company name | OPEN | genuineness/offer_agency.py:436 _after_descriptor unchanged; pinned gap | medium | S | none | vision/doc-recognition |
| TD-495 | Kolej Kediaman / IKM1 line stops agency lift | OPEN | offer_agency.py has no "Kediaman" / campus-facility allow list (grep nil in that file) | low | S | none | vision/doc-recognition |
| TD-496 | Graduation-messages list opens by role label | OPEN | views_admin/graduation.py:31 admin.role in ('reviewer','admin'); no web caller found (only sponsor endpoint… | low | S | none | permissions |
| TD-497 | Four doors still on union doors | OPEN | courses/views_staff.py:421 may_do_admin_work; mentor_invite.py:99; views_admin/org_emails.py:338;… | medium | M | guard | permissions / money |
| TD-498 | Converted doors ask .edit key for reading | OPEN | announcements.py:55, development.py:74 and staff_tables.py:131-133 gate on .edit only | low | S | guard | permissions |
| TD-499 | Web editor enforces retired qc to see_all dependency | OPEN | web components/admin/PermissionEditor.tsx:37,175 (blocked = key==='qc' && !want.includes('see_all')), header… | low | S | mirror | permissions / web |
| TD-500 | Mentor My students: alias query per mentee | OPEN | scholarship/mentoring.py:405 loop calls is_the_student per assignment (reads alias) | low | S | speed | mentor |
| TD-501 | Staff invites take no gift; NULL = every gift | OPEN | courses/views_staff.py AdminInviteView reads no programme; staff_reinvite.py:292 row.programme = None | medium | M | security | permissions / invites |
| TD-502 | Overview cards without filtered link | OPEN | scholarship/my_pending.py:143-155 cards for invitations, payment_runs, wallet_credits, sponsors_to_vet carry… | low | M | none | overview |
| TD-503 | wallet_credits / sponsors_to_vet card scope | OWNER | Owner rules who sees each card; my_pending.py:142-149 | - | - | - | overview |
| TD-504 | Invitations card org_read vs page team_read | OPEN | my_pending.py:144 may_read_org vs surface_gates.py:24-28 may_read_team | low | S | none | overview |
| TD-505 | Overview: id list, double EXISTS, no pooled budgets | OPEN | review_sla.py:114-116 builds Python id list then pk__in=ids | low | S | speed | overview |
| TD-506 | Dependency advisories Next, Pillow, pypdf | OPEN | halatuju-web/package.json:28,44 next 14.2.35; requirements.lock:67-82 pillow 11.3.0, pillow-heif 0.22.0,… | high | L | security | infra / dependencies |
