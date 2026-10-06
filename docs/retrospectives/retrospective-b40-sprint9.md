# B40 Redesign — Sprint 9 Retrospective (2026-05-24)

Apply-form rebuild ① — **About Me + My Family** inline-editable with commit-on-submit. Branch
`feature/b40-redesign`, not deployed (single deploy at S12). Re-scoped on 2026-05-24 to these two sections only
(My Results' onboarding-return mechanism split out to S9b).

## What Was Built
- **About Me** (was a read-only "About You" with an Edit→/profile bounce) is now **inline-editable**, pre-filled
  from the profile: name, school, NRIC (editable until verified; read-only + "Verified" badge once locked),
  referring org (fixed dropdown), home state, phone. Contact email **locked**.
- **My Family**: exact household income (required) + household-definition tooltips, STR/JKM toggles with
  explainers, new parent/guardian **name + phone** (→ `profile.guardians`) and **preferred call language**
  (→ `profile.preferred_call_language`).
- **Commit-on-submit**: edits live in form state; on a successful submit the About-Me/Family fields sync to the
  canonical profile (`sync_profile_fields` extended), and the **NRIC commits via the validated claim path**
  (never the application payload). A failed submit persists nothing.
- Required `*` + `i` info-bubble tooltips (`InfoTip` + `FieldLabel`); validation jumps to the offending tab; the
  error banner moved to form level. Referring-org stored as `referral_source`, resolved to `referred_by_org` FK.
- EN/MS/TA i18n for every new label, tooltip, heading, option, and error. Backend: `ApplicationCreateSerializer`
  accepts the new write-only profile fields; profile GET returns `referral_source` + `guardians`.

## What Went Well
- The backend seam was tiny because the **write-back pattern already existed** — `sync_profile_fields` +
  the `referral_source`→`referred_by_org` resolution (already in `ProfileView`) extended cleanly. **No new
  migration** (every field already on `StudentProfile` from S7). Two new tests, full suite green first try.
- Pure helpers in `scholarship.ts` (state, defaults, payload, validation, `nricChanged`, constants) kept the page
  a thin renderer and let **27 node-env jest tests** cover the logic with no DOM.
- The auth-gated form was screenshotted via a **throwaway preview route** seeded with a sample profile — accurate
  visual approval without needing a real Supabase/Google session, then deleted.

## What Went Wrong
- **i18n files were in `src/messages/`, not `src/i18n/`.** *Symptom:* my first `node require('./src/i18n/en.json')`
  failed ENOENT after I'd "confirmed" the path. *Root cause:* my initial probe was `ls src/i18n/ || ls src/messages/`;
  the first branch failed silently (`2>/dev/null`) and the second branch's output was unlabelled, so I mis-attributed
  it to `src/i18n/`. *Fix → lessons.md:* don't probe a path with a chained `A || B` whose output doesn't say which
  branch ran; run one explicit check per candidate (or echo the resolved path).
- **The error banner only rendered inside the Support tab.** *Symptom:* with the new tab-jump validation, a
  name/income error would send the user to About Me / My Family but the message lived only in Support → invisible.
  *Root cause:* the original form only surfaced errors at submit on the last tab, so the banner was scoped there;
  adding mid-form validation broke that assumption. *Fix:* moved the error banner to **form level** (renders on
  whichever tab is active). Caught during the rewrite, before tests.
- **(Expected) the `baseForm()` jest helper lacked the new required fields**, so the older `applyFormError` tests
  would have failed. *Root cause:* S9 added required About-Me fields to a validation function shared by earlier
  tests — exactly the lessons.md#48 drift. *Fix:* updated `baseForm` + assertions in the same change; ran the full
  jest suite (44), not just the new cases.

## Design Decisions
- Commit-on-submit split (profile fields via the submit's `sync_profile_fields`; NRIC via the claim path) +
  fixed referring-org list stored as `referral_source` → FK. See `docs/decisions.md` (2026-05-24).

## Numbers
- Backend tests **1093 → 1095**; frontend jest **37 → 44**; i18n **1051 keys × 3** (parity green); `next build`
  clean. ~10 files. **No migration.** Desktop responsiveness deferred to S12 (user's call).
