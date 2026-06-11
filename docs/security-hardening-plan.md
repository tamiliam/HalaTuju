# HalaTuju — Security Hardening Plan

**Source:** the 2026-06-11 security posture audit (`docs/security-posture.md`). That audit found **no critical holes**; this plan executes the residual **hardening backlog**. Items #1 (leaked-password protection) and #3 (no secret leakage) are already done. This covers the rest.

> **This is a LIVE system holding sensitive PII** (NRIC, income, STR/IC scans). Every item below: test locally first, run the pre-deploy checklist (`halatuju_api/CLAUDE.md` — full test suite + Supabase Security Advisor), **migrate-first via Supabase MCP** for any migration (+ contenttypes workaround + RLS for new models), **≤2 deploys per item**, and **push = deploy = owner-gated**. Do the items **one at a time** through the small-change-lane; if you do several in one session, write **one retro** at the end but commit/deploy/verify each independently. Re-run `get_advisors(security)` after any migration.

---

## Item A — Back up the document Storage bucket  ⭐ highest value
**Why:** daily DB backups **exclude Storage objects** (verified in the audit). The 311 ID/income/STR scans in the private `b40-documents` bucket currently have **no backup** — a bug or bad delete loses the crown-jewel documents irrecoverably. (Note: PITR would NOT fix this — it's also DB-only. Do **not** buy PITR for this.)
**Change:** a `manage.py backup_documents` command that enumerates all `b40-documents` objects and copies them to an off-platform store, run weekly via Cloud Scheduler (mirror the existing `halatuju-application-reminders` job + `X-Cron-Secret` cron-endpoint pattern).
**Owner decisions:** (1) destination — a GCS bucket in `gen-lang-client-0871147736`, or a Google Drive folder? (2) full re-copy vs incremental sync; (3) retention.
**Files:** new management command + cron-endpoint wiring + a Cloud Scheduler job; settings for the destination creds.
**Rails:** server-side **service-role** access only (never the client); never log document bytes/filenames with PII; verify the export contains all current objects (count match) on a test run; the destination must itself be access-controlled.
**Classification:** small feature (new command + cron) — borderline sprint; keep it contained, write a short retro.
**Interim (do today, no code):** Storage → `b40-documents` → select all → **Download** to Google Drive. That alone closes the immediate gap.

## Item B — Rate-limiting on sensitive endpoints
**Why:** posture #4. No global DRF throttling; brute-force/scraping on custom endpoints is unmitigated (the Supabase-auth login path is already rate-limited by Supabase, but the Django API isn't).
**Change:** add `DEFAULT_THROTTLE_CLASSES` + `DEFAULT_THROTTLE_RATES` (anon + user) in `halatuju_api/halatuju/settings/base.py`; add **scoped throttles** to the highest-risk endpoints: the public (`AllowAny`) **sponsor-pool** views, **document upload**, and confirm the existing AI-help cost-throttle stays. Pick limits comfortably above real traffic.
**Files:** `settings/base.py` + a handful of views. **Classification:** small-change-lane.
**Rails:** verify normal usage isn't throttled (test the apply flow end-to-end); throttles must not block the cron/internal endpoints.

## Item C — Captcha (Cloudflare Turnstile) on anonymous sign-ins + contact form
**Why:** posture #5 + Supabase's own recommendation; bot abuse on anonymous sign-ins bloats the DB and your billable MAU; contact-form spam. Already tracked as **TD-071**. Turnstile is free and you already use Cloudflare.
**Change:** add a Turnstile widget to the sign-in + contact forms (frontend), verify the token server-side, **then** enable Supabase Auth's "Enable Captcha protection" (Attack Protection page) wired to the Turnstile secret.
**Owner decisions:** create the Turnstile site+secret keys in Cloudflare.
**Files:** FE sign-in/contact components + a server-side verify step + new env vars (`NEXT_PUBLIC_TURNSTILE_SITE_KEY` public, `TURNSTILE_SECRET` backend-only).
**Rails — CRITICAL ORDERING:** do **NOT** flip Supabase's "Enable Captcha protection" toggle until the frontend is actually sending a valid Turnstile token in every auth call — otherwise **it blocks all logins**. Wire + test the full sign-in flow (student anon, admin password, sponsor) first, then enable. **Touches auth → treat with sprint care** (this is the one item I'd not rush).

## Item D — Breach / anomaly detection
**Why:** posture #6. Action-level audit data exists (`AssignmentEvent`, consents, verdict audit) but **nothing alerts** on an anomalous mass-read/export — a breach would be silent (the recurring theme across this whole review).
**Change (smallest viable first):** a Cloud Logging metric + alert policy (mirror the existing `halatuju-vision-outage` / SJKT `job-failure-alert` pattern) that notifies the admin email on a suspicious signal — e.g. an admin/bulk export of many application records in a short window, or an error/401 spike on the admin API. Ensure sensitive reads (admin viewing an application, document downloads) write an audit entry.
**Owner decisions:** what counts as "anomalous" (threshold); alert destination (admin email).
**Files:** logging/middleware + an alert policy (gcloud/YAML). **Classification:** design-light but start minimal.

## Item E — Explicit deny-policies on the deny-all tables
**Why:** posture #7. The 18 Django-mediated tables are RLS-on with **no policy** (= deny-all = already safe), but the repo's own standard says "RLS enabled **+ policies**" (`docs/incident-001-rls-disabled.md`). Adding explicit deny/`service_role`-only policies makes the intent legible and audit-clean.
**Change:** one migration adding an explicit `service_role`-only (or `USING (false)` for anon/authenticated) policy on each of the 18 tables. **Behaviour-neutral** (deny-all is already the effective state).
**Files:** one migration, applied **migrate-first via MCP**. **Classification:** small-change-lane.
**Rails:** behaviour-neutral — verify the app still reads/writes (it goes through Django/service-role, which bypasses RLS, so unaffected); re-run `get_advisors(security)` after — the `rls_enabled_no_policy` INFOs should clear.

---

## Suggested order
1. **A interim** (download bucket to Drive — today, free).
2. **E** (deny-policies — quick, behaviour-neutral, clears the advisor INFOs).
3. **B** (rate-limiting — contained, real value).
4. **A full** (scheduled bucket backup — highest value, a bit more work).
5. **D** (minimal detection alert).
6. **C** (Turnstile — most care, touches auth; do last, test hard).

## Owner decisions to settle at kickoff
- Bucket-backup destination (GCS vs Drive) + retention.
- Turnstile keys (create in Cloudflare).
- Detection thresholds + alert email.

## Definition of done
Each item: tested, deployed (≤2 deploys), verified in prod; `get_advisors(security)` re-run after any migration; CHANGELOG entry; the posture doc (`docs/security-posture.md`) hardening row updated to ✅. After the batch: one retro + a `wat_lint` / consolidation check per the workspace small-change-lane workflow.
