# Retrospective — Org Config Sprint B: student comms + the deferred sponsor-email cap (2026-09-07)

**Scope.** The roadmap's Sprint B (`docs/plans/2026-09-06-org-configuration-roadmap.md`): four
student-communication settings — `query_email_delay_hours` (2), `nudge_auto_delay_minutes` (30),
`nudge_cooldown_hours` (24), `max_clarify_open` (3) — plus `sponsor_email_max_cards` (5), the one
setting Sprint A deferred because its render sites carried no organisation. Registry entries +
wired read sites + rows on the existing tab. **NO migration** — the store, the endpoint and the tab
shell all shipped in Sprint A; a Sprint B is exactly what the roadmap promised: entries + wires.

## What shipped

- **Five registry entries in `courses/org_config.py`.** Every default DELEGATES to the platform's
  live home: three to `getattr(settings, …)` env-tunables (`SPONSOR_EMAIL_MAX_CARDS`,
  `NUDGE_AUTO_DELAY_MINUTES`, `NUDGE_COOLDOWN_HOURS`), two to module constants imported LAZILY at
  read time (`services.QUERY_EMAIL_DELAY_HOURS`, `check2_queries.MAX_CLARIFY` — lazy because
  org_config lives in apps.courses and a load-time import of apps.scholarship would be circular).
  The constants stay where they are, as the one platform home each; the registry reads them.

- **Two SWEEPS gained per-organisation SQL windows**, both copying `pool._funded_grace_window`'s
  spelling verbatim — default arm `(~Q(owning_organisation_id__in=…) | Q(isnull=True)) & Q(date)`,
  one OR-arm per configured org:
  - `services._query_email_due_window` → `send_due_query_emails` (the "few questions" email);
  - `nudge._nudge_due_window` → `send_application_nudges` (the one-time auto nudge).
  The filter MUST stay in SQL in both: the query sweep's loop calls `sync_check2_queries`, which
  CREATES items, so a too-early row let through the queryset would be asked early even if the send
  were skipped; and the nudge cutoff is the sweep's ONLY delay gate (`send_nudge` re-checks
  applicability, never the delay).

- **Per-application reads** where an application is in hand: `nudge._auto_delay(application)` /
  `_cooldown(application)` (drives `nudge_state`'s `available_at` and the manual-button cooldown)
  and `check2_queries.max_clarify(application)` (drives BOTH `sync_check2_queries`'s cap and
  `clarify_overflow_count`'s "N waiting" note — one cap, two readers, one function).

- **The sponsor-email card cap is threaded through the organisation, both render sites.**
  `sponsor_notifications` derives the batch's SOLE organisation (`_sole_batch_organisation`: one
  org id and no NULL, else None — a mixed batch follows the platform default, because applying one
  tenant's cap to another tenant's students would be a guess). It flows
  `sponsor_notify.send_student_alert(organisation=…)` → the legacy sender
  (`emails._send_sponsor_notify`) AND the template path (`deliver` context →
  `sponsor_comms.student_cards_blocks(organisation=…)`). **`sponsor_comms.MAX_CARDS` is DELETED**
  — it was a second literal 5 beside `SPONSOR_EMAIL_MAX_CARDS`, exactly how the two sites would
  have drifted; `sponsor_comms.max_cards(organisation)` and `emails._sponsor_email_max_cards
  (organisation)` both read the ONE registry entry now.

- **Both dry-run commands now use the shared windows.** `send_due_query_emails --dry-run` and
  `send_application_nudges --dry-run` had their own copies of the platform-only cutoff — a dry run
  that re-spells the rule would LIE for any organisation with its own delay. Each now filters with
  the same window Q the real sweep uses.

- **FE:** `GROUP_ORDER` gains `student_comms` (the tab is registry-driven — the five rows render
  from the server payload with no other component change); i18n `group.student_comms`, four new
  units (`hours`/`minutes`/`cards`/`questions`) and five label/desc pairs × en/ms/ta (ms/ta first
  drafts). +15 keys, parity 4790 × 3.

## What must not be "tidied"

- **⚠ The `| Q(owning_organisation_id__isnull=True)` arm looks redundant on a LOCAL column and
  stays anyway.** The bite-check found that Django's compiler already guards a negated `__in` on a
  local nullable column (it emits `NOT (col IN … AND col IS NOT NULL)`), so deleting the arm
  currently changes nothing. It is kept because (a) the guarantee is an ORM implementation detail
  nobody should lean on, (b) the pool spelling is the house pattern and three copies that agree
  are auditable, and (c) the moment one of these windows crosses a JOIN the ORM's protection
  changes shape. Do not "simplify" it away.
- **⚠ A mixed-organisation sponsor batch reads the PLATFORM cap, deliberately** — None is a real
  answer (the `signup_programme_for` rule). Do not "improve" `_sole_batch_organisation` to pick
  the majority org.
- **⚠ Doc requests and the one-tap confirms stay OUTSIDE `max_clarify_open`** whatever the value —
  the setting caps typed-answer questions only, and `reporting_date_unknown` keeps its carve-out.
- **⚠ The platform constants (`QUERY_EMAIL_DELAY_HOURS`, `MAX_CLARIFY`) are still the one home for
  the platform numbers.** The registry default READS them; deleting them and inlining a literal in
  org_config splits the home the other way round.

## Bite-checks (each injected, verified to land, restored by writing the original back)

1. `sync_check2_queries` cap reverted to the constant → `test_a_configured_cap_narrows…` FAILED.
2. `_query_email_due_window` collapsed to the default cutoff → the per-org sweep test FAILED.
3. `_nudge_due_window` collapsed to the default cutoff → the per-org sweep test FAILED.
4. Both sponsor-cap sites made to ignore the organisation → BOTH cap tests FAILED (2 failures).

The one bite that did NOT land: dropping the `isnull` arm from the query window — see above; the
finding is recorded as the reason the arm carries a comment rather than a behaviour test.

## Gates

- pytest full suite: **5891** passed (5875 → +16: 11 new in `test_org_config.py` — 35 there now —
  and the rest collected elsewhere unchanged).
- jest **1738** (1737 → +1); `next lint` 0 errors; `tsc` 24 (baseline, test files only);
  i18n **4790 × 3**; `next build` clean. No migration, `makemigrations --check` clean.

## Lessons

- **Django already NULL-guards a negated `__in` on a local column.** A planted defect that fails
  to land is information: the `~Q` trap the pool comment warns about bites through JOINS and raw
  SQL, not through a simple local-column negation. Keep the explicit spelling, but when
  bite-checking a belt-and-braces arm, expect silence and write down WHY instead of forcing a
  fake failure.
- **A dry-run flag is a read site too.** Both sweeps' `--dry-run` branches carried their own copy
  of the cutoff rule and would have silently disagreed with the real sweep for any configured
  organisation. When a rule moves into a seam, grep for the rule's SPELLING, not just its callers.
