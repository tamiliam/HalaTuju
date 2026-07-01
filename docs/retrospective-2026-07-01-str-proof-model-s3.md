# Retrospective — STR-proof model, Sprint 3 (officer-review refinement, 2026-07-01)

Worktree `.worktrees/str-salary` (branches `fix/str-copy` → `fix/str-presentation` →
`fix/str-band-matrix`, each fast-forwarded/rebased onto `main`). Commits on `main`:
`9a349001` (ICU copy fix) · `d82de368` (Status chip + finding-first) · `067dd008` (payment guard +
band matrix + date-only Current chip, MODEL_VERSION 1.2.1) · `a1ca9ade` (prescriptive firm-steward
copy). Built against `docs/scholarship/str-proof-spec.md` (§2–§8 revised this sprint).

## What was built
- **Fixed the S1 raw-ICU verdict copy** (#13/#102): the STR-not-current message used ICU `select`, but
  the app's custom `t` (`lib/i18n.tsx`) does flat `{var}` substitution only — no ICU engine — so the
  template rendered verbatim. Replaced with flat per-status keys + a `verdictItemKey()` resolver, and a
  guardrail test (`no-icu-messageformat.test.ts`) that fails the build on any ICU construct in a catalogue.
- **STR Status (Lulus) chip** — the 3rd required STR variable (Recipient · IC · **Status** · Current),
  split cleanly: Status = approval, Current = date-only. Verdict detail now leads with the active finding.
- **Payment guard** (`_str_currency`): "Lulus" is primary proof of approval; a positive PAID amount
  ("Jumlah Telah Dibayar") is an *extra* rescue for a misread status (the #23 "STR"-label leak).
  Additive only — a zero/absent amount never downgrades. Recomputes live → #23-type docs self-correct on
  deploy, no re-run.
- **STR band matrix**: Lulus+dated→Certain, Lulus+no-date→Probable, stale/approval-unread→Unsure,
  Ditolak/non-STR→salary route (over-B40→**Fail/red**, no-salary→Unsure).
- **Prescriptive, firm-steward Check-2 copy**: every officer verdict line = a lean + an action, never
  "can't tell"; "Unsure" reads as "proof required from the student" (auto-raised as a 5-day Action-Centre
  query). Student-facing Cikgu Gopal (`help_engine.py`) left untouched — kind/tolerant.

## What went well
- **The two-persona split fell out cleanly because the surfaces were already separate.** Officer copy is
  `admin.scholarship.verdict.item.*`; the student sees `scholarship.actionCentre.*` + Gopal's coaching.
  Sharpening Check 2 to a firm steward touched only the officer surface — zero risk of a harsh line
  reaching a student.
- **Live-recompute meant the #23 fix needed no re-run.** `current_status` is derived on read, so deploying
  the payment guard fixed every affected dashboard/Semakan immediately — and shrank the pending re-run list.
- **Iterating with the owner on the model, not just the code**, turned a vague "be less wishy-washy" into
  three durable spec rules (prescriptive; the Unsure definition; the two personas).

## What went wrong
- **The S1 copy shipped broken (raw ICU template) on the officer cockpit.** *Symptom:* #13/#102 showed the
  literal `{status, select, …}`. *Root cause:* I assumed a next-intl ICU pipeline and never checked the
  actual `t` — a custom flat-substitution helper with no ICU engine. *Prevention (landed):*
  `no-icu-messageformat.test.ts` fails the build on any `{x, select|plural|…}` in a catalogue; the earlier
  "per-state copy = ICU select" lesson was corrected in `lessons.md`.
- **The S1 prompt fix ("read Lulus, not the label") did not hold** — the model still returned the label
  "STR" at MODEL_VERSION 1.2 (#23). *Root cause:* relied on prompt-tuning for a safety-critical, money-
  adjacent read the LLM kept getting wrong. *Prevention (landed):* a **deterministic** payment guard off a
  hard signal the model *does* read; new lesson — "when an LLM keeps misreading one critical field, add a
  deterministic backstop, don't keep tuning the prompt."
- **The officer voice and the Unsure definition weren't in the original spec**, so the band/copy needed
  several owner rounds to land (prescriptive → Unsure-only-when-a-human-needs-more-data → firm steward →
  Gopal/Check-2 personas). *Root cause:* the spec defined bands and states but not the reviewer's *stance*
  or the *meaning* of Unsure. *Prevention (landed):* `str-proof-spec.md` §4 now states the two personas,
  the prescriptive rule, and the human-would-conclude test for Unsure.

## Design decisions (see decisions.md)
Payment-as-extra-approval-signal; over-B40 → red (revising the earlier "amber, don't auto-reject");
Unsure = "a human would also need more data" + auto-query; two-persona (Gopal tolerant / Check 2 firm).

## Numbers
3063 pytest (project-wide; 1864 scholarship) + 403 jest green. 4 deploys (3× web, 1× api).
MODEL_VERSION 1.2 → 1.2.1. ~45 STR docs on prod audited for the re-run list; #23-class fixed live (no re-run).
