# Identity, Authentication & Contact Verification — Design

**Date:** 2026-03-17
**Status:** Approved

## Problem

The profile notification badge counts are wrong (email not returned by API, Application Tracking section missing badge, badge doesn't refresh after save). More fundamentally, the system lacks a coherent identity model — login credentials, identity, and contact info are conflated.

## Core Principle

Three separate concerns:

| Concern | What it answers | Anchor |
|---------|----------------|--------|
| **Identity** | Who is this person? | NRIC (permanent, self-reported) |
| **Authentication** | How do they prove it? | Google OAuth / Phone OTP (Supabase Auth) |
| **Contact** | How do we reach them? | Email, phone (verified, editable) |

**NRIC owns the profile. Whoever holds the NRIC holds the data.**

## Identity Model

### NRIC as Identity Anchor

- NRIC is the permanent identifier for a student
- One NRIC = one profile = one student journey
- NRIC is self-reported (no electronic verification — no JPN API available)
- NRIC is required — no entry to the app without it
- Claim/reclaim model: last person to claim an NRIC gets the profile

### Claim/Reclaim Logic

- Student A enters NRIC → profile linked to that NRIC
- Student B enters same NRIC → "This NRIC has existing data. Is this yours?"
  - Yes → B gets A's profile (supabase_user_id updated to B's), A loses access
  - No → B re-enters correct NRIC
- A can reclaim later by entering the same NRIC again

No one is verified. No one is an imposter. Whoever has the NRIC has the keys. The data (grades, course preferences) isn't sensitive enough to warrant heavier protection.

### Why This Works for HalaTuju

- Temporary tool (6-12 months of use per student)
- No financial consequences
- Clean analytics: one NRIC = one student journey
- Students always know their NRIC (printed on MyKad)

## Authentication & Routing Flow

```
Fresh student lands
    │
    ▼
SPM/STPM → Grades → Dashboard (localStorage only, no account)
    │
    │ clicks "load more" / "save" / etc.
    ▼
┌─────────────────────┐
│  AUTH GATE           │
│  Google / Phone      │
└─────────┬───────────┘
          │
    ┌─────┴──────────┐
    │ HAS PROFILE    │ NO PROFILE
    │ (Auth ID found)│ (fresh login)
    ▼                ▼
  GRADE CHECK    ┌──────────┐
    │            │ NRIC GATE │
    │            └─────┬────┘
    │          ┌───────┴───────┐
    │        NRIC exists     NRIC new
    │          │                │
    │          ▼                ▼
    │     "Is this you?"    Create profile
    │      Yes → link       sync localStorage
    │      No → re-enter    to backend
    │          │                │
    │          ▼                ▼
    │       GRADE CHECK     GRADE CHECK
    │          │                │
    ▼          ▼                ▼
    HAS → Dashboard         HAS → Dashboard
    NO  → SPM/STPM          NO  → SPM/STPM
```

**Key:** localStorage remains the pre-auth data store. Students try before they commit. Backend sync happens at profile creation.

## Contact Verification

### Separation from Login

- Login email/phone = Supabase Auth (how you authenticate)
- Contact email/phone = profile fields (how counsellors reach you)
- These can be the same or different

### Email Verification Flow

1. Student adds/edits contact email on profile page
2. Django backend generates a verification token (UUID), stores in `EmailVerification` table with 24-hour expiry
3. Django sends verification email via Gmail SMTP (free, 500/day limit)
4. Student clicks link → Django verifies token → sets `contact_email_verified = true`
5. Profile shows green "Verified" badge

**Why Django sends the email (not Supabase Edge Function):**
The system that verifies should be the system that sends. One log stream, one set of secrets, one place to debug. Canonical practice.

### Phone Verification

Deferred. Requires Twilio (~RM12/month). Same pattern as email but with OTP instead of link.

### On Edit

When a verified field is edited, verification status resets to `false`. New verification triggered.

## Data Model Changes

### StudentProfile (modified fields only)

```
CURRENT                          PROPOSED
─────────────────────────────    ─────────────────────────────
supabase_user_id (PK)            supabase_user_id (PK, unchanged)
nric (optional)                  nric (unique constraint, required)
phone (plain text)               (removed — migrated to contact_phone)

(not stored)                     contact_email (blank)
(not stored)                     contact_email_verified (default false)
(not stored)                     contact_phone (blank)
(not stored)                     contact_phone_verified (default false)
```

**Why not change PK to NRIC:** Foreign keys from SavedCourse, Outcome, Report all reference supabase_user_id. Changing PK requires migrating all FK references — high risk for a live system. NRIC is the logical key enforced in application code; supabase_user_id stays as physical PK.

### EmailVerification (new table)

```
id              auto PK
nric            FK to StudentProfile
email           the email being verified
token           UUID, unique
created_at      auto
expires_at      created_at + 24 hours
used            boolean, default false
```

## Profile Page Changes

### Section Redesign

1. **Personal Details** — IC (locked/masked), Name, Gender, Nationality
2. **Contact Details** (new section) — Login method (display only), Contact Email (with verify), Contact Phone (with verify)
3. **Contact & Location** — State, Address
4. **Family & Background** — Income, Siblings, Colour Blindness, Disability
5. **Application Tracking** — Angka Giliran

### Completeness Badge

`useProfileCompleteness` checks: `name`, `nric`, `gender`, `preferred_state`, at least one verified contact method, `family_income`, `siblings`, `address`, `angka_giliran`.

## Scope

| # | What | Effort | Priority |
|---|------|--------|----------|
| 1 | NRIC uniqueness constraint + claim/reclaim logic | Medium | Must have |
| 2 | Login routing update (profile check → NRIC gate → grade check) | Medium | Must have |
| 3 | contact_email / contact_phone fields + verified flags | Small | Must have |
| 4 | Email verification flow (send link, verify token) | Medium | Must have |
| 5 | Profile page redesign (contact section, login method, verify buttons) | Medium | Must have |
| 6 | Completeness hook update | Small | Must have |
| 7 | Phone verification via OTP | Medium | Deferred (Twilio cost) |
| 8 | Migrate existing phone data to contact_phone | Small | Must have |

## Not in Scope

- Changing physical primary key to NRIC
- Phone login implementation (separate feature)
- Admin-assisted account recovery
- Electronic NRIC verification (JPN)

## Immediate Bug Fixes (Done)

These fixes were made during investigation and are consistent with the design:

1. Backend returns `email` from JWT in profile GET response
2. Header badge refreshes after profile save (profile-updated event)
3. Application Tracking section shows incomplete badge
