# WhatsApp Channel — Go-Live Checklist (interview reminders)

**Date:** 2026-06-20 · **For:** tamiliam (owner steps) + engineer (deploy steps)
**Goal:** take the built-and-proven WhatsApp channel (Sprints 1–2, branch `feat/whatsapp-comms`) LIVE so the
**99 B40 applicants** get interview reminders on WhatsApp alongside email.
Companion to `docs/plans/2026-06-20-whatsapp-comms-channel.md` + `docs/whatsapp-setup-guide.md`.

> **Why there's a code step too:** the sandbox accepts free-text, but a **production** business-initiated WhatsApp
> message (one *we* start, like a reminder) **must use a Meta-approved template**. Our `send_whatsapp` currently sends
> free text — so go-live includes a small change to send via the approved template's `ContentSid`. Sequenced below.

---

## Stage 1 — Owner: production WhatsApp sender (~1–2 days, mostly waiting on Meta)

- [ ] **Buy a dedicated Twilio number** (the chosen approach). Twilio Console → **Phone Numbers → Manage → Buy a
      number** → pick one with the **SMS** capability → Buy (~US$1–2/month). This becomes the WhatsApp sender; it's
      never used on a phone's WhatsApp app, so nothing of yours gets taken over.
      - *Needs the account upgraded from Trial → Pay as you go first (adds a card) — see the spending-cap step below.*
      - *A US number is fine — applicants see the approved "HalaTuju" display name, not the raw number. (Malaysian
        numbers can need extra regulatory documents, so don't block on one.)*
      - *Alternative if you'd rather: a spare SIM / business line not on WhatsApp (must receive the verification OTP).*
      - *Do NOT use your personal WhatsApp number.*
- [ ] Twilio Console → **Messaging → Senders → WhatsApp senders → Create new sender.**
- [ ] Connect/create a **Meta Business (Facebook Business Manager)** account when prompted; complete **business
      verification** (Meta reviews — 1–2 business days).
- [ ] Set the **display name** to `HalaTuju` (Meta reviews the name).
- [ ] Twilio Console → **upgrade from Trial → Pay as you go** (adds a payment method) and set a **spending cap**
      (e.g. US$10/month) as a hard stop.

## Stage 2 — Owner: approve the interview-reminder template

- [ ] Twilio Console → **Messaging → Content Template Builder → Create** (Category: **Utility**).
- [ ] Create it in **English** and **Bahasa Melayu** (two language versions of the same template).
- [ ] Submit for WhatsApp/Meta approval (~1–2 days). When approved, **copy the `ContentSid`** (`HX…`) and send it
      to the engineer (securely — it's not secret, but keep it tidy).

**Suggested template text** (variables: `{{1}}`=name, `{{2}}`=date & time MYT, `{{3}}`=join link)

> **EN:** `Hi {{1}}, a reminder: your B40 Assistance interview is on {{2}}. Join here: {{3}}`
> **BM:** `Salam {{1}}, peringatan: temu duga Bantuan B40 anda pada {{2}}. Sertai di sini: {{3}}`

(Keep it utility/transactional — no marketing language — so it qualifies for the cheaper Utility category.)

## Stage 3 — Engineer: wire the template send (small, ~3 files)

- [ ] Add `TWILIO_WHATSAPP_REMINDER_CONTENT_SID` setting (env-driven, blank default).
- [ ] In `whatsapp.py`, when a `content_sid` is provided, POST `ContentSid` + `ContentVariables` (JSON of the
      numbered vars) instead of `Body`; keep the `Body` path for sandbox/dev (no SID set).
- [ ] In `send_interview_reminders`, pass the reminder `ContentSid` + `{1:name, 2:MYT time, 3:link}`.
- [ ] Tests for the template-send path; `next build` n/a (backend only).

## Stage 4 — Engineer: deploy (migrate-first, then flip)

- [ ] **Apply migrations to prod via Supabase MCP** (deploy doesn't migrate):
  - `0059` (additive `whatsapp_opt_in` on `api_student_profiles`) — `ADD COLUMN … NOT NULL DEFAULT true` then `DROP DEFAULT` (backfills existing 99 to on).
  - `0067` (new `whatsapp_messages` table) — **new model**, so use the **TD-058 contenttypes workaround** + **enable RLS** (service-role-only, deny-by-default) in the same transaction. Verify columns + the `django_migrations` rows.
- [ ] **Set Cloud Run env vars** on `halatuju-api` (never in code):
      `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM=whatsapp:<prod sender>`,
      `TWILIO_WHATSAPP_REMINDER_CONTENT_SID=HX…`.
- [ ] **Merge/push** `feat/whatsapp-comms` → `main` (triggers the Cloud Build deploy). Confirm the api build = SUCCESS.
- [ ] **Flip the flag:** `--update-env-vars WHATSAPP_ENABLED=1` (new revision). Keep it off until everything above is green.

## Stage 5 — Verify + rollback

- [ ] **Smoke:** trigger one real interview reminder (or run the `interview-reminders` cron) to a test applicant whose
      number you control; confirm the WhatsApp arrives AND the email still sends; check the `whatsapp_messages` row = `sent`/`delivered`.
- [ ] **Watch** the first real bookings' reminders land; check Twilio logs for delivery failures.
- [ ] **Rollback (instant):** `--update-env-vars WHATSAPP_ENABLED=0` → every send no-ops again; email unaffected.

## Cost
Utility message to Malaysia ≈ **RM0.09 each** → single-digit ringgit/month at pilot volume. The spending cap is the backstop.

## Follow-ups (not blocking go-live)
- Add a one-line **WhatsApp mention to the privacy/consent copy** (transparency for implied consent).
- Record an inbound **"STOP"** back into `whatsapp_opt_in` (small webhook) — Twilio honours STOP natively meanwhile.
- Tighten later: t="utility" template only; revisit if more message types are added (Sprint 3 sponsor comms / Sprint 4 payment).
