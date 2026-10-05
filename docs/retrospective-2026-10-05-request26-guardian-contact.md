# Retrospective — request #26: correcting the parent/guardian phone (2026-10-05)

Sprint lane (analysis #69, owner rulings R1–R7). Built locally on `feat/req26-guardian-contact`,
**not pushed, not deployed, migration not applied anywhere but the local test database.** The lead
applies `0165` to production migrate-first; the owner gates the push.

---

## 1. What was built

* A student who has applied can correct their parent/guardian name and phone on /profile, except
  while bursary signing is possible for them (R1, R2, R4).
* A super or org_admin can correct it from the applicant summary at any time (R3).
* Every real change writes a `GuardianContactChange` row; a no-op writes nothing.
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

## 6. Not covered

* Malay and Tamil strings are first drafts and need the owner's review.
* Nothing was exercised against a real Twilio or a real browser; the signing path is mocked at the
  PDF, storage and Twilio seams.
