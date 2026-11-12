# HalaTuju v3.1.0 audit: closure table

Built 2026-11-12 from the audit (`docs/audits/2026-11-05-project-audit.md`), `docs/technical-debt.md`, the fix roadmap, the g15 git history (every cited commit is in origin/main) and a grep of the tests. Test names were found by grep; the tests were not run. A register line marked FIXED was believed only when a commit was found.

**Counting note.** The audit's 74 findings are TD-465 plus 73 lens findings. SEC-07 is folded into SEC-18 by the audit, so it has a row but is left out of every count below (75 rows, 74 counted). The severity split matches the audit: 1 high, 45 medium, 28 low. No finding was rejected by the adversarial review in the audit's own Rejected section at the finding level other than as merges or re-ratings, so the rejected count is 0 (CO-05's mock-money-in-production claim and TD-252, CO-04's register contradiction, SP-01's 40 percent figure were rejected as sub-claims only).

## Summary

| Status | Count |
|---|---|
| fixed+tested | 32 |
| fixed-untested | 13 |
| deferred | 24 |
| accepted | 1 |
| rejected | 0 |
| unknown | 4 |
| **Total** | **74** |

| Severity | fixed+tested | fixed-untested | deferred | accepted | rejected | unknown | Total |
|---|---|---|---|---|---|---|---|
| high | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| medium | 19 | 9 | 16 | 1 | 0 | 0 | 45 |
| low | 12 | 4 | 8 | 0 | 0 | 4 | 28 |

## Gaps (high, security, money or access-control findings not yet fixed+tested)

- TD-465 (high, money): fixed+tested, but the 2026-11-02 ruling that the reviewer sets the amount from the time left is not built; stored awards untouched by owner ruling D2.
- SEC-18 / SEC-07: overwrite fixed and tested; the bucket type and size limits are written as SQL, not applied (TD-467, TD-550).
- SEC-11 and SEC-14: SQL written, not applied (TD-550, owner step).
- SEC-13: no gate built; closed as documented by a lead decision, owner may overrule (TD-548).
- SEC-10 and SEC-15 (dependency advisories): fixed, but no test would catch a regression; only audit tooling.
- SEC-20: TD-503 (owner call on two cards) and TD-521 (role sandbox) still open.
- SEC-05 and SEC-12 are fixed+tested but have owner steps that decide the live effect: set per-family cron keys; check live headers and rule on web HSTS (TD-550).
- CO-04 (money, contract): signing flag OFF; TD-534 must land before it is set; TD-140 and TD-152 are owner or legal.
- CO-05 (money): real sponsor money waits on the lawyer, the entity and TD-140 (TD-075, TD-142).
- CO-08 (consent): WhatsApp STOP inert until the owner sets the webhook (TD-318).
- CO-10 (document reading): S7, TD-114 and TD-399 with the owner.
- CO-16 (money code): status unknown, see its row.
- RD-01 (income rule, eligibility and money): TD-262 open.
- RD-03 (permissions): fixed+tested, but the legacy super-flag column drop (TD-064) is still an owner step.
- RD-09 (identity, typed-name check): unknown; two copies pinned, not merged.
- SP-01 and SP-02 (live harm): fixed+tested in code; live proof (7 days of logs after deploy) was not read in the close.

## Closure table

| ID | Severity | Finding | Status | Evidence | Note |
|---|---|---|---|---|---|
| TD-465 | high | STPM accept with an unknown course start year was auto-awarded RM3,000 (money) | fixed+tested | b0bedd54 (part 1, money-a), 4980b2b7a (part 2, A1.13); `apps/scholarship/tests/test_td465_course_start_unknown.py::test_accepted_stpm_with_unknown_start_year_gets_no_rm3000`, `apps/scholarship/tests/test_course_start.py` | Both parts are in origin/main. Not built: the 2026-11-02 ruling that the reviewer sets the amount from the time left. Stored awards untouched; owner ruling D2 closed the case count (no list, no data change). |
| SEC-01 | medium | A student could register another student's stored file path (offer letters guessable inside one organisation) | fixed+tested | ecb02b7ed, 26b47c883; `apps/scholarship/tests/test_sec01_doc_paths.py::test_another_applicants_key_in_the_same_organisation_is_refused` | Register entry TD-512 is not marked fixed (register lag). Follow-up lows TD-510, TD-511 open. |
| SEC-02 | medium | A user-writable metadata flag decided who may claim an invited staff row | fixed+tested | ecb02b7ed, 26b47c883; `apps/courses/tests/test_sec02_staff_link.py::test_a_forged_user_metadata_flag_without_a_confirmed_email_does_not_link` | Code flaw closed whatever the Confirm-email setting is. I found no record of the owner's answer on that setting. TD-513 not marked fixed (register lag). |
| SEC-03 | low | Throttle key could be forged with client-set headers | fixed+tested | fd5deefe4 (TD-514); `apps/scholarship/tests/test_throttling.py::test_a_forged_leftmost_hop_is_ignored` |  |
| SEC-04 | medium | Partner CSV export had no audit line and no spreadsheet-formula guard | fixed+tested | fd5deefe4 (TD-515); `apps/courses/tests/test_admin_export.py::test_a_typed_formula_cannot_run_in_a_spreadsheet`, `::test_the_export_leaves_an_audit_line_without_pii` |  |
| SEC-05 | low | One shared cron secret opened every scheduled job | fixed+tested | fd5deefe4 (TD-546); `apps/scholarship/tests/test_cron_auth.py::test_a_family_key_opens_its_family_only` | The shared secret is still accepted until the owner sets per-family keys (test_before_the_owner_sets_anything_the_shared_key_opens_every_job), so the live gain waits on that owner step. |
| SEC-06 | low | Django admin sign-in had no throttle | fixed+tested | fd5deefe4 (TD-547); `apps/scholarship/tests/test_admin_login_throttle.py::test_a_new_forged_hop_does_not_buy_more_guesses` |  |
| SEC-07 | low | Upload type and size trusted client values (folded into SEC-18) | deferred | TD-467, TD-550 | Not counted separately in the 74 (the audit folds it into SEC-18); status follows SEC-18. |
| SEC-08 | low | Claim-code counter race | fixed+tested | fd5deefe4 (TD-520); `apps/courses/tests/test_profile_claim.py::test_two_callers_that_read_together_cannot_both_take_the_last_use` |  |
| SEC-09 | low | An email address was written into a warning log line | fixed+tested | fd5deefe4 (TD-520); `apps/courses/tests/test_email_verification.py::test_a_failed_send_logs_the_profile_not_the_address` |  |
| SEC-10 | medium | Dependency advisories (DRF, pyjwt and others) on the unauthenticated and auth paths | fixed-untested | 73c7d5f3a (A1.2; TD-516 resolved) | Version bumps, pip-audit clean per the register. No test pins the versions or would catch a regression. |
| SEC-11 | low | Public read policy on the partner organisations table (contact details) | deferred | 033849755 wrote `docs/security/2026-11-07-sec11-partner-organisations-read-policy.sql`; TD-550 | SQL written, NOT applied. The owner runs it. I could not confirm it has been applied. |
| SEC-12 | low | Thin security headers on the web, short HSTS on the API | fixed+tested | 033849755, fd5deefe4; `halatuju-web/src/lib/__tests__/securityHeaders.test.ts`, `apps/scholarship/tests/test_production_hsts.py` | Live-response header check and the web HSTS ruling are still open under TD-550. |
| SEC-13 | low | Anonymous sign-ins skip the NRIC gate | deferred | TD-548 | Closed as documented, no gate built, owner may overrule (a lead decision, not an owner quote). |
| SEC-14 | low | 15 deny-all tables lack a service_role policy | deferred | 033849755 wrote `docs/security/2026-11-07-sec14-service-role-policies.sql`; TD-549, TD-550 | SQL written, NOT applied (owner step). Harmless today. |
| SEC-15 | medium | Next.js advisories (criticals unreachable here, denial-of-service highs remained) | fixed-untested | 1e7fabafa (Next 15.5.29, React 19.2.9; A1.1); TD-506 web half | npm audit clean for next itself per the register; no test applies. TD-506 stays open for residual build-time postcss. |
| SEC-16 | medium | Pillow, pypdf and pillow-heif advisories on student uploads | fixed+tested | 73c7d5f3a, b760e6a80; `apps/scholarship/tests/test_a12_upload_libs_smoke.py` | Smoke tests are mocked. Re-reading one digital STPM certificate on the new pypdf was still to do (TD-506 note). |
| SEC-17 | medium | Reviewer invite took no gift; empty meant every gift | fixed+tested | 80230267e, d654f3af1; `apps/courses/tests/test_reviewer_invite_gift.py::test_no_choice_is_refused_and_nothing_is_written`, `apps/scholarship/tests/test_assign_gift_mismatch.py` | TD-501 marked FIXED. |
| SEC-18 | medium | Uploads could overwrite; bucket had no type or size limit | deferred | 0a8fc1357 + `apps/scholarship/tests/test_a17_upload_no_overwrite.py::test_both_doors_sign_with_x_upsert_false` (overwrite half is fixed+tested); TD-467, TD-550 | Bucket limits SQL (`docs/security/2026-11-06-b40-documents-bucket-limits.sql`) written, NOT applied; TD-467 stays open until the bucket read-back shows limits. |
| SEC-19 | medium | A decline below AWAITING QC got no QC check | fixed+tested | c443e093f (A1.11b); `apps/scholarship/tests/test_a111b_decline_and_close_gates.py::test_qc_reopen_to_interviewing_then_reject_is_refused`, `test_td481_awaiting_qc_decline.py` | TD-487 and TD-488 closed. |
| SEC-20 | low | Known leftovers TD-488, 496, 497, 499, 503, 504; no role sandbox | deferred | TD-503 (owner call), TD-521 (sandbox); fixed: TD-488 c443e093f, TD-497 671c6b383, TD-499 67bc90807, TD-504 (A1.10a), TD-496 closed by removing the view | Four of six leftovers fixed; two still open. |
| CO-01 | medium | No real sign-in per role on a local stack | deferred | TD-521 | Roadmap A3.16b note: not done, CO-01 sandbox. Still open. |
| CO-02 | medium | Roadmap document stale (said v2.0) | fixed-untested | e2fcf8a7d (A0.3, TD-522 resolved) | Docs only; no test applies. |
| CO-03 | medium | No table of live flag values | fixed-untested | e2fcf8a7d; `docs/deployment.md` section Live flag values | Docs only; the table can go stale. |
| CO-04 | medium | In-app signing built but blocked | deferred | TD-140, TD-152, TD-534; TD-347 fixed by 9ce461dfe, d1fe1e355 with `apps/scholarship/tests/test_parent_call_signing.py` | Signing flag still OFF. TD-534 (re-open signing email must state the new deadline) MUST land before the flag is set. |
| CO-05 | medium | Sponsor money is still a mock, not tied to the signed agreement (money) | deferred | TD-075, TD-142, TD-140 | Audit status 2026-11-08 (A1.13): waits on the lawyer, the entity and TD-140. Owner and business items. |
| CO-06 | medium | Phone sign-in is a coming-soon stub | deferred | TD-043 | Owner decision (paid service or Google only). |
| CO-07 | low | Coming-soon screens (billing card, sponsor portal, trust hub, guide) | deferred | Roadmap section 4.3 (features) | No TD or sprint number named; needs the owner's word to build. |
| CO-08 | medium | WhatsApp STOP inert until the webhook is set | deferred | TD-318 | Owner action in the messaging console. Cannot be verified from the repo. |
| CO-09 | medium | No way to withdraw an award once out (money) | fixed+tested | 4980b2b7a, 8138854ec, 6e11556e4 (A1.13, A1.13b); `apps/scholarship/tests/test_award_withdrawal.py::test_withdraw_returns_case_to_pool_and_frees_balance`, `test_award_withdrawal_chain.py` | TD-198 marked FIXED. Maker and checker rule per owner ruling. |
| CO-10 | medium | Document-reading gaps (corpus brief, S7 frozen, TD-114, TD-399) | deferred | 9c3e1b538 (A2.8b) with tests; S7 (paid, owner's word); TD-114, TD-399 | Audit re-checked 2026-11-09: corpus work done; S7, TD-114 and TD-399 stay with the owner. |
| CO-11 | medium | About 92 plan files, most with no Status line | fixed-untested | d814d9b9f, 521a45eb6 (A0.3) | Docs only. |
| CO-12 | medium | Vocabularies that are not yet a gate | fixed+tested | f3bd1e25a; `halatuju-web/src/lib/__tests__/vocabularyGateDrift.test.ts` |  |
| CO-13 | medium | 25 owner-decision debt items waiting | deferred | Roadmap section 3 (owner decisions D1 to D13) | Owner list; not engineering work. |
| CO-14 | low | Debt items never walked in a browser | deferred | TD-070, TD-112 (walk scripts added by 1abce4f1d, skipped by default), TD-184, TD-196 (owner); TD-092 fixed | Walk scripts under `halatuju-web/e2e/` need a local sign-in stack. |
| CO-15 | medium | Release leftovers (repeats SEC-15, SEC-16, SEC-17; merged) | fixed-untested | See SEC-15, SEC-16, SEC-17 | Merged into SEC-15 by the audit; status follows SEC-15. |
| CO-16 | low | Deprecated bank-details code still shipped | unknown | Roadmap A3.17 status line: CO-16 kept (money) | No owner quote or TD found for keeping it; looked in technical-debt.md and CHANGELOG. |
| CO-17 | low | Old roadmap leftovers | fixed-untested | e2fcf8a7d, 26ed3469a (A0.3) | Docs only. |
| RD-01 | medium | Income rule lives in about eleven places, web mirror unguarded | deferred | TD-262 (open; owner ruling on option 4) | A3.4 added golden tests (847050aff) but the unification is not done. |
| RD-02 | medium | Debt index said 137 open, real count 219 | fixed-untested | 627e6fe53 (A0.2), e2fcf8a7d (TD-522) | Index regenerated; docs only. |
| RD-03 | medium | Two permission systems coexist | fixed+tested | 671c6b383, 67bc90807 (A1.10a, A1.10b); `apps/courses/tests/test_role_is_display_only.py::test_every_role_read_is_allowlisted` | Dropping the legacy super-flag column (TD-064) is an owner step still open. |
| RD-04 | medium | Cross-app reach-ins both ways | deferred | F2; xapp 107 against target 50 | Owner's deadline: monthly small audit, 11 Dec. NOT accepted. |
| RD-05 | low | Logic imported sideways from the view layer | fixed-untested | bdd520ce6 (A3.11) | Part only: round_state moved. programme_overview still reaches two helpers in views_admin/reviewers.py. |
| RD-06 | medium | 41 web mirrors without a drift guard | fixed+tested | 44fcff3c1 (A3.16a); `halatuju-web/src/lib/__tests__/appMirrorDrift.test.ts` | Mirror reading 3 to 0. |
| RD-07 | low | Two dead web files | fixed-untested | a8a7d52e3 (A3.17) | Both files confirmed absent from the tree. Removal needs no test. |
| RD-08 | low | API routes with no web caller | fixed+tested | a8a7d52e3; `apps/courses/tests/test_route_web_callers.py::test_the_scan_sees_the_web_source` | 17 routes allowlisted. |
| RD-09 | low | Typed name equals actual name, in several copies | unknown | 37563cdb5; `apps/scholarship/tests/test_typed_name_pin.py` | Two copies, not three; deliberately pinned and NOT merged (they differ on whitespace; CHANGELOG A3.11). No owner acceptance or TD found. |
| RD-10 | medium | Organisation-resolver helper in five copies | deferred | TD-412 (still open) | Scoped in A3.11 but not done; copies remain in views_admin (theme, org_config, overview, invoices, spending_flags). |
| RD-11 | low | Test-only or offline files in the API | fixed+tested | f78fa3bb5 (A3.10); `apps/scholarship/tests/test_repair_commands_have_a_door.py::test_every_repair_command_is_reachable_or_declared` |  |
| SP-01 | medium | record-verdict made two paid model calls inline (live harm) | fixed+tested | f2b33fa2a, 15b5c555d, df6ab4174 (A2.1); `apps/scholarship/tests/test_profile_finalise.py::test_queue_sets_pending_and_calls_nothing` | Live p95 not re-read (needs logs 7 days after deploy). |
| SP-02 | medium | reprocess-ic-vision runs near the 300 s limit | fixed+tested | a8efd64c7, 882b65d90 (A2.2); `apps/scholarship/tests/test_reprocess_time_budget.py::test_stops_at_the_budget_then_resumes_with_none_skipped_or_read_twice` | Live proof (p95 under 120 s) not read in the close. |
| SP-03 | medium | Document upload does heavy work in the request | fixed+tested | 3a38e70c3, 401f91e17 (A2.3); `apps/scholarship/tests/test_upload_read.py::test_an_ic_upload_answers_at_once_with_no_read` | Live p95 not read. |
| SP-04 | medium | Assign sends email inline, heavy reply | fixed+tested | 3a38e70c3, e599c5631 (A2.3, A2.3b); `apps/scholarship/tests/test_assign_query_budget.py::test_each_reading_stays_inside_its_budget` | Live p95 not read. |
| SP-05 | medium | Interview submit, qc-decision, resolution-items slow | fixed+tested | b4617a0a6 (A2.4); `apps/scholarship/tests/test_a24_slow_reads_budget.py::test_each_reading_stays_inside_its_budget` | Local query counts only (334, 333, 319 down to 41, 51, 37). |
| SP-06 | medium | Income coach GETs call a model on every open | fixed+tested | b4617a0a6, 78fcb90cf; `apps/scholarship/tests/test_a24_help_cache.py::test_a_repeat_open_makes_no_second_model_call` |  |
| SP-07 | medium | Applicant detail slow (p50 2.5 s) | fixed+tested | b4617a0a6; `apps/scholarship/tests/test_a24_slow_reads_budget.py` | Only reduced (38 to 33 queries); production p95 not re-measured. |
| SP-08 | medium | No minimum instances; heavy cold start | deferred | TD-523 | Owner's cost call; no decision found. |
| SP-09 | medium | Bundle headroom thin (0.4 to 1.2 kB) | deferred | W1 (build 16-18 Nov, deploy by 20 Nov); std reading FAIL | Headroom not re-measured at close (no next build). |
| SP-10 | low | Bundle budget does not count layouts, CSS, lazy chunks (TD-304) | unknown | TD-304 marked RESOLVED 2026-10-04 before the audit; roadmap A2.5 scope | A2.5 not built (no commit found). Looked for A2.5 commits and a TD-304 closure after the audit; the two records conflict. |
| SP-11 | low | 33 scheduled jobs, 13 hourly or more often | unknown | Roadmap A2.5 scope (merge the hourly email jobs) | Looked for an A2.5 commit and a job-count change in git log and the register; none found. |
| SP-12 | medium | Build minutes high (15-27 min) | deferred | TD-523 | Owner's cost call; no build-time change found. |
| SP-13 | low | N+1 on mentor and pending cards | fixed+tested | b4617a0a6 (A2.4; TD-500, TD-505); `apps/scholarship/tests/test_a24_other_reads_budget.py::test_each_reading_stays_inside_its_budget` |  |
| SP-14 | low | 300 s timeout applies to the whole service | fixed+tested | a8efd64c7 (A2.2); `apps/scholarship/tests/test_reprocess_time_budget.py` | Met by the job's time budget, not by a separate service. |
| CH-01 | medium | Bundle ratchet FAIL from the Next security patch | accepted | Audit summary line 10 and Closing section | Quote: The code-health FAIL (bundle ratchet) is accepted. Closing: std owner-accepted until Fri 20 Nov (W1). It lapses on 20 Nov and goes back to the owner. |
| CH-02 | medium | Consolidation Review overdue, wat_lint FAIL | fixed-untested | c8e1902b1, ed64ca7cc, 8b9882800 (C1) | Closing: Review done 2026-11-12, wat_lint 0 fail. Process item; no test. |
| CH-03 | medium | fix ratio 51 percent, third WARN: becomes a debt item | deferred | F1 (slip-check matrix; deploy by 27 Nov); TD-385 fixed in the workspace tool (fc11e13) | Closing: fix% 52 (WARN, accepted). Proof at the 11 Dec small audit. |
| CH-04 | medium | vision.py hotspot | fixed-untested | 8fad7da46 (A3.1); Closing reading hot#1 32.4 to 18 | Number target met by the split. Top 5 under 15 NOT met (18, 13, 12.2) and has no sprint named. |
| CH-05 | low | 13 files over 1000 lines | fixed+tested | A3.1 to A3.9; Closing reading big 13 to 1; `apps/scholarship/tests/test_code_standards.py`, `halatuju-web/src/lib/__tests__/codeStandards.test.ts` |  |
| CH-06 | medium | 15 functions over 150 lines | fixed+tested | A3.1 to A3.10; Closing reading long 15 to 1; 6c74f4332 scanner self-test in `apps/scholarship/tests/test_code_standards.py` |  |
| CH-07 | low | Duplicated function names in three homes | deferred | Gemini duplicate sprint, by Fri 4 Dec | Closing: dup 4 to 1 (_gemini_generate), target 0 NOT met. |
| CH-08 | medium | 3 web mirrors with no drift test | fixed+tested | a316a, 44fcff3c1; `incomeWizardDrift.test.ts`, `appMirrorDrift.test.ts` | Mirror reading 0. |
| CH-09 | low | Cross-app coupling grew | deferred | F2 (by 11 Dec); xapp 85 to 107 | NOT accepted. Courses-to-scholarship 21 against target 8. |
| CH-10 | low | Suppressions 92 | fixed+tested | 9e132c949 (A3.14), 00a83e400 (A3.15); budgets lowered in the code-standards tests; supp 92 to 20 | Target (30) met. |
| CH-11 | medium | Debt count rose 203 to 219 | deferred | 11 Dec monthly small audit (no sprint) | td_open 219 to 169, target 110 NOT met. Closing: no sprint was set and the owner has recorded no decision on it. |
| CH-12 | low | Register near-misses to tidy | fixed-untested | 627e6fe53 (A0.2) | Docs only. |
