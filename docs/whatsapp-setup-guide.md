# Twilio + WhatsApp — Owner Setup Guide (HalaTuju)

**For:** tamiliam · **Date:** 2026-06-20 · **Goal:** stand up the WhatsApp comms channel.
Companion to `docs/plans/2026-06-20-whatsapp-comms-channel.md`.

You do the account/owner steps below; the engineer does all the code. There are **two stages** —
you only need **Stage 1** to start; Stage 2 is for going live to real applicants later.

---

## Before you start
- Sign up with a **dedicated HalaTuju email**, NOT your personal Gmail (so it can transfer to an org later).
- Nonprofit pricing (Twilio.org) is **N/A for now** — HalaTuju has no registered entity yet. Revisit later.
- **Never paste the Account SID / Auth Token into chat.** Send them via a secure channel; the engineer
  stores them as Cloud Run environment variables, never in code.

---

## STAGE 1 — Free testing (no organisation needed, ~30 min)

### 1. Create the account
- Go to **twilio.com/try-twilio**.
- **Account friendly name:** `HalaTuju`
- **What will this account be used for?** → **Twilio** (SMS, Voice, Verify, Lookup). *Not Flex.*
- Continue.

### 2. Onboarding questions (answer roughly — nothing locks you in)
- What do you want to do first? → **Send or receive a message** / **WhatsApp**
- Which product? → **Messaging**
- Do you write code? → **Yes** (or "with help") — doesn't matter
- Preferred language → anything (e.g. Python). You can skip/▸ through these.

### 3. Verify your email + phone
- Twilio sends an email code and an SMS code to confirm you're real. Enter both.

### 4. Find your keys (the important bit)
- You land on the **Console dashboard** (console.twilio.com).
- On the main page, under **Account Info**, you'll see:
  - **Account SID** (starts with `AC…`)
  - **Auth Token** (hidden — click to reveal)
- Copy both → send to the engineer **securely** (not in chat).

### 5. Turn on the WhatsApp Sandbox (for testing)
- Left menu: **Messaging → Try it out → Send a WhatsApp message**.
- You'll see a **sandbox number** (e.g. `+1 415 523 8886`) and a **join code** (e.g. *"join velvet-tiger"*).
- On YOUR phone's WhatsApp, send that exact `join …` message to the sandbox number.
- You'll get a "connected" reply. Now your number can receive test messages.
- (Add a couple of test numbers — e.g. your own + one colleague — the same way.)

✅ **That's all the engineer needs to build and test Sprint 1.** Stop here for now.

---

## STAGE 2 — Going live to real applicants (later, only when ready)

Don't do these until the pilot has been tested and you've decided to switch it on.

### A. Decide the sender phone number
- You need a **dedicated number** for the "HalaTuju" WhatsApp sender.
- ⚠️ It **must NOT already be on the normal WhatsApp app**. Don't use your personal WhatsApp number.
- Options: buy a Twilio number, or use a spare SIM number not registered on WhatsApp.

### B. Register the WhatsApp Sender
- Console: **Messaging → Senders → WhatsApp senders → Create**.
- Twilio walks you through connecting a **Meta / Facebook Business** account (Business Manager).
  - You can create one as an individual, but a registered entity makes verification smoother.
- Meta verifies number ownership (SMS/voice code) and reviews the **display name** ("HalaTuju").
- Approval typically takes **1–2 business days**.

### C. Get message templates approved
- Business-initiated WhatsApp messages must use **pre-approved templates** (you can't free-text blast).
- The engineer will draft the templates (e.g. interview reminder, in EN + BM); you submit them in the
  Twilio/Meta console for approval (utility category, ~1–2 days).

### D. Upgrade + set a spending cap
- Add a payment method (upgrades from trial → removes the "sent from trial" tag + verified-number limit).
- Set a **spending cap** (e.g. US$10/month) as a hard stop. Pilot volume is single-digit ringgit/month.

---

## Quick reference — what the engineer needs from you
| When | What | How |
|---|---|---|
| To start (Stage 1) | Account SID + Auth Token | Securely (not in chat) |
| To start (Stage 1) | Confirm sandbox joined from a test phone | Just tell me it's done |
| To go live (Stage 2) | Approved sender + approved template(s) | After Meta approval |
| To go live (Stage 2) | Dedicated sender phone number | Decide which number |

## Glossary (plain English)
- **Account SID / Auth Token** — your account's username/password for the API. Keep secret.
- **Sandbox** — a free shared test line; works instantly but only to numbers that "join" it.
- **Sender** — your own branded "HalaTuju" WhatsApp number for real messages (needs approval).
- **Template** — a pre-approved message format; required for messages you start (vs replies).
