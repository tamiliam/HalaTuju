# Public copy — coherence revisions (DRAFT for review)

**Status:** Draft only. Nothing deployed. Prepared after the 2026-06 audit of public copy vs. the
system's actual behaviour. Items marked **⚖️ LAWYER** should be reviewed by a lawyer before publishing;
items marked **🟦 DECISION** need a product/comms call from you. Everything else is plain alignment of
words to what the system actually does.

---

## 0. The one decision that drives the sponsor copy 🟦

**Is the sponsor side taking real money yet?** Today it is **not**: donations are mock-only (no toyyibPay),
no funds are disbursed to students (deferred), and the Yayasan myNADI partnership is "being finalised."
So sponsor copy that says "fund a student / every ringgit tracked / funds are held and released by myNADI"
describes a pipeline that **isn't live**.

Two honest options:
- **(A) "Pledge / register interest" framing** (recommended while money is mocked): sponsors register and
  commit support; actual funding goes live once the myNADI + payment mechanism is ready.
- **(B) Keep "fund now" framing** only once real donations + disbursement are actually live.

The drafts below assume **(A)** + the same "(partnership being finalised)" honesty the *scholarship* page
already uses. Tell me if you'd rather (B) and I'll adjust.

---

## 1. Sponsor landing — tone the money claims to match reality
File: `halatuju-web/src/components/SponsorLanding.tsx` (copy lives in `src/messages/en.json`, keys under `sponsorLanding.*`; mirror in ms/ta).

| Key | Current | Proposed |
|---|---|---|
| `promises.card2Title` | "Every ringgit tracked" | "Every ringgit accountable" |
| `promises.card2Desc` | "Funds are held by Yayasan myNADI and released against verified study milestones, never handed over directly." | "Funds will be administered by Yayasan myNADI and released against verified study milestones — never handed directly to a student. *(Partnership being finalised.)*" |
| `how.step4Desc` | "Fund their studies and follow their progress along the way." | "Commit your support and follow their progress along the way." |
| `faq.a2` ("Where does my money go?") | "Funds are held by Yayasan myNADI and released against verified study milestones. Money is never handed directly to a student." | "Funds will be administered by Yayasan myNADI (a registered non-profit) and released against verified study milestones — never handed directly to a student. We're finalising this partnership." |
| `faq.a6` | "HalaTuju runs the B40 Assistance Programme together with Yayasan myNADI, which holds and disburses the funds." | "HalaTuju runs the B40 Assistance Programme; Yayasan myNADI will hold and disburse the funds *(partnership being finalised)*." |
| `hero.sub` | "…anonymously, with every ringgit accounted for." | Keep (it's a principle) — or "…anonymously, with funds independently administered." |

*Note:* the scholarship page already hedges myNADI three times with "(Partnership being finalised.)" — these
changes simply bring the sponsor page into line with that honesty.

---

## 2. Privacy Policy — full rewrite (it currently describes only the course tool) ⚖️
File: `halatuju-web/src/app/privacy/page.tsx`. The current page omits document uploads, OCR/AI processing,
and the sponsor programme, and wrongly says "we do not share with third parties." Proposed replacement body
(plain-language; **lawyer to confirm PDPA wording + the data-controller entity**):

> **Last updated: June 2026**
>
> HalaTuju provides two things: a free **course-matching tool** for SPM/STPM students, and the **B40
> Assistance Programme**, which connects verified low-income students with sponsors who support their public
> tertiary studies. This policy covers both.
>
> **Data we collect**
> - *Course tool:* your IC number (NRIC, stored securely and shown only masked, e.g. \*\*\*\*-\*\*-1234),
>   SPM/STPM grades, optional profile details (name, gender, nationality, state, contact details, family
>   background), optional quiz answers, and your sign-in identifier (phone number or Google account).
> - *Assistance Programme (only if you apply):* household and family income details, and **documents you
>   upload** to verify your application — your IC, results slip, university/college offer letter, a
>   parent/guardian IC, and proof of household income or aid (e.g. an STR letter, EPF statement, payslip, or
>   utility bill).
>
> **How we use and process your data**
> - To generate course recommendations and to assess and administer assistance applications.
> - **Automated processing:** to help us read and check your documents, we use automated text-recognition
>   and AI services (Google Cloud Vision and Google Gemini) to extract text from uploaded documents and to
>   prepare an anonymised profile for sponsors. We also use an automated rule to check eligibility against
>   the published criteria. **These are decision-support tools — a person reviews your application before any
>   decision**, and you can ask us to review any automated outcome.
> - To send you relevant follow-up emails (e.g. assistance opportunities, important changes). You can
>   unsubscribe at any time.
>
> **Who we share it with**
> - **Service providers that process data on our behalf:** Supabase (secure database hosting, Singapore
>   region) and Google (the text-recognition and AI services above). They process your data only to provide
>   these services to us.
> - **The administering non-profit (Yayasan myNADI)** — for applicants accepted into the Assistance
>   Programme, to administer the support. *(Partnership being finalised.)*
> - **Sponsors** — only an **anonymised profile** (e.g. field of study, region, academic band), and only
>   **after you give explicit consent** (for applicants under 18, a parent or guardian must consent). Sponsors
>   **never** see your name, IC, address, phone, email, photo, or your parents' details.
> - We **do not** sell your data or share it for unrelated third-party marketing.
>
> **Keeping and deleting your data**
> - We keep your data while your account is active and for as long as needed to administer the programme and
>   meet legal obligations. You may request deletion of your account and data at any time. Certain limited
>   data is purged automatically — for example, the contact details of an unconverted sponsor-referral invite
>   are removed after 60 days.
>
> **Your rights**
> - You may access, correct, or delete your data, and withdraw consent (including a sponsor-sharing consent)
>   at any time. Use the [contact form](/contact) (there's a "Data Deletion Request" option).
>
> **Security**
> - Your data is stored on Supabase (Singapore region) with row-level security; sensitive data, including
>   your IC, is encrypted at rest and in transit.
>
> **Minors**
> - Many of our users are school-leavers. If you are under 18, a parent or guardian must consent before your
>   profile is shared with any sponsor.
>
> ⚖️ **For a lawyer:** name the data controller (the responsible legal entity, e.g. Yayasan myNADI / the
> coordinating body) and the PDPA 2010 basis for processing + cross-border transfer (Singapore/Google).

---

## 3. Terms of Use — extend scope + add minors ⚖️
File: `halatuju-web/src/app/terms/page.tsx`. Current terms describe only "a public service tool for exploring
SPM/STPM course options." Proposed additions (keep the existing course-tool + "as is" + "no guarantee of
admission" clauses; **add**):

> **Last updated: June 2026**
>
> **Scope.** HalaTuju provides a free course-matching tool and operates the B40 Assistance Programme. Using
> either means you accept these terms.
>
> **The Assistance Programme.** Applying does **not** guarantee assistance — places are limited and subject to
> eligibility checks and a human review. Assistance is a gift, not a loan; there is nothing to repay. Funds
> (where a sponsor supports a student) are administered by the programme's non-profit partner and are never
> paid directly to a student. *(Partnership being finalised.)*
>
> **Sponsors.** Sponsor contributions support students through the programme's administering non-profit; they
> are not a direct transfer to a student and are not a commercial transaction. *(More detailed sponsor terms
> to follow.)*
>
> **Minors.** If you are under 18, you may use the course tool, but a parent or guardian must give consent
> before you apply for assistance or before your profile is shared with any sponsor.
>
> **Accuracy & honesty.** You are responsible for the accuracy of what you submit; misrepresenting your
> identity, grades, or income may result in disqualification or account suspension.
>
> ⚖️ **For a lawyer:** governing law/jurisdiction (Malaysia), the contracting entity, and proper sponsor terms.

---

## 4. Cookie Policy — light update
File: `halatuju-web/src/app/cookies/page.tsx`.
- Change "Last updated: March 2026" → **June 2026**.
- The existing copy is otherwise accurate (no analytics/tracking cookies — confirmed; auth via Supabase;
  language + profile data stored locally). One small addition under "Profile data": note that uploaded
  **assistance documents are stored on our server, not in your browser** — so users don't think their IC
  image is "only on their device."

---

## 5. Smaller coherence fixes

| Where | Current | Proposed | Why |
|---|---|---|---|
| **Scholarship** `note.confidentialText` | "shared only with the programme coordinators, the administering NGO, and any sponsor you specifically consent to." | *Keep* — it's accurate. The fix is to make the **Privacy page** agree with it (done in §2). | Privacy page said "no third-party sharing" — the contradiction is resolved by rewriting Privacy, not this line. |
| **About** `about.whoP2` | "…community organisations like Yayasan myNADI and Concerned UM Indian Graduates (CUMIG)…" | "…community organisations. Yayasan myNADI, our non-profit partner, administers assistance funds; groups like Sri Murugan Centre (SMC) and CUMIG refer and support students." | About lumps myNADI as a generic community org; elsewhere it's *the* funds administrator. Also: the About page never mentions the Assistance/sponsor programme — consider a short paragraph linking to it. |
| **Main landing** `landing.readySubtitle` | "Join thousands of students who have found their ideal course…" | "Join hundreds of students who have found their course with HalaTuju…" (or use a real figure once you have one) | ~676 students today; "thousands" is unsubstantiated. |
| **Scholarship** `req.item3` | "at least 5 A's in SPM, or a PNGK of 3.0 or above in STPM" | Confirm against the live cohort (`min_spm_a_count`, `min_spm_bplus_count`, `min_stpm_pngk`); the engine's bar is ~4 A's + 5 B+. Either align the headline or rely on the existing "our bar is more generous" note (already present). | Headline is stricter than the actual rule. |
| **Sponsor landing** `promises.card1Title` | "Complete anonymity" | "Full anonymity to sponsors" (or keep — the FAQ wording is precise) | Trusted sponsors see institution + region + field + academic band; "complete" slightly overstates. Minor. |
| **Contact emails** | `info@halatuju.xyz` (scholarship) + `sponsor@halatuju.xyz` (sponsor) | Confirm `sponsor@halatuju.xyz` is a live mailbox (or point both at `info@`). | Avoid a dead public contact. |

---

## 6. Suggested order of work
1. **Sponsor money copy (§1)** + the **"thousands"** line (§5) — quick, removes the clearest overclaims.
2. **Privacy Policy (§2)** — the real legal exposure; gate on your lawyer's pass.
3. **Terms (§3)** + **Cookies date (§4)** — with the lawyer.
4. **About / minor wording (§5)**.

i18n: every change above is en/ms/ta (parity-checked) — Tamil/BM will need translation (I can draft first-pass
ms/ta and flag for your refinement).
