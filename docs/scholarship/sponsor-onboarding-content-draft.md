# Sponsor Onboarding — Content Draft (disclosures · comprehension quiz · donor agreement)

> **Status: WORKING DRAFT — best available knowledge, pre-lawyer.** This is *not* legal advice. It is written so we can
> (a) build the auto-onboarding flow (Phase E4) against real wording, and (b) demo a *visibly mostly-ready* system to
> myNADI and the anchor sponsor. A lawyer vets and hardens this **near the end**, before any real money or real student
> data goes live. Until then everything runs on **dummy students + mocked donations** behind the `SPONSOR_POOL_ENABLED`
> flag, so none of this content is binding on anyone yet.
>
> **British English.** Warm, respectful, plain — a sponsor should finish genuinely understanding what they are doing.
> **Versioned:** ship under `SPONSOR_AGREEMENT_VERSION = '2026-draft-1'`. Bump on any wording change; an approved sponsor
> re-acknowledges the new version before their next funding action.

This document feeds **three** places in the product:
1. **§A Disclosure cards** → the "Understand the commitment" wizard step (each card has its own *I understand* tick).
2. **§B Comprehension quiz** → the must-pass check (retry on a wrong answer).
3. **§C Donor agreement** → the final e-signed terms (typed full name + version + timestamp).

Plus **§D Quick declarations** (an earlier, lighter wizard step) and **§E notes for the lawyer / open items**.

---

## §A — The seven disclosure cards

Each card is shown on its own, with a single **"I understand"** checkbox. The sponsor cannot continue until it is ticked.
Each acknowledgement is stored with its card code + the agreement version + a timestamp.

### A1 · `donation_is_final` — This is a donation, not an investment
When you put money in, it becomes a **donation to myNADI** (under Tamil Foundation). It is no longer your money. You are
**not** buying anything, lending anything, or investing — there is no return, no interest, and no share of anything. You
are giving, generously, to help a student.

> ☐ **I understand that my contribution is a donation, not an investment, and I expect nothing back in return.**

### A2 · `no_bank_refund` — You cannot get the money back to your bank
Because it is a donation, it **cannot be refunded to your bank account** — not if you change your mind, and not if a
student declines. What you *can* do is **redirect it within myNADI**: the money sits in your **giving balance**, and you
choose which student it helps. If a match falls through, the amount simply returns to that balance for you to give to
someone else. It never leaves myNADI back to you.

> ☐ **I understand I cannot withdraw my donation to my bank; I can only direct it to students within the platform.**

### A3 · `permanent_anonymity` — You will never know who you helped
To protect vulnerable students, the programme is **permanently anonymous**. You will **never** see a student's name,
photograph, school, identity-card number, or contact details — not while choosing, not after you fund them, not ever.
You will see only a respectful, non-identifying summary of their situation and their need.

> ☐ **I understand I will never learn the identity of any student I sponsor, and I will not attempt to find out.**

### A4 · `tranches_and_withholding` — The money is released in stages, tied to progress
An award is not handed over in one lump. It is released to the student's institution in **stages ("tranches")** — for
example, part on acceptance and the rest as the student shows genuine progress. If a student does not progress, a stage
can be **withheld**, and that part of the award is **stopped** and returns to your giving balance to help someone else.
This protects your generosity and keeps it tied to real effort.

> ☐ **I understand awards are paid in stages tied to the student's progress, and a stage may be withheld if they do not progress.**

### A5 · `fund_a_need_not_a_person` — You are funding a need, not choosing a person
You are not "picking" a child or forming a personal relationship. You are choosing a **need to meet**. You will have no
say over the student's choices, no special access to them, and no role in their life beyond your gift. myNADI manages the
relationship, the checks, and the release of funds.

> ☐ **I understand I am funding a need, not selecting or mentoring a particular individual, and I will have no relationship with them.**

### A6 · `charitable_gift_and_tax` — This is a charitable gift
Your donation is a **charitable contribution** to myNADI / Tamil Foundation. Any tax treatment (such as a receipt for
relief, where available) depends on the foundation's status and the rules at the time, and will be confirmed to you
separately — it is **not** a reason for, or a condition of, your gift.

> ☐ **I understand this is a charitable gift, and any tax receipt depends on the foundation's status and is confirmed separately.**

### A7 · `conduct_and_privacy` — How you will conduct yourself, and how we handle your data
You agree to act in the student's best interest: you will **not** try to identify, contact, or influence them, and you
will keep anything you see in the programme confidential. In turn, myNADI handles **your** personal data under the
Personal Data Protection Act 2010 — used only to run your sponsor account and your giving, never sold.

> ☐ **I understand the conduct expected of me, and I consent to myNADI handling my personal data under the PDPA 2010 to run my account.**

---

## §B — Comprehension quiz

Shown after the cards. **5 questions, all must be answered correctly.** A wrong answer re-shows the relevant disclosure
card and lets the sponsor try again (no lock-out — the goal is understanding, not a pass/fail exam). Answers + attempt
count are stored.

**Q1.** *(maps to A1/A2)* You donate RM3,000 and later change your mind before funding anyone. Can you get the RM3,000
back to your bank account?
- A. Yes, on request.
- B. Yes, within 14 days.
- **C. No — it stays as a giving balance to direct to a student. ✓**
- D. Only the unspent part.

**Q2.** *(maps to A3)* After you sponsor a student, what will you be able to learn about them?
- A. Their full name and school.
- B. Their name, once the award is accepted.
- **C. Nothing identifying — only an anonymous summary of their need. ✓**
- D. Their contact details, to stay in touch.

**Q3.** *(maps to A4)* A student you funded stops attending and makes no progress. What happens to the not-yet-released
part of the award?
- A. It is paid out anyway.
- B. It is refunded to your bank.
- **C. It can be withheld and returns to your giving balance. ✓**
- D. It is kept by myNADI as a fee.

**Q4.** *(maps to A1)* What are you receiving in return for your contribution?
- A. Interest on the amount.
- B. A stake in the student's future earnings.
- **C. Nothing financial — it is a charitable donation. ✓**
- D. A guaranteed graduate.

**Q5.** *(maps to A5/A7)* Which of these are you allowed to do?
- A. Ask myNADI for the student's phone number.
- B. Choose the student's course for them.
- C. Visit the student's school.
- **D. None of the above — you fund a need and stay anonymous. ✓**

---

## §C — Donor agreement (e-signed)

> Shown in full on the final step; the sponsor types their **full name** to sign. Stored with the typed name, the
> agreement version, a timestamp, the locale, and the request IP — the same audit pattern as the student consent record.

**myNADI Sponsor Donation Agreement** *(working draft v2026-draft-1)*

By signing below, I confirm that:

1. **My contribution is a voluntary, irrevocable donation** to myNADI (under Tamil Foundation), made for charitable
   purposes. It is not an investment, loan, or purchase, and I expect no financial return.
2. **It is not refundable to me.** Once donated, the funds are held by myNADI as a directed-giving balance. I may direct
   that balance to support students within the programme; I may not withdraw it to a bank account. Amounts from a lapsed,
   declined, or withheld award return to my giving balance to be redirected, not refunded.
3. **Awards are released in stages tied to a student's progress**, at myNADI's reasonable discretion, and a stage may be
   withheld if a student does not progress — in which case the withheld amount returns to my giving balance.
4. **The programme is anonymous.** I will not receive, and will not seek, any information identifying a student I support,
   and I will keep all programme information confidential.
5. **I have no relationship with, or authority over, any student**, and myNADI manages all student contact, verification,
   and fund release.
6. **My personal data** will be processed by myNADI under the Personal Data Protection Act 2010 solely to operate my
   sponsor account and giving, and will not be sold.
7. **Eligibility:** I am at least 18 years old, the funds are my own and from lawful sources, and the details I have
   provided are true.
8. **No guarantee:** myNADI does not guarantee any student's academic outcome, and my donation's charitable purpose is
   fulfilled by its proper application to the programme, regardless of any individual student's result.

*Signed:* ______________________  *(typed full name)*  ·  *Date/time + version recorded automatically.*

---

## §D — Quick declarations (earlier wizard step)

A light, self-declared step **before** the disclosures — not identity verification, just clear statements (each a tick):

- ☐ I am **18 years old or over**.
- ☐ The funds I will donate are **my own** (or my organisation's) and come from **lawful sources**.
- ☐ I am sponsoring as: ◯ an **individual**  ◯ on behalf of an **organisation** *(name: __________)*.

*(Email is already confirmed via sign-up. We are deliberately **not** doing full identity/AML verification at launch —
money flows **into** a charity, which is lower-risk; the abuse backstop, if ever needed, is a later add.)*

---

## §E — Notes for the lawyer / open items

When the lawyer comes in near the end, these are the points to stress-test (wording **and** process):

1. **"Irrevocable donation, no bank refund"** — is the directed-giving-balance model expressed safely and fairly? Is the
   donation genuinely final at the point of donation, or only at the point of allocation? *(Current build: final at
   donation — see A1/A2.)*
2. **Withholding a tranche** — the grounds ("does not progress") need a fair, defined standard and a student-side process,
   not pure discretion. What is defensible?
3. **Tax receipts (A6)** — confirm myNADI/Tamil Foundation's actual status (e.g. LHDN approval) and the correct wording;
   today A6 is deliberately non-committal.
4. **Anonymity vs. duty of care** — is "you will never know who you helped" compatible with safeguarding and with any
   donor-reporting expectations?
5. **Foreign sponsors** — phone/identity is Malaysian-only today (TD-072a). Do overseas donors need different wording or
   are they out of scope at launch?
6. **The comprehension quiz as evidence** — does a stored, must-pass quiz + per-card acknowledgement strengthen the
   "informed donor" position the way we intend?
7. **PDPA (A7)** — confirm the sponsor privacy notice is complete (purpose, retention, rights, contact).

**Open product items (not legal):** real toyyibPay donation-in, disbursement-out + the tranche engine, the lapse cron,
and award/decline emails are all deferred (TD-075) — for the demo these are mocked or concept-only.
