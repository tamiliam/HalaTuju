# HalaTuju — Roadmap

Last updated: 2026-11-05 (audit sprint A0.3)

## Status: v3.1.0 released, project audit closed 2026-11-12; feature freeze lifts Wed 18 Nov (owner ruling 2026-11-14, `docs/decisions.md`)

HalaTuju is live at [halatuju.xyz](https://halatuju.xyz). v3.0.0 (2026-10-06) was a complete bursary platform; **v3.1.0 (2026-11-05)** added the staff team and permissions, phone-native pages, exact offer-letter reading, post-award student care and one Overview page per staff member. Notes: [`docs/releases/release-notes-v3.1.0.md`](releases/release-notes-v3.1.0.md); the reasons: [`docs/decisions.md`](decisions.md); every change: [`CHANGELOG.md`](../CHANGELOG.md).

**The plan of record is the audit fix roadmap:** [`docs/plans/2026-11-05-audit-fix-roadmap.md`](plans/2026-11-05-audit-fix-roadmap.md) (from the project audit, [`docs/audits/2026-11-05-project-audit.md`](audits/2026-11-05-project-audit.md)). **Freeze:** lifted at the audit close on 2026-11-12 (closing section of the audit report). Team tables T5d and offer-letter S7 (paid) each still need the owner's word and a sprint-start. Named later sprints still run: W1 (by 20 Nov), F1 (by 27 Nov), Gemini duplicate (by 4 Dec), F2 (by 11 Dec).

Which feature flags are on in production: [`docs/deployment.md`](deployment.md), section "Live flag values". The open debt register: [`docs/technical-debt.md`](technical-debt.md). Plan files: [`docs/plans/`](plans/) (each has a Status line; finished ones are in `docs/plans/archive/`).

---

## What Shipped

### v1.0 to v2.0 (to 2026-03-20)

- SPM and STPM eligibility engines, quiz-based ranking, dashboard with merit traffic lights, Matric/STPM virtual courses, PISMP with the IPG campuses
- AI counsellor reports (Gemini), course search, saved courses and admission outcomes, student profile
- NRIC identity gate, Supabase auth (Google OAuth, anonymous sign-in, linkIdentity), EN/BM/TA
- Field taxonomy, MASCO career mappings, admin portal, custom domain halatuju.xyz, Cloud Build continuous deployment

### v2.x to v3.0.0 (2026-03 to 2026-10-06)

- The BrightPath bursary: application, documents with exact reading and genuineness checks, interviews, QC, awards and payments, sponsors and the sponsor pool
- Multi-tenant platform: organisations, programmes (gifts), staff roles, branding, billing and the Requests space
- WhatsApp outbound comms, partner comms, contract and bursary agreement modules (flags in the live flag table)

### v3.1.0 (2026-11-05)

- One Overview page for every staff member (Team tables T5c); the team, hats and permission catalogue v2 (T1 to T5)
- Phones: Mobile Standard, bottom sheet, student tab bar, every screen measured (M0 to M8); first-load JavaScript 228 kB to 144 kB
- Student maintenance after the award (Sprints 1 to 10): scholar file, results review, announcements, surveys, mentors, "My Bursary"
- Offer letters read exactly (S1 to S6), STPM exact read and CGPA from grades, Matric/Diploma exact read, third results route, Bumiputera and Islamic coverage
- Real invoices, tenant receipts, a paged Requests list
- Security patch: Next 14.2.35, image optimiser off

---

## Now: the audit fix roadmap

Waves, in order (detail and acceptance in the roadmap file): **Wave 0** ship what is ready and clean the register and documents (A0.1 to A0.3); **Wave 1** security and money (Next 15 upgrade first: A1.1 moves the web to Next 15.5.29 and React 19.2, deploy group G1); **Wave 2** live harm and speed; **Wave 3** structure with tests first; **Wave 4** remaining open debt by area. Every deploy group needs the owner's yes.

## Waiting on the owner

- Rulings listed in the audit fix roadmap, section "Owner decisions" (for example TD-487, TD-488, TD-496, TD-497, TD-499, TD-503)
- Phone/OTP login (CO-06): paid OTP, deferred. Students without a Google account still cannot use a phone number to sign in
- Cold starts and build minutes (TD-523): minimum instances cost money under the RM10 budget

## After the freeze (lifted 2026-11-12; each still needs the owner's word)

- Offer-letter exact read **S7** (paid live re-read of the S6-changed letters) and **S8** (the keep-exact gate)
- Team tables **T5d**; TD-501 (reviewer invite chooses one gift or every gift)
- A way to sign in as a reviewer, mentor, finance or QC on a local stack (TD-521)
- Bumiputera/Islamic coverage steps beyond F2; org timing settings Sprint 2 (waits on its trigger); sources and referrals sprints after A

## Still open from the earlier roadmap (not re-checked 2026-11-05)

These were on the v2.0 list. Each is kept only if the register still holds it; confirm in `docs/technical-debt.md` before working on one.

- Report generation has no loading indicator (10 to 15 second Gemini wait)
- 87 offerings missing tuition fee data (a data limitation, not a bug)
- Course `#` interview marker shown as raw text (TD-077)
- Account options on the Settings page (TD-041; the old TD-076 stub entry was merged into it)
- `course` field named `course`, not `name` (TD-024; cosmetic, needs a migration and a wide update)
- Institution proximity scoring (W8), grade modulation, `efficacy_domain` not used in ranking
- Annual STPM pipeline maintenance: test the MOHE scrapers before UPU season (see `docs/roadmap-course-data-pipeline.md`)

## Resolved since v2.0 (kept for the record)

- TD-025 (`api_` table prefix): the dead legacy table was dropped instead, 2026-06-01
- TD-047 (all-or-nothing startup data load): resolved 2026-10-01 (`CoursesConfig.ensure_data` retries)
- TD-076 (Settings stub): merged into TD-041; the version display is done

## Parked

- Lentera integration: HalaTuju as Beam 1 (Searchlight) within the broader Lentera programme
- Signal strength sync to Supabase (localStorage only today)
- Admin analytics: usage stats, grade distributions, course popularity
- The "coming soon" screens are features, frozen with the rest (audit CO-07)
