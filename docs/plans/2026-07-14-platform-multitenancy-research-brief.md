# Research Brief — HalaTuju Multi-Tenant Platform (Route A)

**Date:** 2026-07-14
**Commissioned by:** tamiliam (owner) — reviewed by the architect agent before anything is built
**Your role:** Research analyst / drafting engineer. You produce **documents only**. You do not build, fix, refactor, or deploy anything. Your output will be reviewed by a senior architect and the owner; expect it to be challenged, so every claim must carry evidence.

---

## 1. Context (self-contained — do not rely on outside memory)

HalaTuju is a live production system with two parts:

1. **Course selector** — SPM course recommendation for Malaysian students. Base product, owned and maintained by tamiliam.
2. **BrightPath scholarship** — a B40 scholarship programme (applications, income/document verification, reviewer workflow, offers, sponsors) currently welded into the same app.

**Stack:** Django API (`halatuju_api/`, apps: `courses`, `scholarship`, `reports`) + Next.js web (`halatuju-web/`), both on Cloud Run; Supabase for auth, Postgres and document Storage; Brevo for email; OpenAI/Gemini vision for document extraction. Read `halatuju_api/CLAUDE.md` and the root `README.md`/`CHANGELOG.md` before anything else.

**The decision already taken (do not reopen it):** HalaTuju becomes a **multi-tenant platform** (Route A — one codebase, one deployment, one database):

- The **course selector + student accounts are the shared platform base**, run by the platform superadmin (tamiliam).
- **Scholarships/bursaries become tenant programmes**, each run by a different organisation inside a walled garden: own org admins, reviewers, officers, sponsors, branding, eligibility configuration, email identity. **BrightPath becomes tenant #1.** A hypothetical second tenant ("Inspire scholarship", different target group, different team) is the design test case.
- Three role levels: platform superadmin (creates organisations, toggles which modules each gets) → organisation admin (configures and runs their programme, sees nothing outside it) → programme staff (existing reviewer/officer/sponsor roles, always org-scoped).
- **One student account, many programmes** — a student registers once at platform level and may apply to several programmes. Document reuse across programmes requires explicit student consent.
- The **verification engine** (document genuineness models, STR/income logic) stays **one shared platform service**. Tenants configure *which* checks and documents apply to their programme; they never get bespoke logic.
- Rejected alternatives: per-org white-label deployments (Route B) and spinning BrightPath into a separate codebase (Route C). Do not propose these.

---

## 2. Ground rules (non-negotiable)

1. **Read-only engagement.** No code changes, no migrations, no `git commit`, no `git push`, no deploys, no writes to any database or external service. Your only writes are the three deliverable documents named below.
2. If `git status` shows uncommitted work you did not create — **stop and report it**; do not commit it, do not build on top of it.
3. **Never read or print secrets.** Do not open `.env` files; never run `gcloud run services describe` with env output or any command that echoes credential values.
4. Do not touch production: no Cloud Run, no Supabase dashboard, no live URLs beyond public pages if needed.
5. **Every factual claim about the codebase must cite `file_path:line`** (or a directory for structural claims). If you infer something rather than read it, label it *INFERRED*. Keep a "could not verify" list — an honest gap beats a confident guess.
6. Where a decision belongs to the owner, write **`DECISION NEEDED:`** with 2–3 options and a recommendation — do not silently decide.
7. **British English** throughout. Write the main body in plain language for a non-technical owner; put code-level detail in appendices.
8. Read `../../Settings/_workflows/implementation-planning.md` (workspace workflow, absolute path `C:\Users\tamil\Python\Settings\_workflows\implementation-planning.md`) and follow its roadmap conventions for Deliverable 3.

---

## 3. Deliverable 1 — Tenancy Audit

**File:** `docs/plans/2026-07-14-tenancy-audit.md`

An evidence-based inventory of what is platform-level, what is tenant-level, and where BrightPath is hard-coded. Required sections:

1. **Model inventory.** Every Django model in `apps/courses`, `apps/scholarship`, `apps/reports`: one table row each with (model, app, proposed scope: `PLATFORM` / `TENANT` / `SHARED-CONFIG` / `UNCLEAR`, and why). Flag every foreign key that crosses the proposed platform↔tenant boundary — these are the future fence lines.
2. **Hard-coded BrightPath inventory.** Everywhere BrightPath-specific behaviour or wording lives in code rather than data: eligibility rules and thresholds (B40, STR, income logic), required-document checklists, application windows/intake gating, email templates and sender identity, branding/programme names in `halatuju-web` (including `en/ms/ta` i18n files), PDF/guide artefacts, feature flags. For each: location, what it does, and a proposed disposition — `PER-ORG SETTING` / `SHARED ENGINE, ORG-SELECTABLE` / `STAYS FIXED`.
3. **Identity & access map.** How Supabase auth roles work today (student, reviewer, officer, admin, sponsor): where roles are stored, how the API enforces them, what "org-scoping" would have to attach to. Include how reviewer/sponsor invites are issued.
4. **Storage & documents map.** How uploaded documents are keyed/pathed in Supabase Storage today, and what per-organisation fencing would require.
5. **External-service map.** Brevo (sender identities, templates), OpenAI/Gemini extraction (where keys are read, per-call cost points), Twilio (currently paused), Vircle eWallet (currently dark behind `VIRCLE_SETUP_ENABLED`), and anything else found. For each: what per-tenant attribution or separation would require.
6. **Coupling hot-spots.** The top ~10 places where courses↔scholarship are entangled and will make fencing hardest (shared models, shared views, shared frontend routes/components). Rank by expected pain.

## 4. Deliverable 2 — Draft PRD

**File:** `docs/plans/2026-07-14-platform-prd-draft.md`

A product requirements document for the platform, grounded in Deliverable 1. Required sections:

1. Vision & roles (the three levels above), with a plain-language walkthrough of each persona's day: platform superadmin, org admin, reviewer, student applying to two programmes.
2. **Organisation & module model** — what an "organisation" record contains; which modules exist and what toggling one on/off actually grants; what happens to a tenant's data if it is switched off (suspend vs delete — `DECISION NEEDED`).
3. **Configuration surface** — the definitive proposed list of per-organisation settings (from audit §2), each with type, default, and who may edit it. Be explicit about what is *not* configurable.
4. **Student account & consent** — single platform account; per-application data sharing; explicit consent flow for reusing previously uploaded documents across programmes; what an organisation can and cannot see about a student.
5. **Cost attribution** — options for metering per-tenant costs (AI extraction calls, email sends, storage), including "tenant brings own Brevo/API keys" vs platform-metered. Owner is cost-conscious (<$10/month platform baseline). `DECISION NEEDED` with recommendation.
6. **Data protection** — one page: what PII is processed per tenant, why a data-processing agreement per organisation is needed, and what the platform promises (isolation, deletion, breach notification). Plain language, not legalese.
7. **Non-goals for v1** — explicitly: no per-tenant custom code, no per-tenant deployment, no tenant self-signup (superadmin creates orgs manually), no billing automation.
8. **Open questions register** — every `DECISION NEEDED` collected in one table.

## 5. Deliverable 3 — Draft Multi-Sprint Roadmap

**File:** `docs/plans/2026-07-14-platform-roadmap-draft.md`

Following `implementation-planning.md` conventions. Constraints:

- **Phasing is fixed:** (1) Organisation layer + data fencing with BrightPath as sole tenant, invisible to users; (2) extract hard-coded rules into per-org settings, branding/email first, eligibility last; (3) platform superadmin portal; (4) second-tenant onboarding rehearsal. Sprints live inside these phases.
- Size sprints honestly: ~40 files touched max each; one coherent, reviewable deliverable per sprint; BrightPath must stay live and unbroken after every sprint. Don't cram — if the honest answer is 12 sprints, say 12.
- Per sprint: objective, key files/apps touched, migrations expected (count and nature), test plan, main risk + mitigation, and an explicit "how we know BrightPath still works" check.
- Include a **migration strategy note**: how existing BrightPath data gets re-homed under organisation #1 with zero downtime, and the rollback story.
- Include a **risk register** (top 10 across the programme) — data-leak-between-tenants risk must be #1 with its mitigation (e.g. org-scoped query managers + a test pattern that proves fencing).
- End with a **review checklist for the architect**: the 10 questions you'd want a reviewer to challenge you on.

---

## 6. Suggested working order

Audit first (it feeds everything), then PRD, then roadmap. The audit is the grunt work — expect to read a lot of code; use subagents for parallel read-only exploration if helpful. Budget your effort roughly 50% audit / 25% PRD / 25% roadmap.

## 7. Definition of done

- The three files above exist in `docs/plans/`, **uncommitted** (the owner and architect review before anything enters git history).
- Every codebase claim carries a `file:line` citation or an *INFERRED* label; the "could not verify" list is present.
- All decisions the owner must make appear as `DECISION NEEDED` entries with options and a recommendation.
- A closing summary (≤1 page, plain language) at the top of the PRD that the owner can read in five minutes.
