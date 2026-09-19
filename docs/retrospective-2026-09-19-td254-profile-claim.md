# Retrospective — TD-254 + TD-259: the IC claim is rebuilt as a link, behind a second factor

**Date:** 2026-09-19 · **Ordered by the owner** (*"Fix the two TDs first and then continue on with
H7"*) under the development freeze's security exception. Not a roadmap sprint.
**Built by:** an Opus 5 agent to a written brief; the lead investigated production first, read the
authentication change line by line, re-ran every gate, applied the migration to production, and closed.

## What Was Built

- **The endpoint never names the holder.** `POST /profile/claim-nric/` answers an IC that belongs
  to somebody else with `{"status":"exists","channels":[…]}` — exactly those two keys, bare channel
  types, no name, no digits.
- **A claim is a LINK, not a move.** A verified claim writes one `ProfileLoginAlias` row: *this
  login acts as that profile*. Nothing is copied or re-keyed. `SupabaseAuthMiddleware` — the one
  place `request.user_id` is set — resolves it, so every student endpoint follows, including ones
  not yet written. Deleting the row undoes the claim completely (`revoke_alias`).
- **A second factor the real owner holds.** A code to a contact **already on the target profile
  and already verified**: WhatsApp via Twilio Verify, or a hashed 6-digit email code (10 minutes,
  five attempts) through the metered email seam. One function, `claim_channels(profile)`, holds the
  policy — the owner's two open rulings (unverified contacts; phone when email is lost) widen it
  there, in one place.
- **Every touch is audited.** `ProfileClaimEvent`, append-only: the real caller, the target, the
  IC, the event, the channel. The plain look-up is recorded too — *"has anyone been probing ICs?"*
  has an answer for the first time.
- **The old door is removed.** `confirm: true` is refused; the raw-SQL primary-key move is deleted.
- **Staff and sponsors are fenced off in three layers.** `PartnerAdmin` and `Sponsor` key on the
  same Supabase uid as a student. They now resolve on `request.auth_sub` (the real subject); the
  seam refuses to redirect such a subject, re-checked per request; alias creation refuses one.
- **TD-259:** all `authGate` copy written for the new flow in EN / MS / TA, with no holder name;
  the four other raw keys fixed; **`KNOWN_MISSING` is empty.** A `tOr(t, key, fallback)` helper
  replaces the `t(k) || '…'` idiom, and a hard-zero standard in the gate stops it returning.

## What Went Well

- **Investigating production before designing changed the design.** The five foreign keys to the
  profile table are `ON UPDATE NO ACTION`, four of them not deferrable — so the old transfer **could
  never succeed** for a target with a scholarship application or any saved course. The 143
  applicants had been protected by an `IntegrityError`, not by a rule. Repairing that SQL would
  have meant proving FK ordering on Postgres with a SQLite test suite. A link needs no ordering at
  all, is fully testable on SQLite, and is reversible. The lead would not have chosen it without
  the query.
- **The agent found the flaw in the lead's design before it shipped.** Rewriting `user_id` at the
  seam would have pointed an *admin's* own-account look-up at a student profile. It stopped,
  reported it, and fenced it three ways. It then caught a second one in its own first pass: the
  claim views must act as the REAL login, or a student who had already claimed could file a second
  claim *as* the profile they had claimed.
- **Tests first, seen red, and the red run earned its keep** — the `already_claimed` failure is what
  exposed the defect above. Six bite-checks, six red, each on a named test.
- **Migrate-first, verified:** tables created with RLS and one `service_role` policy each, ledger
  at 75 rows for 75 files, Security Advisor clean of errors, all before the push.

## What Went Wrong

**1. The original TD-254 entry overstated the exposure, and the lead wrote it.**
- *Symptom.* It said a confirm "transfers the whole profile… the scholarship application included".
- *Root cause.* Read from the code, never tried. The constraint rules in the database say the
  transfer raises for any target with child rows. The **name disclosure** was real for all 674
  profiles; the **takeover** was real only for near-empty ones.
- *System change.* The entry's resolution paragraph records the correction. Lesson filed: a
  security finding states what was *demonstrated* and what was *inferred*, separately.

**2. Ninety per cent of students still have no self-service path — by policy, and with no tool
behind it.** Only 70 of 674 IC-holding profiles have a verified contact. The rest are told to write
to support, and **support has no screen for it** — only `revoke_alias` and the database. Filed as
**TD-260**. This is the honest cost of the conservative reading; the owner's two rulings decide how
much of it to buy back.

**3. One more query on every authenticated request.** Deliberate and uncached — a stale cache
would keep a revoked login working. Recorded for H18's query budget.

## Owner review requested

The Tamil copy (table in the agent's report, now in `ta.json`). The lead changed one thing:
"WhatsApp" is written in Latin script, matching the six existing uses in Tamil copy. Flagged by the
agent for the owner's eye: "உள்நுழைவு" for *login*; "அந்தக் குறியீடு தவறானது" rather than the
warmer "சரியில்லை"; "உறுதிப்படுத்தவும்" for *Confirm*.

## Numbers

| Gate | Before | After |
|---|---|---|
| pytest `-n auto` | 6,803 | **6,857 passed · 3 skipped · 0 failed** |
| jest | 2,511 / 137 | **2,565 / 140** · Node 18 green |
| tsc · lint · i18n parity · `next build` | | 0 · 0 errors · ok (5,378 keys) · exit 0 |
| Standards budgets | | one moved, and it TIGHTENED: `courses/views.py` 2,377 → 2,309 |
| Migration | | `courses/0075`, additive, applied migrate-first with RLS |
