# Retrospective — Org Config Sprint F: the agreement clocks (and the end of the arc)

**Date:** 2026-09-07
**Worktree:** `.worktrees/org-config-sprint-f`, branch `feat/org-config-sprint-f`
**Migration:** none.

---

## What shipped

Two settings under a new **Agreements** group — `sign_accept_deadline_days` (30) and
`sign_reminder_days` (3) — and three dead settings deleted. That closes the Org Config arc:
A sponsor page, B student comms, C reviewers & staff, D interviews, E documents, F agreements.

## The finding that shrank the sprint

The roadmap's Sprint F line, written on 2026-09-06, asked for the foundation signatory
name/title/notify email and said they *"currently live in platform env vars"*. They did not.
**Sprint 5 had already moved them onto `ContractTemplate`** — `counterparty_name`,
`counterparty_title`, `counterparty_nric`, `counterparty_notify_emails` — a row already owned by
one organisation, and the thing that actually prints on the agreement. The code even records the
move: *"the hard-coded constants were removed after a render-diff parity test."*

Building the roadmap's request would have produced **a second home for the same fact**: an
organisation could have typed a signatory on the Configuration tab and watched the signed PDF
keep the template's. That is the failure mode this whole arc's binding rules exist to prevent,
and it would have arrived by faithfully following the plan.

It also removed the sprint's stated risk. "Legal-adjacent; prints into the agreement PDF, so the
owner reviews the rendered output" was true of the signatory and of nothing else here — the two
clocks are dates in an email and a cron interval. No PDF was touched.

**What was left standing:** three `FOUNDATION_SIGNATORY_*` settings that nothing read and nothing
set (checked against the live service, not against `base.py`). The owner chose to delete them.
The trap they carried is specific: the day someone needs to correct a name on an agreement, those
three settings are the first place they will look, and changing them does nothing at all.

## The bug the sprint would have shipped

`send_signing_reminders` computed its interval **once, above the loop**:

```python
interval = timedelta(days=getattr(settings, 'BURSARY_SIGN_REMINDER_DAYS', 3))
for ag in qs:   # every tenant's agreements
```

Correct for as long as the number was the platform's. The moment it becomes each organisation's,
one sweep covering every tenant would apply whichever organisation was read first — and it would
have been invisible, because the sweep is idempotent and would simply nudge on the wrong cadence.
The interval now resolves per application with a per-org cache. **A hoisted constant is the tell:
when a value becomes per-tenant, look for every place it was lifted OUT of a loop for speed.**
Sprint C found the same shape in `send_review_nudges`; this is the second.

## What went wrong

**An i18n insert landed in the wrong block, and the parity check passed.** I anchored the new
group key on the text `"documents": "Documents"` — which also appears under
`admin.scholarship.blockers.step`. The key landed there in **all three** locale files, so
`check-i18n` (which compares the three files against each other) saw perfect parity and reported
ALL PASSED. The tab's tri-language render walk caught it: the group had no words behind it.

*Root cause:* a text-anchored insert into a 5,000-line JSON file, using an anchor that is not
unique. *Prevention:* anchor on a neighbour that only exists in the target block (here the
preceding `"interviews"` line inside `config.group`), and **verify by loading the JSON and reading
the resolved path**, not by re-running the parity check — parity cannot see a key that is wrong in
the same way three times.

**Two fixture failures** (a `Sponsorship` needs a `Sponsor`; `bursary.emails` is imported inside
the function, so the module must be patched, not the attribute). Both mine, both caught first run.

## Numbers

| Gate | Result |
|------|--------|
| pytest (`apps/`) | **5964** (+6; `test_org_config.py` 64 → 70) |
| jest | **1779** (+1) |
| `next lint` | 0 errors |
| `tsc --noEmit` | 24 (baseline, none new) |
| i18n | **4850 × 3** (+5 keys; ms/ta first drafts) |
| `next build` | compiled successfully |
| `makemigrations --check` | no changes detected |

Three bite-checks landed and were restored: the accept clock de-orged, the reminder interval
hoisted back above the loop, and a signatory key added to the registry.

## The lesson worth carrying

A roadmap written six days ago described a part of the system that had already moved. The plan
was not wrong when it was written; it aged. **Re-derive a sprint's premise from the code at sprint
start, not just its file list** — the standing rule already says to re-derive the file table, and
this sprint is the case where the *reason for the work* was the stale part.
