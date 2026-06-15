# Plan — Profile narrative redesign + 2-step lifecycle cleanup

**Status:** Drafted 2026-06-15, awaiting owner sign-off (2 open confirmations below). No code yet.

## Goal

Make the AI student profile read like the owner's "desired version" (warm flowing narrative,
not headed sections), and simplify the lifecycle to the **two system-generated steps** that were
always intended — removing the manual scaffolding and the separate anonymous-profile card.

## The agreed lifecycle — ONE profile, generated twice, always by the system

```
Check 2 concludes → reviewer assigned (handoff)
        │
        ▼  [SYSTEM, Gemini Flash]            ← CHECK2_AUTO_GENERATE turned ON
   DRAFT profile  (reviewer reads it to understand the student + prepare to verify claims)
        │
   Reviewer does Check 3, sets verdict + recommended assistance, clicks
   "Save verdict & generate final profile"
        │
        ▼  [SYSTEM, Gemini Pro]
   FINAL profile  — REPLACES the draft in the display; folds in interview findings +
                    the verdict + the reviewer's recommended assistance amount.
                    THIS IS the anonymous version sponsors see. No separate anon step.
```

- **No human ever clicks "Generate".** Draft = auto at handoff; Final = at Save-verdict.
- **One profile, one version on screen.** The final replaces the draft (both kept in the DB for
  audit — `draft_markdown` + `final_markdown` — but the UI shows only the current effective one).
- **The final IS the sponsor/anonymous profile.** There is no confidential-vs-anonymous pair and
  no separate "Generate anonymous profile" step.

## Content / style (approved)

Applies to BOTH the draft (Flash) and final (Pro) prompts:
- **Flowing narrative prose, ~3 paragraphs, NO `##` section headers** (drop Background / Academic
  record / Pathway plan / Funding need / Why support matters). The closing case is woven into the
  last paragraph (this also kills the "ripple effect / breaking the cycle" clichés the section
  scaffold was inviting — and which the prompt already bans).
- **PII-redacted, not strictly anonymous (REVISED policy).** Refer to the student by an **alias
  handle** (e.g. "Scholar-0001" from `pool_ref`) since the name is blocked. **Block ONLY these — for
  BOTH the student and the parents/guardian:** name, NRIC, photo, phone number, email address,
  street address. **Everything else is allowed**, including the **school/college name**, town/region,
  institution, and occupations. (This is looser than the original "permanently-anonymous pool"
  design — see Privacy note below.)
- **Richer, verified specifics:** merit score + the subject-area mix of the A's; the **confirmed**
  programme + institution + intake/start where known (not vague "specific university not detailed");
  a natural duration (no "1.5 years"); lead the funding paragraph with the student's **own named worry**.
- **Funding figure = the reviewer's recommended assistance** (the Decision-panel slider,
  RM1,500–3,000 → `award_amount`). The final states it plainly. The draft (pre-verdict, no amount
  yet) describes the need without a figure. (The per-pathway *estimate* card stays the reviewer's
  award-sizing guide — it informs the slider; the profile reflects the chosen amount.)
- Keep the verification/claim-gating intact (only assert what the deterministic layer confirms).

## Inputs each generation must use

**DRAFT (at handoff)** — ALL available information on the student, specifically including:
- the profile/application facts already fed today (academics, family, household, story, funding need), PLUS
- **the student's answers to Check-2 clarify queries** (the answered `ResolutionItem`s) — NOT fed today.

**FINAL (at Save-verdict)** — the draft PLUS all NEW information gathered during Check 3:
- the student's responses to **reviewer-raised queries**, and **any new/updated Check-2 answers** since the draft,
- the reviewer's **interview findings** (already fed),
- the reviewer's **recommended assistance amount** (already fed),
- the reviewer's written **conclusions** (the Decision-panel "Conclusion" → `verdict_reason`, already fed).

So both prompts gain a "student's answers to our questions" block sourced from the answered resolution items;
the final additionally distinguishes answers gathered after the draft.

## UI changes (cockpit profile card)

REMOVE:
- "Regenerate", "Save", "Publish" buttons.
- "Refine with interview findings (AI)" button + the "Submit an interview first…" hint
  (the final is produced by the verdict button, which already calls the Pro refine path).
- The entire "Anonymous profile (sponsor pool)" card (Generate/Publish/Unpublish, "Not published"
  badge, the "A non-identifying profile sponsors can read…" text).
- The manual draft "Generate" button (draft now auto-appears at handoff).

CHANGE:
- Render the profile as **normal flowing text — no inner scroll box, no box-inside-a-box**
  (it's read-only display now, so the editable `<textarea rows={14}>` and the bordered `<pre>`
  block both go; render the markdown/prose at natural height inside the card).
- The verdict button already reads **"Save verdict & generate final profile"** — keep as is.

FLAG / CONFIG:
- Turn **`CHECK2_AUTO_GENERATE` ON** in prod (currently NOT SET → off) so the draft is made at
  handoff. Billable: one Gemini Flash draft per first reviewer assignment.

## Backend (mostly already there)

- Draft: `generate_ready_profile` → `generate_sponsor_profile` (Flash) — rewrite the prompt to the
  narrative + anonymous style; feed merit/subjects/confirmed-programme.
- Final: `recordVerdict({finalise:true})` → `refine_sponsor_profile` (Pro) — **already wired to the
  verdict button**; rewrite the prompt to the same style and have it emit the anonymous final +
  state the recommended `award_amount`.
- The final becomes the sponsor-pool profile (see open question 2).
- `generate_anonymous_profile` + the anon generate/publish endpoints become unused → remove (or
  repoint, per question 2).
- Update `test_profile_engine.py` (it asserts the section structure, which is changing).

## Confirmations — RESOLVED 2026-06-15

1. **Draft uses the alias too — YES**, but it MAY name the school. Both draft and final follow the
   same PII-redaction list (block name/NRIC/photo/phone/email/street for student + parents/guardian;
   everything else, incl. school, allowed).
2. **Final → sponsor pool: publish on Approve — YES.** At "Save verdict" the final profile is the
   sponsor version; it is published to the pool when the student is **Approved** (a declined student
   never reaches sponsors).

## Knock-on: the pool leak scanner must follow the new policy

`pool.scan_anon_for_identifiers` (the publish-time guard) currently blocks **name + school + town +
distinctive tokens**. Under the revised policy it must block **only** the 6 PII items (name, NRIC,
phone, email, street; photo is non-text) for student + parents/guardian — otherwise it would reject
every profile that (now legitimately) names the school. Relax it to match.

## ⚠️ Privacy note — one explicit confirmation

This redaction list is **looser than the original design**, where the sponsor-facing pool profile was
**strictly anonymous** (no school, no town). Under the new rule, **sponsors will see the school name,
town/region, institution and occupations** — only the 6 contact/ID items are hidden. That is a
deliberate, hard-to-reverse change (sponsors are external; once shown, it's out). **Confirm you're
happy for sponsors to see school/town/etc.** — if yes, I'll build to this list; if the looser list was
meant only for the **reviewer's** draft (staff) while the **sponsor** final stays strictly anonymous,
say so and I'll split the two redaction levels.

## Validate

Build in a worktree; validate the new draft + final on a real student of this shape (#18, SMK
Pulau Sebang, Social Science — the desired "Scholar-0001" example) before calling it done.
No migration. Single focused sprint.
