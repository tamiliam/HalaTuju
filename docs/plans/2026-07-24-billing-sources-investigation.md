# Billing-sources investigation — service inventory, provider APIs, apportionment model

**Date:** 2026-07-24 · **Status: COMPLETE — this document satisfies the Billing & usage gate** (roadmap Gates summary: "Billing-sources investigation done (service inventory + provider billing APIs + apportionment model)"). Owner-triggered 2026-07-24; produced from a two-track investigation (repo/docs inventory + provider research, sources cited at end).

## 1. Service inventory (what the platform pays for)

| Service | Used for | Cost behaviour | Reality today |
|---|---|---|---|
| GCP Cloud Run ×2 (api, web) + Cloud Build + Artifact Registry + Scheduler + release-decisions job | App runtime, CI/CD, crons | Fixed platform overhead | **RM89.07 incl. tax (Jun-2026 ACTUAL)** — the "RM≈3–4/mo" Mar-2026 snapshot is SUPERSEDED; see the 2026-07-26 cost addendum |
| **Gemini API** (AI Studio key, bills to project `gen-lang-client-0871147736`) | Doc extraction ×5 paths, genuineness scorers, IC fallback, doc-help coach, answer relevance, sponsor profiles (draft/refine/blurb), verdict summaries, contract quiz/segmentation, requests triage | **Per-student-document + per-application — the dominant cost** | RM61.71 of RM65.08 in Mar-2026 (incl. a one-off RM35 bulk job); "normal usage well under RM5/mo" |
| Google Cloud Vision | Raw OCR per document upload | Per-student-document | Small; throttled 40 uploads/hr |
| OpenAI (gpt-4o-mini) | Course-selector report fallback ONLY (after 3 Gemini failures) | Platform-base (course selector is not tenant work) | Negligible |
| Supabase (project pbrrlyoyyiftckqvzvvo) | Postgres, Auth (own Brevo SMTP in dashboard), private Storage bucket `b40-documents` (docs, agreement PDFs, request attachments) | Plan-based; grows with data/docs | **ALREADY ON PRO — $25/mo, being paid since ~Dec 2025 (invoice #8 dated 8 Jul 2026).** The original "free plan today / Pro is a future trigger" reading was WRONG; verified live 2026-07-26 (`get_organization` returns `plan: pro`). Egress still the metric to watch as tenants grow |
| Brevo SMTP | 53 send_* functions (student/sponsor/ops mail) | Per-send; free 300/day (~9k/mo) | Free tier; Starter ≈$9/mo for 5k/mo when volume forces it |
| Twilio | WhatsApp reminders (ON), phone-verify OTP (PAUSED — ~$0.34/SMS) | Per-student message | Low |
| Google Workspace SA | Meet/Calendar interviews; Vircle relay Sheet/Drive/CSV; guide PDF | Free-tier API usage | Nil |
| Sentry, domain, GCS backup bucket | Monitoring, halatuju.xyz, doc backup mirror | Fixed / tiny | Nil–small |

Not billable to HalaTuju: Vircle (manual relay, no fee in any code path); Cloudflare Turnstile (IS used — the public contact form, verified in the Supabase edge function; FREE, so listed-not-metered. Corrected 2026-07-25: the original sweep missed it because the check lives outside Django); Google Workspace APIs. NOTE: the GCP **billing account is shared across five unrelated projects** — every cost query must filter `project.id`.

## 2. What each provider can report programmatically (July 2026)

| Provider | Usable API | Practical minimum |
|---|---|---|
| GCP | **BigQuery billing export** (already configured: dataset `billing_export`, per-service + per-label GROUP BY, ~hours–24h lag); Budget Pub/Sub pushes month-to-date spend ~every 20 min. Cloud Billing API does NOT return historical costs. | The two BigQuery queries already scripted in memory (`gcp_cost_monitoring.md`) — monthly by project + by service |
| Gemini | **No account-level usage endpoint.** Per-call `usageMetadata` (exact token counts) in every response = the billing-grade source. Spend lands in the GCP export (~24h lag). Keys have no own billing identity. | Log tokens at the seams; price internally; reconcile vs export monthly |
| Supabase | **No billing/usage API** (dashboard internals undocumented; egress not queryable). DB size + storage bytes obtainable via SQL. | Monthly SQL snapshot; treat plan fee as fixed shared cost |
| Brevo | Solid statistics API (`aggregatedReport`, per-message `events` — tenant-attributable if sends carry tags) | Bill from our own send log; `aggregatedReport` as monthly cross-check |

## 3. Attribution readiness (the decisive finding)

- **Every billable call site is org-resolvable TODAY**: vision/profile/help/verdict paths all hold the `application` (→ `owning_organisation`, the denormalised tenancy FK); contracts hold the org-owned template; requests triage holds `OrgRequest.organisation`; storage keys are org-prefixed; WhatsApp callers pass the application. Email senders are mixed — callers hold the application but most senders aren't yet threaded with the org (a Sprint 13a task, not a blocker).
- **Zero metering exists**: no usage table, no token logging, no tenant tag anywhere (audit §5 confirmed still true post-Sprint 15). The audit's call-site list was verified complete by Sprint-0's sweep and matches what we found.
- PRD **D-4 stands and is validated by this investigation**: Option A — platform-metered, tenant tag at every billable call, one `usage_events` table `(organisation, service, model, units/tokens, unit_price_version, at)`; per-org own-keys remain a designed-in later option.

## 4. Proposed apportionment model (the invoice, three lines)

1. **Platform fee (fixed, per organisation/month)** — covers the shared floor: Cloud Run/Build, Supabase plan, Brevo plan, domain, monitoring. Set by the owner; the BigQuery export + plan fees give the floor to price above. Do not meter these — split by simple driver (per active tenant) per standard small-SaaS practice.
2. **Metered usage at PUBLISHED unit prices** — from `usage_events` × a **versioned internal price table** (e.g. per document analysed, per 1M tokens, per email/WhatsApp beyond an included allowance). NEVER bill raw provider actuals (24h lag, unauditable, provider price swings leak into invoices). Monthly reconciliation of internal totals vs the BigQuery export catches margin drift. **Price the AI units against Gemini 3.x rates, not 2.5** — the forced October migration raises unit costs (3.x Flash ≈5× 2.5 Flash; 3.1 Pro ≈1.6× 2.5 Pro): pricing on today's rates would go underwater in three months.
3. **Feature work at quoted prices** — already live (Requests space, hours-based owner-gated quotes).

## 5. What "Billing & usage v1" is (when the owner triggers the build)

- **Sprint 13a (already roadmapped, Phase 4)** = the meter: `usage_events` table (additive migration + RLS) + thin wrappers at the sanctioned seams (`vision._call_gemini_json`, `profile_engine._call_gemini_text`, `contracts._gemini_generate`, `_send*`, `send_whatsapp`) logging `(org, service, model, units)` — the seams were built for exactly this (tenancy Rule 6).
- **Billing & usage card** (the Administration "Coming soon" card): per-org month-to-date usage readout + the price table. **No auto-invoicing** (PRD non-goal): the invoice is generated as a document for the owner to send; payments stay manual.
- Prerequisite check before first real invoice: accountant confirmation on **MyInvois e-invoicing** applicability (small-business phase live since 1 Jul 2026); SST not applicable below RM500k turnover.

## 6. Risks & dated items

- **Gemini 2.5 retirement 16 Oct 2026** — app-wide model migration (4 subsystems) AND the unit-price uplift above. Plan in September.
- **Supabase Pro ($25/mo)** becomes near-certain with tenant #2's document volume — bake into the platform fee from tenant #2 day one.
- **Brevo 300/day ceiling** — a second tenant's email volume may force Starter (~$9/mo); the pre-flight quota-check pattern from SJKTConnect applies.
- Shared GCP billing account across five projects — all queries filter by project; consider a HalaTuju-only billing account if invoicing auditability ever demands it.

## Verdict

**The gate condition is met.** Service inventory: complete. Provider billing APIs: mapped (conclusion: meter internally, reconcile externally). Apportionment model: three-line invoice per §4, D-4/Option A confirmed. The build (Sprint 13a + the Billing card) stays owner-triggered and pairs naturally with the Phase 3–4 work if next week's second-tenant meeting proves credible.

### Sources (provider research, July 2026)
GCP billing export/budgets: docs.cloud.google.com/billing (export-data-bigquery, budget-api-overview, budgets-programmatic-notifications) · Gemini: ai.google.dev/gemini-api/docs (pricing, billing, deprecations) · Supabase: supabase.com/docs (api introduction, telemetry/metrics, billing-on-supabase, manage-your-usage/egress) · Brevo: developers.brevo.com (get-smtp-report, getaggregatedsmtpreport, get-email-event-report) · Attribution patterns: particula.tech, oneuptime.com, dodopayments.com (multi-tenant billing) · Malaysia: duittools.com SST guide, vatabout.com digital-services 2026.

---

## Addendum — pricing readiness, measured against the LIVE meter (2026-07-26)

The meter has now been running since **25 Jul 2026 ~02:32 MYT** (first recorded call). Owner asked
what it would take to put PRICES on the Billing & usage screen. Measured, not estimated:

### The data IS priceable — no re-instrumentation needed
`UsageEvent` records the **model name plus a separate input/output token split**, which is the
billing-grade source §2 prescribed. First 55 events: `gemini-2.5-flash` 21 calls (15,623 in /
3,293 out), `gemini-2.5-pro` 3 calls (6,942 in / 1,272 out), `vision_ocr` 13, `email` 16,
`whatsapp` 2.

### The finding that should shape the build: metered usage is PENNIES
Those 55 events cost roughly **RM0.16 across a day and a half** at market rates — consistent with
the Mar-2026 snapshot ("normal usage well under RM5/mo"). Against a fixed floor that becomes
~RM150/mo once Supabase Pro ($25) and Brevo Starter (~$9) trigger with tenant #2.

**So the per-token rate is not where the money is — the PLATFORM FEE is.** Setting a token price
is the interesting engineering problem and the trivial commercial one. Do not let it absorb the
effort; §4 line 1 (the fixed fee) is the number that decides whether this is profitable.

### Three gaps between here and a price on screen
1. **No price table exists at all** — `usage.py` states this explicitly ("NO prices anywhere in
   v1"). This is the actual build.
2. **`unit_price_version` was specified in §3 and never built.** Without it, changing a price
   silently rewrites last month's invoice. An invoice must reproduce. Either stamp the version on
   the event at write time, or use an effective-dated price table plus a snapshot at issue.
3. **Email attribution — 16 of the first 55 events are org-NULL.** Pricing today under-charges the
   tenant by every email sent. Close before any figure reaches a tenant. (The help-engine's
   org-NULL rows are correct and must stay — the coach is firewalled from application data.)

### Recommended split (the risk profiles differ sharply)
- **Now — cost visible to the OWNER only.** Versioned internal price table + cost per line on the
  usage screen, super-only. No invoice semantics, no tenant sees a figure, reversible. This is what
  proves the pricing is sane before anyone is billed. Pairs with the email-attribution fix.
- **Later — bill a tenant.** Needs price versioning, issued-invoice snapshots, the platform-fee
  decision, and the **MyInvois e-invoicing check with the accountant** (§5 prerequisite — a real
  blocker, not an engineering one).

### Still-open owner decisions (business, not engineering)
- The **platform fee** per organisation per month (floor ~RM150 and rising with tenant #2).
- The **margin** — Sprint 14 recorded "cost + 15–30%"; never fixed to a number.
- Whether the screen shows **cost only, or cost + marked-up price** (recommendation: both to the
  owner, neither to a tenant until a full month has been watched).

§4's standing rules are unchanged and still bind: never bill raw provider actuals, and **price
against Gemini 3.x rates, not 2.5** — the October migration puts 3.x Flash ≈5× today's rate.

---

## Addendum 2 — MEASURED cost actuals + the waste finding (2026-07-26)

Owner produced the real Supabase invoice and the GCP billing console. Both were read directly.
**Two claims in §1 above were wrong and have been corrected in place.**

### Supabase — ALREADY ON PRO (correcting §1)
Invoice **TPTHYS-00008** (the eighth), billed to **Rajula Consultancy**, period 8 Jun – 7 Jul 2026:
**$25.00, all of it the Pro plan fee.** Every usage line sat inside the included allowance —
compute 720 h ($9.68 gross, covered by the $10 credit), egress 5.03 GB, cached egress 2.93 GB,
storage 428 GB-hrs, MAU 155, function invocations 6. Verified live: `get_organization` →
`plan: "pro"`. So Pro is a **current cost, not a tenant-#2 trigger.**

Live usage via SQL (2026-07-26): **DB 46 MB** (8 GB included), **storage 1,213 MB** across 1,335
objects (`b40-documents` 1,086 MB · `field-images` 90 MB · `field-images-concept` 37 MB), **829
auth users**. Comfortable headroom — Inspire would not move this bill.

⚠ **The $25 is per ORGANISATION, not per project.** HalaTuju, Lentera and tamilnadai all sit under
`Rajula Consultancy`; the other two are PAUSED, which is why compute reads exactly 720 h (one
project, one month). **Un-pausing Lentera adds compute hours to this same invoice.** Clean
per-tenant cost attribution would need separate orgs.

### GCP — June 2026 actual: RM89.07 incl. tax (correcting §1)
| Service | Cost | Metered by `usage_events`? |
|---|---|---|
| Cloud Run | RM45.84 | ✗ |
| **Artifact Registry** | **RM27.46** | ✗ |
| Cloud Vision API | RM5.97 | ✓ |
| Cloud Scheduler | RM3.37 | ✗ |
| **Gemini API** | **RM1.22** | ✓ |
| Cloud Storage + Build | RM0.16 | ✗ |

By project: HalaTuju RM83.73 usage − RM20.71 savings = RM63.02; cci-gms RM0.28. Subtotal RM84.01
+ RM5.06 tax.

### The conclusion that should shape the billing build
**The meter captures RM7 of RM89 — about 8%.** Everything `usage_events` tracks (Gemini, Vision)
is a rounding error; **infrastructure is the cost.** Combined with Supabase, the **true fixed floor
is ~RM207/month** (GCP RM89 + Supabase ~RM118), not the ~RM150 previously estimated.

This does NOT invalidate §4's three-line model — it re-weights it. Line 1 (the fixed platform fee)
is the commercial decision; line 2 (metered usage) is ~8% of cost and precision there buys little.

### ⚠ Waste finding — Artifact Registry — INVESTIGATED AND ACTIONED 2026-07-26 (see TD-178)
RM27.46/month — **31% of the GCP bill** — stored **1,732 images totalling 77.6 GB**.

**The first diagnosis above was half wrong.** Investigated 2026-07-26:
- The `delete-images-older-than-30d` policy **was** executing correctly — the oldest image in every
  actively-deployed package was exactly 30 days old, to the second.
- The 14 Mar images were real, but sat in **dead** packages, pinned forever by the unfiltered
  `keep-most-recent-10` (KEEP beats DELETE). That half of the hypothesis was right.
- Most of the cost was **not waste at all**: ~11 builds/day (reconciling with 438 commits touching
  `halatuju_api/` in 30 days) × ~258 MB, held 30 days. Real artefacts, kept 4× longer than useful.
- The ~650 "untagged" images were **not** waste either — they are in-toto provenance attestations
  at ~12 KB each. Counting images overstated the problem; only bytes matter.

**Actioned:** retention cut 30d → 7d (~62 GB billed, projected ~RM20/month) and six orphan packages
deleted. **`keep-most-recent-10` was deliberately left unscoped** — `tamilnadai`'s live image dates
from 2026-02-12 and that rule is the only thing protecting it. Reclaim is asynchronous; re-measure
after 2026-07-28 before treating the saving as banked.

**Effect on the floor below:** if the reclaim lands, GCP falls to roughly **RM69/month** and the
combined fixed floor to about **RM187/month**. Do not re-price on that until it is measured.

### ⚠ Waste finding 2 — Cloud Run **Jobs** was the biggest line — ACTIONED 2026-07-26
SKU-level reading of the June bill (BigQuery export) put **Cloud Run Jobs CPU at RM29.81 + Jobs
Memory RM3.31 = RM33.12**, ahead of Artifact Registry and ~37% of the GCP total. One job exists:
`release-decisions`, 2 vCPU / 2 GiB, fired every 15 minutes.

Working back from the bill: **~51 seconds per execution × 2,880/month**, almost entirely Django
start-up. The same work on the always-warm api service measured **200 in 66 ms**.

**Actioned:** the scheduler now calls the HTTP cron endpoint that 22 of its 23 siblings already use
(`decision-emails` was already registered in `CronRunView.JOBS`). The Job is left dormant — Cloud Run
Jobs bill per execution, so the saving is banked and rollback is one scheduler edit. See
`docs/decisions.md` 2026-07-26.

### Revised expectation for the GCP floor
| line | June actual | after both fixes |
|---|---|---|
| Cloud Run Jobs (CPU + memory) | 33.12 | **~0** |
| Artifact Registry storage | 26.95 | ~7 (projected, re-measure after 28 Jul) |
| everything else | 28.37 | 28.37 |
| **GCP total** | **88.44** | **~RM36** |

That is a **~59% reduction** on infrastructure that no tenant's activity was driving. **Both figures
are projections until the July/August invoice confirms them** — the Artifact Registry reclaim is
asynchronous, and the Jobs line only stops accruing from 2026-07-26. Do not set the platform fee off
this table; set it off the next invoice.

**Tooling gotcha:** `gcloud artifacts repositories list` reported the size as **"72.2 MB"**;
`describe` reports **77,576 MB**. A thousandfold discrepancy — always size a repository with
`describe`, never the list column.
