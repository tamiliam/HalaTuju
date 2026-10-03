# Retrospective — Next-tier batch 3 (2026-10-03)

**Scope (the lead's brief):** five small, student- or officer-visible fixes from the debt
register's Next tier — TD-164, TD-169, TD-145, TD-244, TD-251. Built by one agent; not committed,
pushed or deployed. An adversarial reviewer who did not build it reads the diff before the lead
commits. The owner reads the one new Tamil string and rules on TD-145's switch.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-164 | the student's mask for an embargoed decline reads `pre_decline_status` (blank → 'interviewed'; 'recommended' still masked) | `test_student_status_mask.py` (6); the old masking test carries its superseding note |
| TD-169 | the Vircle guide attachment is named after the sending brand; the platform keeps `VIRCLE_GUIDE_FILENAME` byte-for-byte | `test_email_branding.py` — the leak test reads attachment names, with a positive half on all nine guide sends; the 113 goldens untouched |
| TD-251 | an activated phone in the inbound row is the activation, stamped at arrival; a wallet without one warns, names only | `test_vircle_activation_signal.py` (6); the Pending test in `test_vircle_airtable.py` stands |
| TD-244 | `wallet_not_live` on each funding row + a count; an amber line on the Payments funding summary names the students | `test_payment_endpoints.py` (+1, key snapshot extended); `payments/page.test.tsx` (+2); `financeAllowlistDrift` |
| TD-145 | `catalogue_declared_institution` built; the wiring HELD | `test_declared_catalogue_institution.py` (5, incl. the pinned blind spot) |

## What bit

Twelve injected faults, each restored from a byte backup with the SHA-256 equal:

| Fault | Went red |
|---|---|
| the mask back to a hard-coded `'interviewed'` | `test_shortlisted_decline…` + the per-stage subtests |
| `send_vircle_install_email` stops passing branding to the attachment | the org-2 leak test |
| `send_award_offer_email` stops passing branding to the attachment | the org-2 leak test |
| the activated phone stops being a signal | 8 in `test_vircle_activation_signal.py` |
| any present `Status` value activates | both Pending tests (old and new) + the names-only warning test |
| `wallet_not_live` always False | the funding-summary endpoint test |
| the resolver guesses the first campus of a multi-campus course | the multi-campus test |
| the held wiring switched on in `_declared_pathway` | the held-wiring test |
| (review) shortlisted shown as itself again | the profile_complete test |
| (review) the phone beats a present non-Done Status | the Pending-silences-the-phone test |
| (review) the release cron drops its branding | the release-cron caller test |
| (review) the Vircle command drops its branding | the Vircle-command caller test |

## The adversarial review (FIX-THEN-SHIP; two MEDIUM, two LOW — all fixed, each bitten)

- **F1 (MED):** masking a declined SHORTLISTED student as `shortlisted` put her back on the editable
  form, where every write 403s and the documents list reads empty. Lead's ruling: show
  `profile_complete` (locked). Test + a contractual-from-`active` test (shows `active`).
- **F2 (MED):** a present phone beat a present non-Done Status. A Status now silences the phone.
- **F3 (LOW):** no PRODUCTION caller passed branding — only the send functions took it. All four
  now do (`test_award_sends_branding.py`). The first report said "both callers pass their
  branding": true of the two send functions, false of the code that calls them. The leak test
  proves a send renders what it is given and cannot see a caller that gives nothing.
- **F4 (LOW):** the register said "step 3"; only its second half (the warning) is built. Reworded.
- Production counts (the lead, read-only): 0 students mid-embargo; 0 funded with a wallet and no
  activation (65 activated); TD-145 T4 = 0 and T6 = 0 — no live offer would flip under the held
  switch.

## What was learnt

- **The prescribed fix for TD-145 had been overtaken by its neighbour, and only reading the call
  site showed it.** The entry (June) said: fill the declared institution from the catalogue so
  `offer_pathway_match` can raise a clash. Since #48 (July), a record with a `course_id` never
  reaches that comparison — `institution_agreement` replaces it, and for a one-campus course it
  answers `match` without looking. Wiring the resolver as written would have shipped green, closed
  the entry, and caught nothing. The honest deliverable is the resolver, the pinned blind spot,
  and the question to the owner. (Rule 8: characterise before you change.)
- **The settings default made the "thread branding" fix a no-op on its own.** `VIRCLE_GUIDE_FILENAME`
  defaults to the BrightPath string, so a fix that only changed the module constant would never
  have reached a tenant. The attachment NAME and the Drive LOOKUP name are two things and are now
  two values.
- **A positive half for every negative.** The leak test's new "no BrightPath in attachment names"
  would have passed if the guide vanished; it now also asserts the tenant-named guide is there on
  all nine sends (rule 1).

## For the owner

- **TD-145:** should a genuine offer from a demonstrably different university raise the pathway
  confirm for a one-campus course pick? Size it first with the lead's probe (T4/T6 are upper
  bounds).
- **Tamil (first draft):** `admin.payments.funding.walletNotLive`.
- **Still untenanted:** the contract-mode sign email (`send_award_offer_sign_email` in
  `sponsorship.py`) passes no branding — no attachment, so outside TD-169; dormant while the flag
  is off.
