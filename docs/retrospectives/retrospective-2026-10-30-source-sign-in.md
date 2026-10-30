# Retrospective — Source sign-in, S1–S4 and two review rounds (2026-10-30)

Branch `source-signin`, seven commits (`89714e00` … `f45bc558`). Roadmap
`docs/plans/2026-10-30-source-sign-in-roadmap.md`. **Built and reviewed, NOT deployed — waiting for the owner's
go.** Deploy order: `halatuju_api/CLAUDE.md` "Next Sprint".

## What Was Built

A referral source (a `referral_sources` row) can now be invited, sign in and see its own students — the owner's six
asks, with nothing that could compromise review.

- **S1 — the role and the fence.** New role `source_partner` and `PartnerAdmin.source` (courses 0089, a database
  CHECK ties the role to a source). **Deny by default:** `PartnerAdminMixin.get_admin` treats a source user as "not
  an admin" on every view unless the view opts the method in. `source_access.py` decides which applications and
  gifts a source may see (its own students, plus a witness override). A source user is not staff: left out of the
  Team roster and every staff-management action.
- **S2 — inviting a source.** Invitations → Source replaces "Add source" (the old POST answers 410); invite an
  existing source or a new one; Resend and Remove; super and org_admin only. `Invitation.referral_source`
  (scholarship 0190). The Sources page's Edit locks once the source has joined (409 `managed_by_source`). The source
  letter is wired; `set-password` lands through `adminLanding`.
- **S3 — the read-only console.** Six routes under `api/v1/admin/source/` built as allowlists: Profile, Overview,
  Applications, one application, Scholars, one scholar. The stage shown is what the STUDENT sees, so a source never
  learns an outcome first. No NRIC, income, documents, scores, verdicts or money.
- **S4 — the witness.** The witness source reads the full contract (owner ruling) and records its witness itself
  (typed name + declaration), through the unchanged `bursary.record_witness` under a row lock; `witness_ip` and
  `witness_admin` (scholarship 0191). The super's button stays as the fallback. Witness emails get their link back
  when the source has a signed-in user. `BURSARY_AGREEMENT_ENABLED` is off, so this ships ready but quiet.
- **Web.** The Source invite tab, the Sources lock, the console pages (each lazy-loaded), the witness step inside
  the student's page (`?step=witness`), the role in the menu registry, and a layout guard that sends a source user
  off any staff page before it mounts.
- **Two adversarial review rounds** (a reviewer that did not build it): backend (1 high, 2 medium, several low) and
  web (4 medium, 10 low). Every finding fixed with a test that failed first, or logged (TD-429, TD-430, TD-431).

## What Went Well

- **Deny by default held.** The sweep test walks every `api/v1/admin/` route and every method off the URL resolver
  as a source user; a new staff view added tomorrow is denied without anyone remembering the role. Bite-checked:
  with the gate off the sweep went red on five routes.
- **The doors list paid for itself.** Writing down every way to become, widen or lose a source user before S1 gave
  the builders and both reviewers the same checklist; the review hunted for a door not on it rather than re-deriving
  the list.
- **Mock-ups before UI code.** The eight screens were approved ("Looks good. Proceed") before any web work, and the
  web half needed one review round, with no layout rework.
- **The bundle was protected on purpose.** Each source screen is its own lazy chunk; imported statically they put
  the median at 148.6 kB against 148, a gate failure caught locally, not by Cloud Build.
- **Tests failed first.** Every review fix (20 backend, 39 web) was run against the pre-fix code and seen to fail.

## What Went Wrong

1. **The assignment picker's staff list would have served a source user.**
   *Symptom:* the S1 sweep found `GET` on the assignable-admins staff list answering 200 to a planted source user —
   a list of the organisation's reviewers and staff. *Root cause:* that view's gate asked "is this an admin inside
   the organisation's fence?", which a source user is; the gate was written when every `PartnerAdmin` was staff, so
   it was not role-aware. Auditing views one by one (the roadmap's C3 list) had not named it.
   *System change:* fixed once, centrally — `get_admin` denies the role by default and a view must opt a method in
   (`source_partner_methods`); the resolver-driven sweep (`test_source_user_denied_everywhere.py`) fails on any
   route a source user reaches that is not on its `ALLOWED` list. Lesson added.

2. **A decline still in its cool-off leaked through a raw-status query, and a witnessed contract followed the live
   override.**
   *Symptom:* the backend review (H1) found the Scholars list and the witness check reading `has_file_q` and
   `WITNESS_STATUSES` on the RAW status, so a source would see a student leave its list — the decline — before she
   was emailed. M1: after a witness was recorded, moving the override handed the signed contract to the new source.
   *Root cause:* the console's stage used `student_facing_status`, but the two set-level queries borrowed staff
   helpers that filter on the stored status; the masking lived in one function and the query helpers went round it.
   For M1, "who may read the contract" was computed from the live override, not from the record of who signed.
   *System change:* `source_console.scholar_q()` and `contract_live()` read the student-facing status; a recorded
   witness is bound to `agreement.witness_org`; `test_source_signin_review.py` pins both. Lesson added: an outcome
   rule must read the student-facing status, never a raw-status query helper.

3. **No layout-level guard for a typed staff URL.**
   *Symptom:* the web review (M3) found that a source user typing a staff URL would have that staff page mount and
   fire its calls (each refused by the server); only the menu kept the links out of sight. *Root cause:* each source page
   branched on the role, but nothing above the pages did; the menu was treated as the fence. *System change:*
   `adminLanding.sourceMustLeave` in the admin layout sends a source user on any page `canAccess` refuses to its
   landing BEFORE the page or the shell mounts; `noStaffCalls.test.tsx` renders all seven pages as a source user
   and fails on any staff API call.

4. **The weekly partner email already leaks a cool-off decline (pre-existing).**
   *Symptom:* the S3 builder found `partner_comms.stage_counts` counting a decline still inside its 24-hour cool-off
   as "Rejected" in the weekly summary a source already receives today. *Root cause:* the same raw-status trap as
   item 2, older; the email was written before the masking function existed. *System change:* not fixed here (it
   changes a live email and needs its own decision) — raised as TD-430 (medium), with the console's rule as the fix.

5. **The roadmap's migration number was stale.**
   *Symptom:* the roadmap named `scholarship/0189` for S2; another session (maintenance S6a) took 0189 first, so S2
   became 0190 and S4 0191. *Root cause:* a migration number was written into a plan hours before the build, in a
   repo where several sessions add migrations the same day. *System change:* plans name the migration's CONTENT, not
   its number; the builder derives the number at build time from `origin/main` (as S2's builder did), and the
   roadmap now says why it moved.

**Review answered.** Every finding of both rounds is fixed or answered: backend in `decisions.md` 2026-10-30
"Source sign-in: the adversarial review's fixes" (L5 → TD-430, L6a → TD-431), web in the CHANGELOG's review round 1.

## Design Decisions

Logged in `docs/decisions.md` (2026-10-30): "Sources sign in" (S2, owner rulings), "What the source console shows"
(S3), "A source witnesses from its console" (S4), "Source sign-in: the adversarial review's fixes", and "Source
sign-in web" (the witness step inside the student page, lazy source screens, the layout guard).

**Owner items still open:**
- Confirm the witness source may see the FULL contract, NRICs and amounts included (the owner ruled "full contract";
  the lead is to say plainly what that includes).
- The lead's call that a source's student page shows the coarse missing checklist parts — one step past the
  partner-email ceiling.
- The Admin role no longer adds sources: inviting is super / org_admin only. The lead's default; the owner has not
  been asked explicitly (Admin could Add a source since 2026-07-19).
- The wording of the witness declaration.

## Numbers

- 7 commits, 111 files, +9,404 / −486 lines; 3 migrations (courses 0089, scholarship 0190, 0191), all migrate-first.
- 10 new api routes (6 console, agreement, witness, resend, revoke); the invitation POST gains a source audience.
- New backend tests: `test_source_invite.py` 41, `test_source_console.py` 38, `test_source_witness.py` 36,
  `test_source_signin_review.py` 20, plus S1's three sweep / scope files.
- Gates at the close: api **10,837 passed / 3 skipped** (`pytest -n auto`, rebased branch, before the web review
  round, which touched no backend file) · web **5,418 jest / 337 suites** · `next build` OK · bundle median
  **147.751 kB of 148** (0.249 kB room); `/scholarship/application` 0.132 kB under its line.
- Tech debt raised: TD-429, TD-430 (backend review), TD-431 to TD-433 (close); TD-427 status updated.
