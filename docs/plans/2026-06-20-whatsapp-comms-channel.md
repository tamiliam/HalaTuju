# WhatsApp Comms Channel — Implementation Roadmap

**Date:** 2026-06-20 · **Status:** roadmap for approval (do NOT start Sprint 1 until approved)
**Supersedes:** `2026-03-09-whatsapp-otp-plan.md` (that plan targeted *login*, which is low-ROI since
~600 students already use Google Sign-In; this plan targets *outbound comms*, the higher-value goal).
**Provider:** Twilio (chosen) · **Author:** Engineering with tamiliam

---

## Goal

Add an **outbound WhatsApp notification channel** alongside the existing email-only comms, so HalaTuju
can reliably reach applicants (and sponsors) who don't check email. Start with a small, flag-gated pilot.

## Why now (feasibility — checked against the live DB, 2026-06-20)

- **100% of B40 applicants (99/99) have a phone number on file** (the apply form collects it).
- Numbers are **clean and uniform**: 98 in `0XX-XXXXXXX` form, 1 already `+60`, none malformed →
  normalisation to E.164 (`+60…`) is a trivial deterministic transform.
- **Gaps to close:** numbers are **unverified** and **no WhatsApp consent is captured** yet.
- Comms today are **email-only** (Brevo SMTP, `apps/scholarship/emails.py`); the B40 invite campaign
  saw ~63% email open-rate — a third never opened. WhatsApp closes that gap.

## Scope (chosen message types)

| Message | When | Audience | Phase |
|---|---|---|---|
| **Interview reminder** | pilot (now) | applicant | Sprint 1 |
| **Sponsor comms** (e.g. impact/acknowledgement) | after pilot | sponsor | Sprint 3 |
| **Payment notice** ("RM300 sent") | later | awardee | Sprint 4 (gated on disbursement existing) |

*Out of scope for now:* shortlisted/decision notifications, two-way chat, a full notification platform.

---

## Architecture (thin, not a rebuild)

- **Send helper** in the API (`apps/comms/` or alongside `emails.py`): one function that POSTs an
  approved template to Twilio's WhatsApp API. Dark by default behind `WHATSAPP_ENABLED`.
- **Phone normalisation** util (`0XX…` → `+60XX…`), deterministic + unit-tested.
- **Approved templates** only — WhatsApp forbids free-text business-initiated messages. Each message
  type = one Meta-approved "utility" template (owner-submitted; ~1–2 day approval).
- **Consent + opt-out** (PDPA): a `whatsapp_opt_in` flag per recipient; every send gated on it; honour
  STOP/opt-out.
- **Delivery logging**: a `WhatsAppMessage` row (recipient, template, status, Twilio SID, error,
  timestamps) + Twilio status-callback webhook → auditable, mirrors WAT's audit principle.
- **Sends run alongside the existing email**, not instead of it (belt-and-braces during pilot).

---

## Owner pre-flight (one-time, before Sprint 1 — you drive, I can't)

1. Create a **Twilio account**; note Account SID + Auth Token.
2. Register a **WhatsApp Business sender** for HalaTuju (Twilio → Senders); submit for approval (1–2 days).
   Use the **sandbox** number for dev testing meanwhile.
3. Submit the **interview-reminder utility template** (EN+BM) for approval.
4. Set a **Twilio spending cap** (e.g. $10/month) as a hard stop.
5. Hand me the credentials → I store them as Cloud Run env vars (never in code, per Secrets Policy).

## Cost (pilot volume)

Utility message to Malaysia ≈ **$0.019/msg** (Meta ~$0.014 + Twilio ~$0.005) ≈ **RM0.09/msg**.
At ~100 applicants × a few messages/month → **single-digit ringgit/month**. Well within budget.
(Optimisation for later: a flat-fee BSP like 360dialog removes Twilio's per-msg markup at higher volume.)

---

## Sprint roadmap

### Sprint 1 — Foundation + first live message (interview reminder)
- **Goal:** prove the whole pipe end-to-end with one real message type, flag-gated.
- **Scope:** phone-normalisation util (+tests) · Twilio WhatsApp send helper (`WHATSAPP_ENABLED`,
  env creds) · `WhatsAppMessage` model + migration · Twilio status webhook · wire the
  **interview-reminder** send next to the existing email in `send_interview_reminders` /
  `emails.py` · tests · CHANGELOG/decisions.
- **Acceptance:** with flag on + a consenting test number, an interview reminder arrives on WhatsApp and
  is logged with delivery status; flag off → email-only behaviour unchanged; normalisation unit-tested.
- **Complexity:** medium-high (this carries the foundation). ~15–20 files.
- **Blocker:** owner pre-flight (creds + approved template). Dev uses the sandbox.

### Sprint 2 — Consent capture + opt-out (PDPA) + go-live to real applicants
- **Goal:** make it lawful and safe to message real applicants, then flip the flag on.
- **Scope:** `whatsapp_opt_in` field + capture in apply form/profile · opt-out (STOP keyword + UI
  toggle) · normalise + backfill existing 99 numbers · consent gate on all sends · PDPA note in
  decisions · tests.
- **Acceptance:** a user can opt in/out; no message sends without consent; existing numbers normalised;
  interview reminders go to consenting real applicants.
- **Complexity:** medium. ~12–15 files.

### Sprint 3 — Sponsor comms
- **Goal:** reach sponsors on WhatsApp for 1–2 high-value moments.
- **Scope:** sponsor `whatsapp_opt_in` · define + (owner) approve a sponsor template (impact/ack) ·
  wire 1–2 sponsor events alongside email · tests · docs.
- **Acceptance:** a consenting sponsor receives the sponsor WhatsApp message; logged; email still sent.
- **Complexity:** medium. ~10–12 files.

### Sprint 4 — Payment notice (LATER — gated)
- **Goal:** notify awardees when a disbursement is sent.
- **Scope:** wire the payment-sent event to the WhatsApp helper.
- **Dependency:** requires the **disbursement feature** (recipient-portal roadmap, Sprint D) to exist first.
- **Acceptance:** on a recorded payment, a consenting awardee gets a "payment sent" WhatsApp + email.
- **Complexity:** low (foundation already built). ~5 files.

### Sprint 5 — (Optional, future) channel abstraction
- Only if more event types pile up: refactor email+WhatsApp behind a `Notification` dispatcher.
  Not needed for the pilot.

---

## Sequencing & rationale
Foundation + riskiest external blocker (template/sender approval) first (S1), then the legal gate that
unlocks real-user sending (S2), then sponsors (S3). Payment (S4) waits on the separate disbursement
work. **3 sprints to a useful live channel; 1 more later.** Each sprint is a vertical slice, well under
the file-touch budget.

## Risks
| Risk | Mitigation |
|---|---|
| Template/sender approval delay | Owner submits early; dev on sandbox; Google/email unaffected |
| Number not WhatsApp-reachable | Email still sends; delivery webhook flags failures |
| Consent/PDPA | No send without `whatsapp_opt_in`; opt-out honoured; logged |
| Cost overrun | Twilio spending cap; pilot is single-digit RM/month |
| Vendor lock-in | Send helper is thin; can swap to a local BSP later |

## Open decisions / what I need from you
1. Approve this roadmap (or adjust scope).
2. Confirm you'll do the owner pre-flight (Twilio + WhatsApp Business + template + spending cap).
3. Sponsor message — what should it actually say? (impact update? donation acknowledgement? both?)
