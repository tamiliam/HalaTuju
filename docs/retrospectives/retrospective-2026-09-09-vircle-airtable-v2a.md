# Retrospective — Vircle Airtable V2a: the student stops typing the wallet id (2026-09-09)

## What was asked

Owner: **"go v2a"** — the second half of the Vircle Airtable plan approved earlier the same day.
V1 (the two webhooks) was deployed and verified with Vircle's Gokula end-to-end; V2a removes the
student-facing wallet-ID box now that the id arrives from Vircle's own Airtable callback.
Scope as approved: **remove the box; keep the 48-hour activation email and the relay sheet as
backstops.** V2b (retiring the 48h email) waits for the first real student to flow through with
`AUDIT vircle_id_set … by=vircle-airtable` in the logs.

## What shipped

- **`ActionCentre.tsx` — `VircleTask` is mobile-only.** The `suffix` state, `VIRCLE_PREFIX` /
  `SUFFIX_LEN` constants, the assembled-id echo and the DuitNow-specific error branch are deleted.
  The component docstring says why and says "do not add the box back".
- **Five i18n keys retired** in en/ms/ta: `walletId`, `walletIdHint`, `walletIdEcho`,
  `walletIdCheck`, `errorDuitnow` under `scholarship.actionCentre.vircle` (the orphan-key
  guardrail requires all three locales to move together).
- **`views.py` — `vircle_id` on the Vircle resolve is OPTIONAL.** Absent or empty resolves the
  task and stores nothing; the Airtable callback fills the field. Supplied-but-bad is still a
  400 with the `duitnow`/`format` reason — an old cached bundle may still send a value, and
  storing a wrong id silently is worse than refusing it.
- **`api.ts` — `resolveResolutionItem`'s `vircleId` parameter stays** (the server still accepts a
  value), with the comment updated so nobody re-wires it thinking the omission is a bug.
- **Emails** — award-email STEP 2 (en/ms/ta) and the standalone install email's Action-Centre
  paragraph no longer send the student hunting the id behind the gear icon; both now say Vircle
  sends us the details directly. `_BOLD_PHRASES` loses its 'eWallet ID'/'ID eWallet' entries.
  Email goldens regenerated (`UPDATE_EMAIL_GOLDEN=1`) — an owner-approved copy change.
- **Guards**:
  - `ActionCentre.vircle.test.ts` (new, jest) — a source-shape guard: no `vircle-id` input, no
    `walletId`/`VIRCLE_PREFIX`/`SUFFIX_LEN`/`errorDuitnow` in the component; the five keys gone
    from all three locales; the mobile field and confirm still present. Structural claim →
    source guard is the right tool (the repo's own testing note).
  - `test_vircle.py::TestConfirm` — `test_missing_vircle_id_is_rejected` is REPLACED by
    `test_missing_vircle_id_resolves_and_stores_nothing` + `test_empty_vircle_id_resolves_too`;
    `test_bad_vircle_id_is_rejected` stays.
  - `test_sponsorship.py` — the old D10 guard (every language must carry the eWallet-ID ask) is
    INVERTED: `test_award_offer_email_no_longer_asks_for_the_wallet_id` asserts the gear-icon
    hunt is ABSENT and the "Vircle sends us your eWallet details" promise present, per language.
    When a capability is removed, the guard that demanded it must flip, not vanish.

## What must not be "tidied"

- **⚠ SUPPLIED-BUT-BAD IS STILL REFUSED.** Do not "simplify" the optional branch into ignoring a
  bad value — the band check is what caught three DuitNow numbers in the first 46 students.
- **⚠ THE 48H ACTIVATION EMAIL AND THE RELAY SHEET STAY** (owner ruling). They are the backstop
  until the webhook pair is proven on a real student. Their tests
  (`TestPendingActivation`, `TestActivationEmail`, the relay-row suite) are untouched.
- **⚠ THE INVERTED EMAIL GUARD IS AN ABSENCE CHECK.** A presence grep cannot verify a removal —
  the same lesson as the gift-code `codeWarning` correction earlier this week.
- **The payments CSV, relay sheet and activation email still speak "eWallet ID"** — those are
  operator/Vircle surfaces, not student asks. Do not sweep the phrase out of them.

## Verification

- pytest **6082** (full `apps/`, 0 failures); jest **1925** (+6); tsc **24** (baseline);
  lint **0 errors**; i18n **4914 × 3** (−5 keys); `next build` exit 0;
  `makemigrations --check` clean. **NO migration.**
- **Three bite-checks, each verified to bite and restored to green:**
  1. Optional-id branch disabled (`if vircle_id:` → `if True:`) → both new resolve tests failed.
  2. "gear icon" injected back into the en award email → the inverted email guard failed.
  3. `walletId` injected into `ActionCentre.tsx` → the new source guard failed.

## Lessons

1. **Flip a guard when you flip a behaviour.** The D10 test existed precisely to stop the
   eWallet-ID ask being dropped; V2a drops it on purpose, so the test had to be inverted with the
   new rationale in its docstring — deleting it would have left the removal unguarded in the
   other direction.
2. **A removal has more homes than the component.** The box lived in one file, but the ASK lived
   in two email bodies, a bold-phrase table, five i18n keys × 3, an api-client parameter and two
   test guards. Grep for the capability's NAME, not the component's.
