# Assistance-Recipient Portal — Proposal & Research Dossier

**Date:** 2026-06-19
**Status:** Proposal for discussion (nothing built yet beyond the existing `/scholarship/in-programme` page)
**Author:** Engineering (with tamiliam)
**Scope:** What the post-award "assistance recipient" experience should contain, how it fits the
existing one-login app, desktop + mobile layout, and the supporting research (architecture, cards,
payments, student-success resources, onboarding/legal, information architecture, duty-of-care).

---

## 0. The question we set out to answer

Should HalaTuju build a richer portal for students who have been *awarded* assistance — and if so,
what goes in it, how does it fit the menu when course-explorers, applicants and awardees all share
one login, should the common profile be extended, and what about contracts/T&C, monthly payments,
bank details, prepaid cards, and enrichment content? Desktop + mobile. Concrete proposal grounded
in best practice.

---

## 1. Ground truth — what the app does today

From reading the actual code:

- **One login, three "classes" of student**, distinguished only by *data*, not by a role field:
  a *course-explorer* (browses/saves courses), a *B40 applicant* (`status` = applied/under review),
  an *awardee* (`status = 'sponsored'`). The app infers the class from application status.
- **One shared profile page** (`halatuju-web/src/app/profile/page.tsx`) with 6 sections: identity,
  contact, address, family/income, application tracking, course interests. Everyone sees the same profile.
- **The recipient portal is currently an orphan.** `halatuju-web/src/app/scholarship/in-programme/page.tsx`
  exists but **nothing in the menu links to it** — reachable only programmatically. First real gap.
- **Already exists post-award:** `SemesterResult`, `GraduationMessage`, promotional consent, an
  onboarding questionnaire (`OnboardingResponse`), award accept/decline
  (`halatuju-web/src/app/scholarship/award/page.tsx`) with a guardian modal for minors.
- **Does NOT exist at all yet:** bank details, any payments/disbursement ledger, a formal
  agreement/T&C acceptance record, a comprehension quiz, a card. Real-money disbursement is gated
  behind `SPONSOR_POOL_ENABLED` (off).

---

## 2. Information architecture — how it fits the menu

The three classes are **stages of one journey** (explore → apply → receive), not personas. So:

- **Stable primary nav, content adapts by state — don't make users pick a role.** Infer the state
  and re-prioritise the **Dashboard**; keep the nav constant. (This is how StudentAid.gov works:
  one login, dashboard shows application status to applicants and payment/grant history to recipients.)
- **Primary destinations, not tabs, for the three big functions:**
  `Home · Courses · My Application · My Aid · More`. **My Aid** lights up once sponsored.
- **Tabs only *within* a destination,** capped at 3–4 (NN/g). Inside **My Aid**:
  **Overview · Money · Progress · Support**. The one-time **Agreement** step folds into the Overview
  onboarding checklist rather than a permanent tab.
- **Mid-application = a GOV.UK-style task list** (one-thing-per-page, resumable across sessions).
- **Keep the shared Profile as the single identity record** for everyone — don't fork it. Recipient-only
  financial data (bank details) lives in **My Aid → Money**, not bloating the shared Profile.

**Separate, larger UX decision this surfaced:** on mobile the evidence strongly favours a **bottom
navigation bar** (thumb-zone, ≤5 items) over the current top hamburger (~30%+ better feature discovery;
hamburgers tank discoverability for low-confidence users). That touches the *whole app's* navigation, so
treat it as its own decision, not part of this work.

**Revised IA in one line:** stable `Home · Courses · My Application · My Aid · More` spine + a
state-aware Home dashboard + ≤4 tabs inside *My Aid* (Overview/Money/Progress/Support).

---

## 3. What goes in the recipient hub (feature catalogue)

✓ = already built.

**Tab 1 — Overview (home)**
- Welcome + award summary (amount, monthly figure, start/end).
- **Onboarding checklist** that gates first payment: ① accept offer ✓ ② agree to T&C (with quiz)
  ③ add bank details ④ upload enrolment proof. Progress bar.
- Next payment date + status; latest announcement.
- "Conditions of your assistance" at a glance.

**Tab 2 — Money**
- **Bank details** (account name, bank, account number / DuitNow ID). Verify before first payout.
- **Payment history / statement** — date · amount (RM) · status (Paid/Pending/Failed) · reference ·
  masked destination (****1234) · downloadable.
- Next scheduled payment; failed-payment alert + "fix your details" prompt.
- **Card display (only if a card programme is ever adopted, later):** name + last-4 + balance +
  transactions only — never full PAN/CVV/PIN.

**Tab 3 — Progress & accountability**
- Semester results upload ✓ (move here).
- **Per-semester enrolment proof** re-upload (confirms still studying before next disbursement).
- Conditions tracker: CGPA threshold met? report submitted? — green/amber, reusing existing colour language.

**Tab 4 — Support & resources**
- Thank-your-sponsor ✓ + promotional consent ✓ (move here).
- **Lightweight curated resources** — a short linked list with review dates, NOT a CMS.
- **Event-driven nudges** (results day, enrolment deadline, CGPA dip) rather than evergreen articles.
- Contact / help; (later, carefully) a light mentor/check-in touchpoint.

**Folded into Overview (one-time):** Agreement + comprehension quiz; onboarding questionnaire ✓.

**Considered but deferred:** at-risk flag → human check-in (high value, but safeguarding/PDPA weight —
see §10); announcements channel; clawback wording lives in the agreement.

---

## 4. Concrete layout

**Desktop** (wider than the current `max-w-md`):
```
┌───────────────────────────────────────────────┐
│  HalaTuju        Dashboard  Search  My Assistance ▾  👤 │
├───────────────────────────────────────────────┤
│  My Assistance                                  │
│  [Overview][Money][Progress][Support]           │  ← ≤4 tabs
│  ┌─────────────────────┐  ┌──────────────────┐ │
│  │ Award: RM300/month  │  │ Onboarding 3/4 ●●●○│ │
│  │ Until: Dec 2027     │  │ Add bank details →│ │
│  └─────────────────────┘  └──────────────────┘ │
│  Next payment: 1 Jul 2026 · RM300 · Scheduled   │
└───────────────────────────────────────────────┘
```

**Mobile** (phone-first card style; tabs as a short strip):
```
┌─────────────────┐
│ ‹ My Assistance │
│ [Overview][Money…│ ← ≤4 tabs
│ ┌─────────────┐ │
│ │ RM300/month │ │
│ └─────────────┘ │
│ Onboarding 3/4  │
│ ▸ Add bank deta…│
└─────────────────┘
```

Same components, responsive container (single column on mobile; two-column + persistent tabs on desktop).

---

## 5. Data model additions (engineering view)

New models (minimal fields):
- `AwardAgreement` — version, accepted_at, accepted_by (guardian for minors), quiz_score, ip, t&c_version.
- `BankAccount` — account_name, bank, account_number (encrypted at rest), duitnow_id, verification_status, verified_at.
- `Disbursement` — month, amount, status (scheduled/paid/pending/failed), reference, failure_reason.
- `DisbursementSchedule` — cadence, next_run, active.

**Security rules:** never store full card numbers/CVV; encrypt bank account numbers at rest with
documented key management; mask to last-4 in UI; never log full numbers; PDPA consent + retention limits.

---

## 6. Suggested phasing (cost-conscious)

1. **Sprint A — Navigation + hub shell.** Conditional "My Assistance" nav item, state-aware Dashboard
   card, tabbed shell wrapping what exists (results, thank-you, promo). Unblocks the orphan page. Low risk, no money.
2. **Sprint B — Agreement + quiz + guardian-as-signer.** Legally load-bearing (see §9).
3. **Sprint C — Bank details + payment history (display/manual first).** Capture details, show a
   statement you populate manually while paying by normal transfer. No live money movement.
4. **Sprint D — Automated disbursement (IBG bulk + DuitNow name-check) + enrolment-gated payments.**
   The real-money step, behind the existing flag, only when ready.
5. **Later / optional — resources polish; at-risk check-in (safeguarding groundwork first); card programme** if ever justified.

---

## 7. Decisions needed from the user

1. **Disbursement rail:** recommendation → **IBG bulk file for the monthly run + DuitNow Name Enquiry
   for onboarding verification**; prepaid card only later, only if recipients are unbanked or spend-control matters.
2. **Payments now or later:** automated ledger soon, or manual "payment history" first while paying by transfer?
3. **Quiz as a hard gate** (must pass to unlock payment) or soft "please read"?
4. **Bank details location:** in the hub's Money tab (recipient-only) — recommended — vs the shared Profile?
5. **Resources scope:** minimal vetted link list (recommended) vs something richer.

---

# Research Dossier (seven streams, with sources)

## R1. Navigation / auth / profile architecture (codebase map)
Summarised in §1–§2. Key files: `AppHeader.tsx` (nav), `auth-context.tsx` (anonymous / needs-nric /
ready), `profile/page.tsx` (6-section shared profile), `models.py` + `in_programme.py` (post-award models),
`award/page.tsx` + `onboarding/page.tsx`. The in-programme page is reachable only when `status='sponsored'`
and has **no menu link**. Missing entirely: bank details, disbursement ledger, agreement/T&C record, card.

## R2. Prepaid / disbursement cards
- **Swipey is a B2B corporate expense-management product** (cards for employees/vendors), built on
  **Fasspay** (BNM-licensed e-money issuer). Wrong tool for paying many external beneficiaries; for a
  card programme you'd engage the underlying issuer/BaaS directly and ask about bulk issuance, mass-load,
  MCC controls, and the fee schedule.
- **Cards fit only if** recipients are genuinely **unbanked** or you need **MCC spend-control**.
  Otherwise **DuitNow transfer / e-wallet top-up is cheaper and lower-friction.**
- **Dormancy/reload/ATM fees** quietly erode small stipends — a real risk with cards, near-zero with DuitNow.
- **Minors can't hold a standalone card in Malaysia** — off-the-shelf models (Hong Leong Junior Debit,
  Maybank imteen-i, CIMB YOUth Savers) require a **guardian-linked account + guardian indemnity letter**.
- **If a card is ever displayed:** name + last-4 + balance + transactions only (PCI). Store nothing card-sensitive.

Sources: [Swipey/Fasspay FAQ](https://swipey.co/faqs/), [Swipey cards](https://swipey.co/cards/),
[Hong Leong Junior Debit Card](https://www.hlb.com.my/en/personal-banking/debit-cards/debit-card/junior-debit-card.html),
[Maybank imteen-i](https://www.maybank2u.com.my/maybank2u/malaysia/en/personal/accounts/savings/imteen_i_account.page),
[CIMB YOUth Savers](https://www.cimb.com.my/en/personal/day-to-day-banking/accounts/savings-account/youth-savers-account.html),
[U.S. Bank — prepaid disbursement](https://www.usbank.com/corporate-and-commercial-banking/insights/payments-hub/cards/prepaid-cards-disburse-government-funds.html),
[UNHCR cash vs card](https://www.unhcr.org/us/news/stories/cash-assistance-gives-refugees-power-choice),
[PCI DSS Req 3](https://pcidssguide.com/pci-dss-requirement-3/).

## R3. Disbursement / payments
- **PCI does NOT apply to bank account numbers** — they're out of PCI scope but **more sensitive**
  (static, never expire). Encrypt at rest, mask last-4, restrict access, never log. Real exposure = **PDPA + guardian consent**.
- **Two rails:** **IBG bulk file** for the cheap monthly batch (~RM0.10/txn, next business day, payroll-style);
  **DuitNow Name Enquiry** (mandatory in PayNet's API) for free real-time payee-name confirmation at onboarding.
  Require a **name match before first payout.**
- **Failed payments:** hard fails (closed/invalid account, name mismatch → don't retry, prompt to fix) vs
  soft fails (timeout/outage → retry next batch). Add a finance ops queue.
- **AML — don't over-build:** a grant-making NGO paying its own beneficiaries is generally **not** a
  reporting institution; FATF R8 (2023) says NPOs get *proportionate* oversight, not full CDD. Sensible
  controls: sanctions-screen against MOHA/UNSCR lists, verify identity + name match, keep audit trails
  (also satisfies ROS annual returns).

Sources: [PayNet DuitNow API](https://docs.developer.paynet.my/docs/duitnow-transfer/introduction/overview),
[Wise — IBG vs DuitNow](https://wise.com/my/blog/ibg-vs-duitnow),
[PCI data storage do's & don'ts](https://listings.pcisecuritystandards.org/pdfs/pci_fs_data_storage.pdf),
[Modern Treasury — bank-data sensitivity](https://www.moderntreasury.com/journal/what-is-the-pci-of-bank-payments),
[Tookitaki — AML Malaysia](https://www.tookitaki.com/compliance-hub/aml-compliance-malaysia-bnm-amlatfpuaa),
[FATF R8](https://www.fatf-gafi.org/en/publications/Fatfrecommendations/protecting-non-profits-abuse-implementation-R8.html),
[Gr4vy — retry logic](https://gr4vy.com/posts/payment-retry-logic-explained-smart-retries-for-failed-transactions-in-2026/),
[Papaya — penny-drop verification](https://www.papayaglobal.com/blog/a-complete-guide-to-penny-drop-verification/).

## R4. Student-success / enrichment resources
- **Lead with cash certainty + a light human touch, not a content library.** Strongest-evidence
  programmes (Posse ~90% grad, Sutton Trust, QuestBridge) win on **mentoring/relationships**.
- **Unguided content gets ignored; broadcast nudges show ~zero effect.** Gains come only when a nudge is
  **just-in-time, tied to a real deadline, from a trusted source, aimed at high-risk students.**
- **Keep enrichment thin:** curated external links *with review dates* (self-pruning), event-driven nudges,
  a light mentor/contact point. The bigger lever is a **human check-in tied to the at-risk flag.**
- **Financial literacy:** bite-sized + experiential beats workshops; knowledge decays without reinforcement;
  **behavioural defaults move young/low-income savers more than information.**

Sources: [Posse Foundation](https://www.possefoundation.org/supporting-scholars/career-program),
[Sutton Trust Online](https://www.suttontrust.com/news-opinion/all-news-opinion/new-digital-platform-sutton-trust-online/),
[EdResearch — summer melt](https://edresearchforaction.org/research-briefs/helping-students-make-it-to-college-evidence-based-design-principles-for-reducing-summer-melt/),
[Castleman & Page — summer nudging](https://www.sciencedirect.com/science/article/abs/pii/S0167268114003217),
[Kitchen et al. 2025 — peer mentoring](https://journals.sagepub.com/doi/10.1177/01614681251334786),
[Frontiers — youth financial literacy](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2024.1397060/full),
[Financial literacy is not enough](https://www.sciencedirect.com/science/article/abs/pii/S0148296320300746).

## R5. Onboarding & formal acceptance (legal)
- **⚠️ Minors can't validly accept your agreement.** The Contracts (Amendment) Act 1976 only validates
  minor scholarship contracts where the sponsor is **government / statutory / an approved educational
  institution**. A **private NGO is outside it** → under the Contracts Act 1950 a minor's direct agreement
  is **void**. **→ For under-18s the parent/legal guardian must be the binding contracting party /
  guarantor** who gives acceptance. Get a Malaysian lawyer to confirm the structure before launch.
- **Mechanics are simple & cheap:** clickwrap "I Agree" + audit record is valid under the Electronic
  Commerce Act 2006 s.9 — no licensed digital signatures needed. Use **scrollwrap** (must scroll terms
  before Accept), a separate non-pre-ticked checkbox, and store timestamp + ID + IP + exact T&C version. Version your T&C.
- **Comprehension quiz:** keep it, framed as *informed-consent evidence* (defensive), not a proven comprehension-booster.
- **Standard clauses:** maintain CGPA / academic standing · semester progress report · stay enrolled ·
  defined use of funds · code of conduct · clawback on withdrawal/breach · guarantor clause (doubles as
  the minor-validity fix). **Keep penalties proportionate** — heavy clawback against a B40 minor risks
  unconscionability + reputational blowback.

Sources: [Dropbox Sign — e-sign Malaysia](https://sign.dropbox.com/esignature-legality/malaysia),
[AskLegal — minor capacity](https://asklegal.my/p/child-minor-sign-contract-malaysia-act-capacity-employment-marriage),
[Contracts (Amendment) Act 1976](https://www.lawyerment.com/library/legislation/acts/1976/A329/section/),
[TermsFeed — clickwrap/scrollwrap](https://www.termsfeed.com/blog/clickwrap-browsewrap-scrollwrap/),
[Sunway scholarship T&C](https://scholarship.sunway.edu.my/scholarship-terms-conditions),
[JPA loan repayment](https://www.jpa.gov.my/en/loan-repayment-compensation).

## R6. Portal information architecture
Summarised in §2. Key principles: state-aware dashboard (not role toggle); persistent primary
destinations for the three functions; tabs only for parallel views within a destination (cap 3–4);
GOV.UK task list for the application journey; mobile bottom-nav (≤5, thumb-zone) over hamburger; same IA
as a desktop sidebar; keep nav stable, change only the default emphasis.

Sources: [NN/g — Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/),
[NN/g — Tabs](https://www.nngroup.com/articles/tabs-used-right/),
[NN/g — Mobile Navigation](https://www.nngroup.com/articles/mobile-navigation-patterns/),
[NN/g — Portal Personalization](https://www.nngroup.com/articles/intranet-portals-personalization/),
[GOV.UK — Navigate a service](https://design-system.service.gov.uk/patterns/navigate-a-service/) +
[Task list](https://design-system.service.gov.uk/components/task-list/),
[StudentAid.gov — account](https://studentaid.gov/articles/key-facts-accounts/),
[Smashing — bottom navigation](https://www.smashingmagazine.com/2019/08/bottom-navigation-pattern-mobile-web-pages/),
[Finovate — US Bank mobile nav](https://finovate.com/ui-us-bank-tackles-new-mobile-navigation-conventions/).

## R7. Engagement, retention & duty of care
- **Highest-impact lever:** a **human check-in triggered by an at-risk flag**. Two-way SMS nudges
  (Georgia State "Pounce": melt 19%→9%) work best when they point to *concrete support*. At-risk trigger
  should be **multi-signal** — CGPA dip + missed check-in + **skipped monthly claim** (payment-gap data
  you already have). **Define the intervention before the detector**; standardise follow-up; rules-based tier (auditable).
- **Safeguarding (minors):** **no unmonitored 1:1 adult-mentor↔minor contact** — route all comms through
  monitored channels (in-app or WhatsApp Business broadcast), never a mentor's personal WhatsApp. Needs a
  safeguarding policy + Designated Safeguarding Lead + mentor vetting before any mentoring feature ships.
- **PDPA 2024 amendment (in force Jan 2025):** mandatory breach notification, mandatory DPO appointment,
  wellbeing-survey data likely **sensitive → explicit consent + restricted access**, penalties up to RM1m.
  SMS/WhatsApp vendor is a **data processor with direct liability → need a DPA**. No explicit minors-consent
  statute → **default to guardian consent.**
- **Roadmap effect:** mentoring/check-in is high-value but compliance-heavy → a later, carefully-scoped
  sprint with policy groundwork first. Early safe version = an **automated, logged, in-app/SMS nudge tied
  to the at-risk flag** (no human 1:1, no new compliance surface).

Sources: [Georgia State "Pounce" — Mainstay](https://mainstay.com/case-study/how-georgia-state-university-uses-behavioral-intelligence-to-improve-student-retention-and-persistence/),
[JFF — nudging to holistic supports](https://www.jff.org/nudging-students-toward-holistic-supports-and-postsecondary-success/),
[Kitchen et al. 2025 — peer mentoring](https://journals.sagepub.com/doi/10.1177/01614681251334786),
[EAB — early-alert design](https://eab.com/resources/blog/student-success-blog/3-reasons-why-your-early-alert-program-is-falling-short/),
[Mayer Brown — PDPA 2024 amendment](https://www.mayerbrown.com/en/insights/publications/2025/07/from-legislative-reform-to-practical-guidance-key-amendments-to-malaysias-pdpa-and-the-launch-of-cross-border-transfer-guidelines),
[NSPCC — safeguarding in the voluntary sector](https://learning.nspcc.org.uk/safeguarding-child-protection/voluntary-community-groups),
[NCVO — vetting staff/volunteers](https://www.ncvo.org.uk/help-and-guidance/safeguarding/steps-safer-organisation/choosing-staff-volunteers-trustees/).

---

## Headline takeaways

1. **Unblock the orphan page first** (nav + hub shell) — cheap, no money, immediate value.
2. **The Agreement is the legally load-bearing piece — guardian-as-signer for minors is non-negotiable.**
3. **Pay via IBG bulk + DuitNow name-check; cards only later, only if justified.** Watch fee drag on small stipends.
4. **Keep resources thin; the real lever is a human check-in on the at-risk flag** — but that carries
   safeguarding + PDPA weight, so do it later with policy groundwork.
5. **Don't over-build for PCI** (it doesn't apply to bank data); spend the effort on **PDPA, encryption-at-rest,
   and name verification** instead.
