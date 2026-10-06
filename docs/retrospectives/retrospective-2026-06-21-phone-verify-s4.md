# Retrospective — Phone verification over WhatsApp (S4 / TD-136) + S5 close

**Date:** 2026-06-21 · **Branch/worktree:** `feat/whatsapp-comms` (`.worktrees/wa-comms`) · **Commit:** `5be1123` → main
**Roadmap:** `docs/plans/2026-06-21-whatsapp-and-scheduling-followups.md` (S4 ✅ built, S5 ✅ deployed)

## What shipped
The last two items of the WhatsApp/scheduling roadmap.

**S4 — phone verification (Twilio Verify, WhatsApp channel, opt-in/voluntary).** Owner decision (2026-06-21):
verify over **WhatsApp**, **opt-in only** — a "Verify my number" control in /profile, nothing gated or forced.
- **Backend:** `whatsapp.start_phone_verification` / `check_phone_verification` (urllib, Verify v2, never-raise —
  Twilio holds the code + enforces its lifecycle/rate limits, so **no DB model, no migration**). New
  `TWILIO_VERIFY_SERVICE_SID` setting. `PhoneVerifyStartView` + `PhoneVerifyCheckView`
  (`POST /api/v1/profile/verify-phone/{send,check}/`, self-scoped, 5-sends/hour soft cache cap; status mapping:
  unconfigured→503, invalid_number→400, transport→502). On a confirmed code → `contact_phone_verified=True`
  (persists a newly-typed number). `contact_phone_verified` already existed (reset on phone change).
- **Frontend:** `sendPhoneVerification`/`checkPhoneVerification` clients + a code-entry control in Contact Details
  (Verify my number → enter code → Confirm → ✓ Number verified); editing the number un-verifies it. i18n en/ms/ta.
- **Tests:** +13 — Verify unit tests in `test_whatsapp.py` (configured flag, unconfigured, bad number, normalised
  WhatsApp send, approved/wrong/expired-404/error check) + `test_phone_verification.py` view flow (saved-phone send,
  missing-phone 400, unconfigured 503, rate-limit after 5, correct→verified, persists new number, wrong→400, missing
  code 400, unconfigured 503).

**S5 — STOP→opt-out webhook.** Code already deployed earlier in the session (endpoint live: GET→405, unsigned POST→403,
5 webhook tests green). No further code needed.

## Gates
2625 backend pytest (scholarship + courses) · 365 jest (incl. i18n parity) · `next build` clean · NO migration.

## Decisions / notes
- **No DB for OTP.** Twilio Verify is stateful on Twilio's side — storing codes ourselves would duplicate state and add
  a migration for no benefit. We keep only the boolean outcome (`contact_phone_verified`).
- **Rate-limit is soft (cache) + Twilio hard.** A per-profile cache counter (5/hour) is best-effort (LocMemCache isn't
  shared across Cloud Run instances); Twilio Verify's per-number limits are the real backstop. Acceptable for a
  low-traffic, opt-in, self-serve action.
- **Behind the NRIC gate, like verify-email.** A student verifies their phone after establishing identity; no
  middleware whitelist change.

## Owner actions to activate (both are Twilio console; I can't do them)
1. **S4:** create a Twilio **Verify Service** with the **WhatsApp** channel enabled → give me the `VA…` SID → I set
   `TWILIO_VERIFY_SERVICE_SID` on halatuju-api + smoke-test. (Small per-verify cost.)
2. **S5:** set the WhatsApp sender's **inbound webhook URL** →
   `https://halatuju-api-90344691621.asia-southeast1.run.app/api/v1/scholarship/whatsapp/inbound/` (POST).

## Parked (owner)
WhatsApp display name: Meta rejected "HalaTuju"; owner plans to rebrand the programme to **"BrightPath Bursary"** but
left it as-is for now. Account is owned by **Tamil Foundation** (registered entity) → green-badge path open later.
Free quick win still open: set profile photo/logo + description + website in Meta Business Manager.
