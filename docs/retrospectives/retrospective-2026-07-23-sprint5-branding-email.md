# Retrospective — Sprint 5: Per-org branding & email sender identity (backend)

**Dates:** 2026-07-23 (Phase 0–2, first executor) → 2026-07-24 (Phase 2 remainder → close, second
executor). **Scope:** backend only; no migration; `halatuju-web/` untouched. **Result:** shipped
locally, **not pushed** (owner gates the deploy). 4350 pytest pass, 0 failures, 0 skips; the 113
email goldens pass UNMODIFIED end-to-end.

## What we set out to do

Route every rendered brand literal — programme name, team sign-off, coach persona, sender identity,
display domain — behind ONE read seam (`apps/scholarship/branding.py`) so the scholarship platform
can render a second tenant's identity, WITHOUT changing a single byte of BrightPath's live output.
The byte-identity guarantee is enforced by 113 golden snapshots captured before the extraction.

## What happened

- **Phase 0** normalised drifted BrightPath sign-offs to one canonical form per language (owner
  rulings) so the goldens pin the *intended* copy, not the drift.
- **Phase 1** froze the 113 goldens against the untouched code.
- **Phase 2** built the seam and extracted sender identity, then (this executor) routed the
  remaining ~126 `BrightPath` / 5 `Cikgu Gopal` / 4 `halatuju.xyz` literals: the 5 core `.format`
  families through `{programme}`/`{signoff}`/`{domain}` placeholders threaded with an optional
  `branding=None`, and the tail (interview ×5, reviewer, executed/witness/countersign, sponsor,
  payment + vircle-activation ops) through the platform seam.
- **Phase 3** moved the coach persona + programme name in `help_engine.py` onto the seam.
- **Phase 4** added the org-2 leak test and the AST brand-guard.
- **Phase 5** installed the declared `python-docx` dep (the local venv lacked it → 11 pre-existing
  `test_contracts` failures, now green), ran the full suite, and closed out.

## The load-bearing discovery: true column-driven byte-identity was impossible

The obvious design — "the platform tenant reads its own seeded BrightPath columns like any other
org" — cannot reproduce today's output, because three seeded columns intentionally disagree with
what the emails actually render:

1. **`email_from`** is settings-driven (`DEFAULT_FROM_EMAIL`, e.g. `HalaTuju <noreply@halatuju.xyz>`
   in dev), NOT the seeded `info@halatuju.xyz` column.
2. **`persona_name_ta`** is seeded Latin `Cikgu Gopal`, but email BODIES render Tamil script
   `சிக்கு கோபால்` (while the coach PROMPT wants the Latin form).
3. The award email prints the **bare display domain** `halatuju.xyz` regardless of `FRONTEND_URL`
   (which is `http://localhost:3000` in dev).

So the seam renders the platform tenant from a byte-exact `PLATFORM` block (the one sanctioned home
for the literals, allow-listed by the AST guard), and only a TENANT org reads its own columns. This
also cleanly separates the two axes: brand COPY is per-language literal; sender identity + frontend
URL stay settings-driven, so output is identical in every environment, not just prod.

## Owner wording rulings (Phase 0, binding)

EN sign-off `The BrightPath Bursary Team`; MS `Pasukan Program Bursari BrightPath` + programme
`Bursari BrightPath`; TA sign-off `BrightPath Bursary குழு`. EN/TA programme name `BrightPath
Bursary` unchanged. The per-language programme form is why the 5 core families fill `{programme}`
from `branding.programme_name(lang)` and NOT from the caller's `programme_name` argument (the cohort
name, always the EN form) — feeding the caller's value would have rendered "Perjanjian BrightPath
Bursary" where MS wants "Perjanjian Bursari BrightPath", breaking a golden.

## The two-agent handoff

The first executor left a clean, green checkpoint (3 commits, seam + goldens + Phase 0) and a
precise handoff describing the exact remaining literal families and the two platform-column-vs-
runtime mismatches. That handoff was accurate and made the continuation low-risk: every family
converted was verified against the goldens immediately, so a byte-break surfaced at the function
that caused it, never at the end. The one place the handoff's mechanical advice needed care was the
string-concatenation form used to route a phrase through the seam: it silently drops the `f`-prefix
on any segment REOPENED after the brand, so an f-string with a `{placeholder}` *after* the brand
(`f'A reminder … {programme} … {soon_en}'`) rendered a literal `{soon_en}`. The goldens caught the 3
student-facing cases instantly; a grep for reopened-segment placeholders caught the 3 ops-email
cases the goldens don't cover. All 6 were rewritten as clean f-strings.

## What went well

- **Goldens as a tight feedback loop.** Running the 113-snapshot suite after every converted family
  turned a 3375-line, tri-lingual, mixed plain/f-string/`.format` refactor into a series of small,
  independently-verified steps.
- **The AST guard is genuinely self-checking.** It derives the `send_*` surface via `inspect` and
  asserts minimum scanned counts (emails ≥1000, help_engine ≥150 string constants; ≥40 send funcs),
  so a scanner that silently matched nothing fails loudly — the exact trap `lessons.md` warns about.
- **No migration, no web diff, no model change** — the 19 tenant columns landed in platform Sprint 1;
  this sprint only READS them.

## What to watch / carry

- **The Vircle guide ATTACHMENT filename** still derives from the platform seam (`_P.programme_name`)
  even on a tenant send — deliberately out of scope (the PDF itself is a BrightPath-specific Vircle
  onboarding asset), and the leak test scopes to subject/body/html/from/reply-to per the brief. A
  real tenant onboarding needs its own guide + a branding-aware filename.
- The `{programme}`-parameterised student mail (ack/pass/submission/award-confirmed/request-info/
  query-*) takes `programme_name` from the caller but its SENDER identity is still the platform seam
  (no `branding` param) — wiring those callers to pass tenant branding is a follow-up, not needed
  while BrightPath is the only tenant.
- **`python-docx` was missing from the local venv** though declared in `requirements.txt` — installed
  via `uv pip` this sprint; the 11 `test_contracts` failures were purely that, not code.

## Deviations from the brief

- One existing test (`test_vircle.py::test_every_language_tells_an_under_18_to_use_a_parent_account`)
  manually `.format()`s `VIRCLE_INSTALL_BODIES` and broke on the two NEW placeholders. Its
  behavioural assertion (the under-18 paragraph + `help@`) is unchanged; it was updated to supply
  `{programme}`/`{signoff}` from the platform seam exactly as the real sender does — a necessary
  consequence of the template's public shape gaining placeholders, not a silent edit to hide a break.
- The `test_help_engine` firewall guardrail pinned the engine's exact parameter set; `branding` is a
  new, legitimately non-sensitive parameter (a brand value object with no student data), so the
  guardrail was updated to allow it and additionally asserts branding exposes no
  application/profile/score accessor.
