# Retrospective — v2.19.0: Four rejection buckets + differentiated decline emails

**Date:** 2026-05-31
**Version:** 2.19.0
**Migration:** `scholarship/0029` (additive — `rejection_category` + `rejected_at`/`rejected_by`), applied migrate-first via Supabase MCP.

This sprint started from a user observation during the previous one: a rejected applicant still showed the (irrelevant) Review & actions panel. Pulling that thread revealed there was no way to reject *after* the interview at all — the funnel only moved forward to `accepted`. The user then specified four rejection buckets, each with a slightly different email.

## What Was Built

Rejections are now **categorised**, and each bucket gets its own decline email:

| Bucket | Set by | When | Email |
|---|---|---|---|
| **merit** | engine | academic floor not met | suggestive — "competitive on academic results" |
| **need** | engine | financial-need test not met | suggestive — "greatest financial need prioritised" |
| **ineligible** | engine | hard gate (consent/intent/IPTS) | generic warm decline |
| **interview** | admin | reviewed but not selected (shortlisted onward) | extra-thankful, "limited budget, both need (primarily) + merit" |
| **contractual** | admin | failed post-award steps (accepted only) | generic (admin reason deferred — TD-068) |

- **Engine buckets are automatic.** `evaluate()` already recorded *why* it rejected (`academic floor: …` vs `income: …` vs the hard gates); it now returns a `category`, `score_application` persists it at submit, and the scheduled reveal sends the matching email via `emails.send_decline_email(category=…)`.
- **Admin buckets** go through a reviewer-gated `AdminRejectView` → `services.admin_reject()`, which validates the status (interview from shortlisted/profile_complete/interviewing/interviewed; contractual from accepted only), stamps who/when, and sends the email immediately.
- **Admin UI:** Decline-after-review + Decline-contractual buttons (with confirm), a rejection-bucket badge, and the Review & actions panel hidden **only** for pre-shortlist buckets (merit/need/ineligible) — interview/contractual keep the record visible for audit.

## What Went Well

- **The engine already held the answer.** Buckets 1–3 needed no new decision logic — the rejection reason string was already computed and stored; I just lifted it into a structured `category`. That kept the automatic path tiny and the golden master untouched.
- **One status + a category field beat five new statuses.** `status` stays `rejected`; `rejection_category` carries the why/when. No funnel rewrite, no migration of existing rows, and the earlier Review & actions guard refined cleanly to "hide only pre-shortlist buckets".
- **The wording fork was settled in planning, not in review.** Asking up front ("disclose the reason — blunt or suggestive?") meant the B40-appropriate tone ("suggestive, a generic note is more frustrating") was baked into the first draft rather than reworked after the user saw blunt copy.
- **Emails tested without sending any.** All four bucket emails are asserted via Django's `mail.outbox` (locmem) — 22 new tests, zero real mail.

## What Went Wrong

1. **An unrelated stray file was nearly committed.**
   - *Symptom:* `git add -A` staged `docs/plans/2026-05-31-apply-helper-coach-plan.md` — an untracked file from some other context that had nothing to do with rejection buckets.
   - *Root cause:* `git add -A` is indiscriminate; the working tree contained an untracked file I didn't create, and a blanket add sweeps those in.
   - *What prevented it shipping:* reviewing `git status --short` / `git diff --cached --name-only` *before* committing caught it, and I unstaged it (left it in place — not mine to commit or delete). The standing habit — read the staged file list before every commit — is what saved it; reinforced, not newly learned. Flagged the file to the user rather than silently deleting it.

(No build/test/deploy issues — backend and frontend were green on the first full run.)

## Design Decisions

Logged in `docs/decisions.md`:
- **One `rejected` status + a `rejection_category` field** (not five distinct statuses) — the category carries why/when; the funnel and existing rows are untouched.
- **Engine buckets derived, admin buckets actioned** — merit/need/ineligible fall straight out of the existing decision reason; only interview/contractual (genuinely human judgements) need an admin endpoint.
- **Suggestive, not blunt, decline wording** — per the user; a hint at the reason is kinder *and* less frustrating than a generic non-answer, for vulnerable B40 applicants.

## Numbers

- **Backend:** 1373 pytest (+22). 0 failures.
- **Frontend:** 163 jest; `next build` clean.
- **Golden masters:** SPM 5319, STPM 2026 — unchanged (the engine change was additive: a `category` label, no rule change).
- **i18n parity:** 1551 × en/ms/ta (Tamil first-draft for the decline + reject strings).
- **Migration:** `0029` additive, migrate-first.
- **Real mail in CI:** 0.

## Carried Forward

- **TD-068** — contractual rejection's admin-typed reason + post-award capture flow (sign-by deadline, account-number) — the user's deferred piece; the natural next slice.
- **Live-verify** — Decline-after-review on a shortlisted student → bucket badge + the correct decline email; confirm each engine bucket sends its own email at reveal.
- **Tamil refine** now includes the new decline-email + reject strings (~13 batches).
