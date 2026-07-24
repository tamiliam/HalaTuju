# Billing-sources investigation — service inventory, provider APIs, apportionment model

**Date:** 2026-07-24 · **Status: COMPLETE — this document satisfies the Billing & usage gate** (roadmap Gates summary: "Billing-sources investigation done (service inventory + provider billing APIs + apportionment model)"). Owner-triggered 2026-07-24; produced from a two-track investigation (repo/docs inventory + provider research, sources cited at end).

## 1. Service inventory (what the platform pays for)

| Service | Used for | Cost behaviour | Reality today |
|---|---|---|---|
| GCP Cloud Run ×2 (api, web) + Cloud Build + Artifact Registry + Scheduler + release-decisions job | App runtime, CI/CD, crons | Fixed platform overhead | RM≈3–4/mo (Mar-2026 snapshot) |
| **Gemini API** (AI Studio key, bills to project `gen-lang-client-0871147736`) | Doc extraction ×5 paths, genuineness scorers, IC fallback, doc-help coach, answer relevance, sponsor profiles (draft/refine/blurb), verdict summaries, contract quiz/segmentation, requests triage | **Per-student-document + per-application — the dominant cost** | RM61.71 of RM65.08 in Mar-2026 (incl. a one-off RM35 bulk job); "normal usage well under RM5/mo" |
| Google Cloud Vision | Raw OCR per document upload | Per-student-document | Small; throttled 40 uploads/hr |
| OpenAI (gpt-4o-mini) | Course-selector report fallback ONLY (after 3 Gemini failures) | Platform-base (course selector is not tenant work) | Negligible |
| Supabase (project pbrrlyoyyiftckqvzvvo) | Postgres, Auth (own Brevo SMTP in dashboard), private Storage bucket `b40-documents` (docs, agreement PDFs, request attachments) | Plan-based; grows with data/docs | Free plan today; **Pro ($25/mo) trigger = DB >500 MB or egress >5 GB/mo** — egress (doc viewing) likely trips first as tenants grow |
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
