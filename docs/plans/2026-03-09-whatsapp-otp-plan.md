# WhatsApp OTP Authentication — Design & Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable phone-based login via WhatsApp OTP alongside existing Google Sign-In, using Twilio as the SMS/WhatsApp provider through Supabase's custom SMS hook.

**Architecture:** Supabase Auth sends OTP requests to a custom SMS hook (Supabase Edge Function) which routes messages through Twilio's WhatsApp Business API. The frontend login page already has phone OTP UI — we just need a working provider behind it.

**Tech Stack:** Supabase Auth, Supabase Edge Functions (Deno), Twilio WhatsApp Business API, Next.js 14

**Estimated cost:** ~RM12/month (~$3 USD) for low-volume Malaysian WhatsApp messages (Twilio WhatsApp: $0.0042/msg utility, $0.005/msg auth template)

---

## Current State

The login page (`src/app/login/page.tsx`) already has:
- Phone number input with +60 Malaysia prefix
- 6-digit OTP verification flow
- `signInWithPhone()` and `verifyOTP()` in `src/lib/supabase.ts`
- Google OAuth as secondary option

**Problem:** Supabase phone auth has no SMS provider configured → "Unsupported phone provider" error.

**What we need:**
1. Twilio account with WhatsApp Business sender
2. Supabase Edge Function as custom SMS hook
3. Enable phone auth in Supabase dashboard
4. Minor frontend tweaks (WhatsApp branding)

---

## Pre-Requisites (Manual — User Action Required)

Before any code work, the user must complete these one-time setup steps:

### A. Twilio Account Setup
1. Create Twilio account at https://www.twilio.com/try-twilio (free trial includes $15 credit)
2. Get Account SID and Auth Token from Twilio Console dashboard
3. Enable WhatsApp Sandbox (Console → Messaging → Try it out → Send a WhatsApp message)
   - For production: Apply for WhatsApp Business Profile (takes 1-2 business days)
   - For testing: Use sandbox number (join sandbox by sending "join <word>" to Twilio sandbox number)
4. Note down: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` (e.g. `whatsapp:+14155238886` for sandbox)

### B. Supabase Phone Auth Configuration
1. Go to Supabase Dashboard → Authentication → Providers → Phone
2. Enable Phone provider
3. Set "SMS Provider" to "Hook" (not Twilio directly — we use a custom hook for WhatsApp routing)
4. Note: The custom hook will be configured after deploying the Edge Function

### C. Install Supabase CLI (if not already)
```bash
npm install -g supabase
supabase login
supabase link --project-ref pbrrlyoyyiftckqvzvvo
```

---

## Task 1: Create Supabase Edge Function for WhatsApp OTP

**Files:**
- Create: `supabase/functions/send-otp-whatsapp/index.ts`

**Step 1: Initialise Supabase functions directory**

```bash
cd C:/Users/tamil/Python/Development/HalaTuju
mkdir -p supabase/functions/send-otp-whatsapp
```

**Step 2: Write the Edge Function**

```typescript
// supabase/functions/send-otp-whatsapp/index.ts
import { serve } from "https://deno.land/std@0.177.0/http/server.ts";

const TWILIO_ACCOUNT_SID = Deno.env.get("TWILIO_ACCOUNT_SID")!;
const TWILIO_AUTH_TOKEN = Deno.env.get("TWILIO_AUTH_TOKEN")!;
const TWILIO_WHATSAPP_FROM = Deno.env.get("TWILIO_WHATSAPP_FROM")!;

interface SMSHookPayload {
  type: "sms";
  body: {
    phone: string;  // e.g. "+601234567890"
    otp: string;    // e.g. "123456"
  };
}

serve(async (req: Request) => {
  // Verify this is from Supabase (check webhook secret)
  const hookSecret = Deno.env.get("SMS_HOOK_SECRET");
  const authHeader = req.headers.get("authorization");
  if (hookSecret && authHeader !== `Bearer ${hookSecret}`) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const payload: SMSHookPayload = await req.json();
  const { phone, otp } = payload.body;

  // Format phone for WhatsApp (must be whatsapp:+<number>)
  const to = `whatsapp:${phone}`;
  const from = TWILIO_WHATSAPP_FROM;

  // Send via Twilio WhatsApp
  const twilioUrl = `https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json`;
  const credentials = btoa(`${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}`);

  const body = new URLSearchParams({
    To: to,
    From: from,
    Body: `Kod pengesahan HalaTuju anda: ${otp}\n\nYour HalaTuju verification code: ${otp}\n\nKod ini sah selama 5 minit. / This code expires in 5 minutes.`,
  });

  const response = await fetch(twilioUrl, {
    method: "POST",
    headers: {
      Authorization: `Basic ${credentials}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });

  const result = await response.json();

  if (!response.ok) {
    console.error("Twilio error:", result);
    return new Response(
      JSON.stringify({ error: "Failed to send WhatsApp message" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  return new Response(JSON.stringify({ success: true, sid: result.sid }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
```

**Step 3: Deploy the Edge Function**

```bash
supabase functions deploy send-otp-whatsapp --project-ref pbrrlyoyyiftckqvzvvo
```

**Step 4: Set Edge Function secrets**

```bash
supabase secrets set TWILIO_ACCOUNT_SID=<value> --project-ref pbrrlyoyyiftckqvzvvo
supabase secrets set TWILIO_AUTH_TOKEN=<value> --project-ref pbrrlyoyyiftckqvzvvo
supabase secrets set TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 --project-ref pbrrlyoyyiftckqvzvvo
supabase secrets set SMS_HOOK_SECRET=<generate-random-secret> --project-ref pbrrlyoyyiftckqvzvvo
```

**Step 5: Commit**

```bash
git add supabase/functions/send-otp-whatsapp/index.ts
git commit -m "feat: add WhatsApp OTP Edge Function via Twilio"
```

---

## Task 2: Configure Supabase Custom SMS Hook

**This is a dashboard/SQL configuration task — no code files.**

**Step 1: Enable phone provider in Supabase**

Go to Supabase Dashboard → Authentication → Providers → Phone:
- Enable Phone
- Set OTP expiry: 300 seconds (5 minutes)
- Set OTP length: 6

**Step 2: Configure custom SMS hook**

Go to Supabase Dashboard → Authentication → Hooks:
- Enable "Custom SMS Sender" hook
- Set hook type: "Edge Function"
- Select function: `send-otp-whatsapp`
- Set the hook secret (same as `SMS_HOOK_SECRET` above)

**Alternative — via SQL:**

```sql
-- Enable the hook via Supabase auth config
-- This may need to be done via Dashboard if SQL config is not supported
SELECT set_config('auth.sms_provider', 'hook', false);
```

**Step 3: Test with sandbox**

1. Open HalaTuju login page
2. Enter a phone number that has joined the Twilio WhatsApp sandbox
3. Click "Hantar Kod" (Send Code)
4. Check WhatsApp for the OTP message
5. Enter OTP → should redirect to dashboard

---

## Task 3: Update Frontend Login Page — WhatsApp Branding

**Files:**
- Modify: `halatuju-web/src/app/login/page.tsx`
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add WhatsApp icon and update copy**

The login page currently says "SMS" for the phone flow. Update to indicate WhatsApp:

In `login/page.tsx`:
- Change the phone section header/description to mention WhatsApp
- Add a small WhatsApp icon (green) next to the phone input section
- Keep the same `signInWithPhone()` call — Supabase handles the routing

**Step 2: Update i18n strings**

Add/update keys:

```json
// en.json
"login": {
  "phoneTitle": "Login with WhatsApp",
  "phoneSubtitle": "We'll send a verification code to your WhatsApp",
  "sendCode": "Send WhatsApp Code",
  ...
}

// ms.json
"login": {
  "phoneTitle": "Log masuk dengan WhatsApp",
  "phoneSubtitle": "Kami akan hantar kod pengesahan ke WhatsApp anda",
  "sendCode": "Hantar Kod WhatsApp",
  ...
}

// ta.json
"login": {
  "phoneTitle": "WhatsApp மூலம் உள்நுழைக",
  "phoneSubtitle": "உங்கள் WhatsApp-க்கு சரிபார்ப்புக் குறியீடு அனுப்பப்படும்",
  "sendCode": "WhatsApp குறியீடு அனுப்பு",
  ...
}
```

**Step 3: Run frontend build to verify**

```bash
cd halatuju-web && npm run build
```

**Step 4: Commit**

```bash
git add src/app/login/page.tsx src/messages/en.json src/messages/ms.json src/messages/ta.json
git commit -m "feat: update login page with WhatsApp OTP branding"
```

---

## Task 4: Test End-to-End Flow

**No files — manual testing task.**

**Test cases:**

1. **WhatsApp OTP happy path:**
   - Enter Malaysian phone number (+60...)
   - Receive WhatsApp message with OTP
   - Enter OTP → redirected to dashboard
   - Session is valid (can access /profile, /dashboard)

2. **Google Sign-In still works:**
   - Click Google button → OAuth flow → dashboard
   - No regression

3. **Invalid OTP:**
   - Enter wrong 6-digit code → error message shown
   - Can retry

4. **Expired OTP:**
   - Wait >5 minutes → enter code → error shown

5. **Non-Malaysian number:**
   - Enter non-+60 number → should still work (Twilio routes internationally)

6. **Backend JWT verification:**
   - Phone-auth JWTs should pass backend middleware (same Supabase Auth, same JWT format)
   - Test: login via WhatsApp, then access /profile API → 200

---

## Task 5: Deploy and Production Cutover

**Step 1: Apply for Twilio WhatsApp Business Profile**

- Twilio Console → Messaging → Senders → WhatsApp Senders
- Register HalaTuju as a WhatsApp Business sender
- Submit for approval (1-2 business days)
- Once approved: update `TWILIO_WHATSAPP_FROM` to production number

**Step 2: Deploy frontend**

```bash
cd halatuju-web
gcloud run deploy halatuju-web --source . --region asia-southeast1 --project gen-lang-client-0871147736 --allow-unauthenticated
```

**Step 3: Verify production**

- Test WhatsApp OTP on production URL
- Test Google Sign-In on production URL
- Check Twilio logs for delivery status

**Step 4: Commit and close**

```bash
git add -A
git commit -m "feat: WhatsApp OTP authentication via Twilio"
git push
```

---

## Cost Breakdown

| Item | Cost | Notes |
|------|------|-------|
| Twilio WhatsApp (auth template) | $0.005/msg | Per OTP sent |
| Twilio WhatsApp (utility) | $0.0042/msg | If using utility template |
| Twilio phone number | $1/month | Required for WhatsApp sender |
| Supabase Edge Function | Free | Included in free tier |
| **Estimated monthly** | **~$3-5** | Assuming 200-500 OTPs/month |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Twilio WhatsApp approval takes time | Use sandbox for testing; apply early |
| Student doesn't have WhatsApp | Google Sign-In remains available as fallback |
| WhatsApp rate limits | Supabase has built-in OTP rate limiting (60s cooldown) |
| Twilio outage | Google Sign-In unaffected; monitor Twilio status |
| Cost overrun | Set Twilio spending limit at $10/month |

## Architecture Diagram

```
Student → Login Page → "Send WhatsApp Code"
                            │
                            ▼
                    Supabase Auth (phone provider)
                            │
                            ▼
                    Custom SMS Hook
                            │
                            ▼
                    Edge Function: send-otp-whatsapp
                            │
                            ▼
                    Twilio WhatsApp API
                            │
                            ▼
                    Student receives WhatsApp message
                            │
                            ▼
                    Enter OTP → Supabase verifies → JWT issued
                            │
                            ▼
                    Redirect to /dashboard (authenticated)
```

## Dependencies on Existing Code

- `src/lib/supabase.ts` — `signInWithPhone()` and `verifyOTP()` already exist, no changes needed
- `src/app/login/page.tsx` — UI exists, only branding changes needed
- Backend JWT middleware — already supports Supabase Auth tokens (both HS256 and ES256), no changes needed
- `src/lib/auth-context.tsx` — session management works with any Supabase auth method, no changes needed
