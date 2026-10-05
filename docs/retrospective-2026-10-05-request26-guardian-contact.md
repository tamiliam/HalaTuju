# Retrospective — request #26: correcting the parent/guardian phone (2026-10-05)

Sprint lane (analysis #69, owner rulings R1–R7). Built locally on `feat/req26-guardian-contact`,
**not pushed, not deployed, migration not applied anywhere but the local test database.** The lead
applies `0165` to production migrate-first; the owner gates the push.

---

## 1. What was built

* A student who has applied can correct their parent/guardian name and phone on /profile, except
  while bursary signing is possible for them (R1, R2, R4).
* A super or org_admin can correct it from the applicant summary at any time (R3) — while frozen, an
  org_admin only through the organisation holding the open offer (review F1).
* Every real change made through the product writes a `GuardianContactChange` row; a no-op writes
  nothing. Django's staff-only `/admin/` site is the one exception (review F2).
* The application-complete email asks the student to check the number (R5).
* Storage, `guarantor_phone_for` and `merge_guardians` are untouched (R7). No emergency contact (R6).

## 2. Where the build disagreed with the brief, and why

1. **The freeze is NOT "status 'awarded' until executed".** The brief described the signing window as
   "an application in the signing window (agreement not yet executed)" and also, rightly, required the
   freeze to REUSE the signing path's own predicate. Those two are not the same thing, and the second
   rule wins. The signing path's predicate (`_award_application`) is "a sponsorship with status
   **'offered'**" — the award not yet accepted. Accepting IS the in-session student + guarantor
   signature; after it the PIN views answer `no_offer`, so no PIN can be sent to the profile number
   again, and the number that WAS verified is stamped on the application (`guarantor_phone`). So the
   contact unfreezes when the student and guarantor have signed, which is EARLIER than the
   Foundation's countersignature ("executed"). Copying `status == 'awarded'` would also have frozen
   the 'signed, awaiting countersign' state for no reason. Pinned by
   `test_flag_on_once_student_and_guarantor_have_signed_is_not_frozen` and by the predicate-agreement
   test, which drives the REAL `verify-phone/send/` view across six states × flag on/off.
2. **The student endpoint is not on ProfileView.** `apps/courses → apps.scholarship` imports are at
   their budget (25) and `TestTheAppBoundary` refuses a 26th. A new scholarship endpoint,
   `/api/v1/scholarship/guardian-contact/`, keeps `apps/courses/views.py` untouched (2316 lines, all 13
   of its spare lines unspent), and the profile component fetches its own data.
3. **`/profile` had 195 bytes of first-load headroom, not "a few hundred".** Measured on a clean build
   of HEAD: 309.805 kB against a 310 kB budget. The section is therefore a lazy chunk
   (`LazyGuardianContactSection`, the `LazyStpmSchoolPicker` arrangement), and two optional strings
   were cut to stay under it (a "we'll use this later" hint on the profile and an "every change is
   recorded" note in the admin dialog — the FAQ and manual say the latter). Final: 309.953 kB, 47
   bytes under. **The next change that touches /profile or the shared catalogue will meet this
   line.**
4. **The baseline pytest run was contaminated by this sprint.** It was started before the first edit
   but ran for nine minutes while new files were being written; two subtests failed on an
   ImportError of a half-written module. Re-measured on a clean detached checkout of HEAD:
   **7826 passed, 3 skipped.** Lesson: never edit the tree a baseline is still running against — take
   the baseline in a separate worktree from the start.

## 3. Numbers

| Gate | Before | After |
|---|---|---|
| pytest `apps/` | 7826 passed, 3 skipped | 7852 passed, 3 skipped |
| jest | 3378 / 219 suites (lead) | 3391 / 221 suites |
| tsc | — | clean |
| next build | — | compiled (first build cold; later builds on the warm cache) |
| bundle-budget `/profile` | 309.805 kB | 309.953 kB (budget 310) |
| bundle-budget median | 227.676 kB | 227.740 kB (budget 229) |
| i18n | — | all passed, 5403 keys per locale |

After the gap A/B follow-up: pytest **7857** passed, 3 skipped; jest **3392 / 222 suites**; tsc clean;
next build compiled; `/profile` **309.953 kB (unchanged)**, median **227.740 kB (unchanged)**,
`/scholarship/award` 247.414 kB; i18n all passed, 5403 keys (no new string).

## 4. ⚠ GO-LIVE OPERATIONAL STEP (before anyone sets `BURSARY_AGREEMENT_ENABLED`)

When the flag flips, **every student holding an offered award freezes at the same moment** — they can
no longer correct the parent phone themselves; only a super/org_admin can. Before flipping it,
prompt every awarded student (65 today) to check their parent/guardian phone on /profile, and give
them time to do it. A wrong number found after the flip is a support ticket per student; found before
it is a self-service fix.

## 5. The two gaps this build reported — both closed in a follow-up commit

The first commit's retro listed two things it had not covered. The lead verified the first was
real and asked for both to ship closed.

**Gap A — a second application moved a frozen phone. PRE-EXISTING, not introduced here.** How it was
found: while reading the writers of `guardians` for the freeze, the apply form's
`create_application` → `sync_profile_fields` showed no freeze check, and the only guard in front of
it (views.py) is "one live application per student PER ROUND". The lead confirmed a round is open
until 1 Nov, so a student holding an offered award in one round could apply to another with their
own number in the parent box — and with signing on, receive the guarantor PIN themselves. The
2026-07-01 "locked phone" design had the same hole. How it was closed: in `create_application`,
when `contact_frozen(profile)`, the form's `guardians` are dropped before the sync; the stored one
stands, the application is created, every other field syncs. Not in `sync_profile_fields` itself,
because the admin correction path calls it while frozen. **Every write was re-checked by grepping
for the WRITE, not the helper** (assignments to `guardians`, `merge_guardians(` calls, `update_fields`
naming it, generic field copies): the only writers are `profile_sync` (reached from intake and
`guardian_contact.py`), the throwaway rolled-back eval fixtures, the local `bursary_e2e` command, and
Django's own `/admin/` site for staff — no other student-reachable writer.

**Gap B — signing trusted that the verified number was still the number on file.** Closed with one
more refusal in the existing chain: `guarantor_phone_changed` unless `application.guarantor_phone`
and `guarantor_phone_for(application)` are the same number in E.164. This is also what makes an R3
admin correction in the window correct: the old PIN vouched for the wrong phone. The award page
maps the code to the existing "verify your parent's phone with the PIN" words — a new string would
have ridden on `/profile`'s first load through the shared catalogue (47 bytes of headroom) — and puts
the PIN step back (it does the same for a stale `guarantor_phone_unverified`, which used to leave the
page showing "verified" with no way to re-send).

Bite-checked: removing the intake guard fails the flag-on gap-A test; removing the signing check
fails the gap-B test; removing the award-page mapping fails its jest test.

## 6. The adversarial review, and the bundle line that broke on rebase

**The bundle.** Rebased onto main, `/profile` read **310.101 kB against 310** — main's 7 new keys
plus our 3; neither commit alone broke it, together they did, because the whole en catalogue rides
on `/profile`'s first load. Shaving bytes would not have lasted: every key anywhere costs this route.
So a real static import moved: `malaysia-postcodes` (~10.9 kB gz, a chunk only `/profile` loaded) is
now imported on the fifth postcode digit. `/profile` 310.101 → **299.358 kB**. The ratchet then
REQUIRED the line to come down (a budget more than 2 kB above the build fails), so it was lowered
310 → **301** — the most headroom the ratchet allows (**1.642 kB**). The "~2 kB" the lead asked for is
capped by `SHRINK_SLACK_KB = 2` by design; 1.6 kB is the honest maximum. Median 227.888 → 228.000 kB
(our 3 new keys, on every route); routes that may cross before the median does 3 → 1. The catalogue
itself was not split (TD-300/TD-304 territory).

**The findings, all fixed and bite-checked** (each guard removed → its test failed):
* **F1 cross-organisation** — an org_admin of organisation A could move organisation B's signing PIN
  through A's application for the same student. Now 409 `guardian_contact_locked` while frozen unless
  their organisation holds the open offer.
* **F2 "every change is recorded" was false** — the application form wrote unrecorded. It records
  now; Django's `/admin/` site stays the documented exception.
* **F3 the student's own number** — refused on the profile and admin paths; dropped on the form.
* **F4 prefill** — `+60…` pre-filled as `601-…`; fixed in `lib/guardianPhone.ts`.
* **F5 junk numbers** — the server now validates a Malaysian mobile and stores one display form.
  `normalise_msisdn` is untouched: its other callers (Vircle confirm, phone-verify send/check, every
  outbound WhatsApp) read stored numbers of every historical shape.
* **F6 admin dialog** — real codes map to words; invalid phone reuses `scholarship.apply.error.phone`.

Gates after follow-up 2 (on main `ed7f9c0c`): pytest **7869** passed, 3 skipped; jest **3426 / 224**;
check-i18n **5413** keys; tsc clean; makemigrations clean; next build compiled (warm `.next` — deleting
it was denied); bundle-budget **ok**.

Left as known, per the lead: display-vs-PIN entry mismatch (pre-existing), the freeze check before
the row lock, frozen-without-template, the silent drop on a frozen second application, no rate limit.

## 7. The owner's consent reframe (follow-up 3)

"We are not dealing with a potential fraud. We only want the parent's consent to signing a contract,
so in the event of a dispute we could prove we have taken reasonable steps to ensure the parent is
onboard." That changed the design rather than a detail:

* **The own-phone refusal (review F3) was removed.** It flagged genuine families (9 production
  profiles; #62 and #125 share the PARENT's phone) and was dodgeable three ways. A shared number is
  accepted and FLAGGED; the flag is live, derived, and cleared only by a consenting confirming call
  recorded against the current number.
* **Record call** is the admin's tool, with one trail for changes and calls. Migration 0165 was
  edited in place (not yet in production); its profile link is now SET_NULL so the evidence lives as
  long as the signed agreement — the retention point the review caught: CASCADE would have deleted
  the consent evidence exactly when the contract it supports is kept.
* **The award good-news email waits** for the call on both senders (found by grepping the send
  functions and the env-gated paths: `release_award_offer_emails` — both its branches — and the
  owner's `send_award_offer_emails`; `award_and_notify` sends nothing inline).
* **Second review C, D, E** closed (guardians shape; ANY other-organisation offer refuses; a late
  postcode answer is dropped once anything moved).
* **The record corrected:** the parent-IC match proves knowledge, not presence; decisions.md said
  "stronger" and now says so.

Gates: pytest **7886** passed, 3 skipped; jest **3437 / 226**; check-i18n **5418** keys; tsc and
makemigrations clean; next build compiled (warm `.next`); bundle-budget **ok** — `/profile`
299.358 → **299.538 kB** (budget 301, 1.462 kB of room), median 228.000 → **228.081 kB** (0.919 kB of
room), routes that may cross before the median **1**. Every guard was bite-checked.

### ⚠ GO-LIVE STEPS added by this follow-up
* After this deploys, an admin should **Record a call** for **#116, #62, #125** (flagged by the
  shared-phone rule) and also **#25** (Swetha — her parent phone equals her own VIRCLE phone, so the
  contact-phone flag cannot see her). **Not #20** (Sharvani — under 18, so her parent registered her
  Vircle; the match is expected).
* Before the hourly release runs after the deploy, expect it to report `held_for_parent_call=[…]`
  for any flagged student whose award is still unemailed — that is the email waiting, not a fault.

## 8. The owner's final rulings and the record fixes (follow-up 4)

* **Ruling A — signing waits for the call.** Found every sender of the sign invitation by grepping
  the send function: only `send_sign_invitation_emails` (the signing reminders nudge the witness and
  Foundation AFTER the guarantor signed, so they do not apply). It now holds a flagged student and
  arms no accept clock; the PIN send and `sign_agreement` refuse `parent_call_needed`.
* **Ruling B — the list.** `?parent_call=needed`, super + org_admin, org-fenced, two queries for the
  whole set (a test pins that adding rows adds no query).
* **The record fixes the review confirmed.** A call was recorded against whatever number was on file
  at SAVE, not the one dialled — now the dialog sends what it displayed and a changed number is
  refused. An untouched consent box recorded "the parent refused" — now an explicit Yes / No with
  nothing pre-selected. Both made the evidence untrustworthy, which is the one thing it must not be.
* **Small fixes:** a corrected number takes the name the parent gave; a confirming call needs a
  number on file; Save, like Cancel, drops a late postcode answer; the note has `common.note`.

Gates: pytest **7899** passed, 3 skipped; jest **3448 / 227**; check-i18n **5420**; tsc and
makemigrations clean; next build compiled (warm); bundle-budget **ok** — `/profile` 299.538 →
**299.592 kB** (budget 301), median 228.081 → **228.133 kB**, routes that may cross **1**. Every new
guard bite-checked. NOT covered by a test: the profile page's Save calling `edited()` (the page has
no test harness; the hook's `edited()` itself is tested).

Left as known, per the lead: a student with no parent or guardian at all cannot be expressed; one
organisation's call clears the flag for another when nothing is frozen; one log line per held
student per hour.

## 9. The bundle line after the rebase, and the final review (follow-up 5)

**The bundle.** On `a3f56a44`, `/scholarship/application` read 274.009 kB against 274 — the shared en
catalogue rides on every route, our 13 keys (+272 gz bytes) plus main's tipped a route already at its
edge. The lever was OUR OWN strings: reuse where an existing sentence is honest, one "locked" sentence
for student and admin, shorter call strings under a short group. That got ~140 bytes, short of the
~150 asked. Seven genuinely dead keys were then deleted the TD-309 way, each proven unreferenced: no
`src`, test, script or api file names the full path OR the leaf, and no dynamic prefix in source
(`${…}` after a dot) reaches its parent. (A blanket finder was NOT trusted: its first pass listed
`sponsorLanding.faq.a1`…`a6` and `pathways.*`, which are reached through ``faq.a${i}`` and through
reason codes the api SERVES — both live.) Net: our catalogue footprint is −7 gz bytes.

**The findings.** (1) After a stale-number refusal the dialog kept the old number, so the advice
"close and record again" refused again until a reload — the dialog now re-reads the case on that
refusal. (2) With no number on file, "could not reach" always failed — only "corrected" is offered.
(4) The list and the case flag are two implementations of one rule — one test now runs both over
eight shapes and asserts the same answer. (3) is TD-347: not fixed, by ruling.

Gates: pytest **7919** passed, 3 skipped; jest **3722 / 239**; check-i18n **5416**; tsc and
makemigrations clean; next build compiled (warm); bundle-budget **ok** — `/scholarship/application`
**273.728 kB** (line 274, 272 bytes under), `/profile` **298.941 kB** (its line lowered 301 → 300 as
the ratchet required), median **227.941 kB**, routes that may cross **1**. Bite-checked: the stale
re-read, the corrected-only offer, and the agreement test (twice — the list ignoring consent, and
ignoring the number).

## 10. Not covered

* Malay and Tamil strings are first drafts and need the owner's review.
* Nothing was exercised against a real Twilio or a real browser; the signing path is mocked at the
  PDF, storage and Twilio seams.
