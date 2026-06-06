# B40 Assistance Programme — Lawyer Review Bundle

> **Prepared for:** Vickneswari Veerasamy & Co, Advocates & Solicitors (Kajang).
> **Prepared by:** HalaTuju (tamiliam).
> **For: legal review.** **Status: working draft for the lawyer to vet — not yet legal advice, not yet live.**
> This document describes the sponsor (donor) programme in full so you can vet both **how it works** and **the exact
> words** people agree to, and harden them before we go live with real money and real students. *(What we are asking for
> is set out in §0.)*
>
> **The full system is not live yet.** Only a pilot of around 20 students is live, to gauge student response; there are
> no sponsors yet and none have been onboarded. A live system involving real money will be switched on only **after**
> your sign-off — that is the last step.
>
> Version: sponsor agreement `2026-draft-1`; student consent `2026-draft-3`.

---

## 0. What we are asking you to do

1. **Vet the words** a sponsor agrees to (the disclosures, the comprehension quiz, and the donor agreement — Appendix A)
   and the words a student / guardian agrees to (Appendix B).
2. **Stress-test the process** — does the design hold up legally and ethically: an irrevocable charitable donation, a
   non-refundable "giving balance", progress-tied release of funds, and **permanent anonymity** between donor and student
   (including minors).
3. **Flag what must change** before go-live, and tell us where we are exposed.

Our specific questions are in **§7**. The supporting detail is in **§1–§6** and the **Appendices**.

---

## 1. The programme in one page

**The B40 Assistance Programme** connects **sponsors** (donors) with **B40 students** (from the bottom-40% income band in
Malaysia) who need financial help to continue their education. A sponsor donates money to **Yayasan myNADI** ("myNADI");
myNADI matches that donation to a student's assessed need; the funds are released to support that student's studies.

Two promises sit at the heart of it:

- **It is a donation.** A sponsor gives money to the charity. They are not investing, lending, or buying; they get nothing
  financial back; and they **cannot withdraw it to their bank**. They can only **redirect it within the programme**.
- **It is permanently anonymous.** A sponsor **never** learns the identity of a student they help — not the name, photo,
  IC number, or contact details — even after a match. The student likewise never learns the sponsor's identity.

The programme is planned to be run by **myNADI**, a tax-exempt charity under Subsection 44(6) of the Income Tax Act 1967,
in partnership with other non-profit organisations such as CUMIG, SMC, EWRF and HYO. *(The operating entity is still
being finalised.)*

---

## 2. The parties

| Party | Who | Role |
|---|---|---|
| **Yayasan myNADI** | The charity (non-profit) | Receives donations, assesses student need, manages matching and the release of funds, holds all student data |
| **Sponsor** | An individual or organisation donor | Donates money; directs their giving balance to anonymous student needs |
| **Student** | A B40 applicant | Applies for assistance; consents to an **anonymised** version of their profile being shown to sponsors |
| **Parent / guardian** | For students under 18 | Gives consent on the minor's behalf |

There is **no direct legal relationship between a sponsor and a student.** The sponsor's relationship is with myNADI
(a donation); myNADI's relationship is with the student (assistance). This separation is deliberate and is the spine of
the anonymity model.

---

## 3. How the money works

This is the most legally sensitive part.

1. **Donation in.** A sponsor donates a sum to myNADI (in production, via a payment gateway — **to be determined**). At
   the moment of donation the money becomes **myNADI's**. It is **final** and **not refundable to the sponsor's bank
   account**.
2. **Giving balance (a ledger, not custody of the sponsor's money).** The donated sum credits the sponsor's internal
   **directed-giving balance**. This balance is simply *bookkeeping*: `balance = total donated − amounts currently
   committed to students`. The sponsor can **direct** this balance to students within the programme; they cannot take it
   out.
3. **Award amount.** For each student, a myNADI reviewer sets an **award amount** (the assessed need).
4. **Fund a student.** A sponsor with enough balance funds a student's award **in full** (1:1, full-or-nothing at launch;
   the design allows several sponsors to a single student later). This issues an **award offer**.
5. **Student accepts.** The student — or the **guardian**, for a minor — accepts the award within a deadline. On
   acceptance, the match becomes active and the student leaves the visible pool. If they do not accept in time, the offer
   **lapses** and the amount **returns to the sponsor's giving balance** (to redirect — never a bank refund).
6. **Release in stages ("tranches").** *(Designed, not yet built.)* The award is released to the student's institution in
   **stages tied to progress** — e.g. part on acceptance, the rest as the student progresses. A stage can be **withheld**
   if the student does not progress; a withheld amount returns to the giving balance.

**Key legal framing we have chosen:** by making the inbound payment a **final charitable donation** (myNADI's money) and
the "balance" purely an internal **directed-giving ledger**, we intend to avoid holding the *sponsor's* money on trust or
operating a refundable custody/escrow arrangement. **We need you to confirm this framing is sound** (see §7.1).

---

## 4. The anonymity model

Anonymity is **two-way and permanent**, and enforced in the software, not just by policy:

- **What a sponsor sees:** an **anonymised profile** of a student — a respectful, non-identifying summary of their
  situation, academic band, field of study, and funding need. It is **generated** from non-identifying inputs (never the
  raw application), and is checked by software before publication to ensure it contains no name, photograph, IC number,
  home address, phone, or email. The sponsor-facing data is an **allowlist** (only explicitly permitted, non-identifying fields can ever
  appear), so a future change cannot accidentally leak identity.
- **What a student sees:** nothing identifying about the sponsor. The student's view of their award has **no sponsor
  field at all**.
- **What myNADI sees:** both sides (it runs the programme and must).

The intent: a sponsor funds a **need**, not a **person**; there is no contact, no relationship, and no route to identify
the student.

---

## 5. The sponsor journey & onboarding (where the donor agrees to everything)

A sponsor self-registers and then completes a short **onboarding** that **auto-approves** them on completion (no manual
gatekeeping). The onboarding is deliberately built so the donor **demonstrates understanding** before they can give:

1. **Sign up** (email + password or Google) — email confirmed.
2. **Quick declarations** — 18+, lawful own funds, individual or organisation *(Appendix A §D)*.
3. **Understand the commitment** — seven disclosure cards, **each separately acknowledged** *(Appendix A §A)*.
4. **Comprehension quiz** — five plain-language questions they must answer correctly *(Appendix A §B)*.
5. **Donor agreement** — the full terms, **e-signed** with their typed full name *(Appendix A §C)*.
6. **Auto-approved** — they may now donate and fund students.

Every acknowledgement, quiz answer, and the signature are **stored with the version and a timestamp** as an audit trail
of informed consent. The full wording is in **Appendix A**.

---

## 6. The student / guardian side

A student (or, for a minor, their guardian) must **consent** before their anonymised profile is shown to sponsors, and
again when an award is **accepted**. The current wording is in **Appendix B**. Safeguards already built:

- **Minors (under 18):** consent is given by a **parent or guardian**, in the guardian's voice, with a structured
  **relationship** (father / mother / legal guardian / grandparent / sibling / relative).
- **Identity checks:** the guardian's IC is required and is cross-checked (by OCR) against the typed name/NRIC; a
  **non-parent** guardian must also upload a **guardianship letter** (a court order **or** the parent's written
  authorisation; **we want your view on whether this is sufficient** — §7.5).
- **Withdrawable:** the consent states it can be withdrawn at any time.

---

## 7. What we need from you (the questions)

**On the money (§3):**
1. **Is the "final donation + non-refundable directed-giving balance" framing sound** to avoid holding the sponsor's money
   on trust / operating a refundable custody arrangement? Is the donation properly final at the **point of donation**, or
   should it be final only at the **point of allocation** to a student?
2. **Tranche withholding** — withholding a stage because a student "does not progress" needs a **fair, defined standard**
   and a student-side process, not unfettered discretion. What is defensible, and what must we put in writing?

**On charitable / tax status:**
3. **Tax receipts** — myNADI is a Subsection 44(6) tax-exempt charity. Please confirm the correct, compliant donor-facing
   wording for tax-deductible receipts, and whether disclosure A6 (currently deliberately non-committal) can now be made
   specific.

**On anonymity & safeguarding:**
4. Is **permanent two-way anonymity** — *"you will never know who you helped"* — compatible with safeguarding obligations
   and with any donor-reporting or transparency expectations for a charity?

**On minors & consent (§6, Appendix B):**
5. Is a **parent's written authorisation OR a court order** a sufficient basis for a **non-parent guardian** to consent on
   a minor's behalf? Is the guardian consent wording (Appendix B) adequate and properly informed?

**On data protection:**
6. Are the **PDPA 2010** notices complete for both sponsors and students (purpose, retention, rights, contact, the
   anonymisation safeguard)? *(We do not yet have a stated retention period — flagged.)*

**On the donor's informed consent:**
7. Does our approach — **per-disclosure acknowledgement + a must-pass comprehension quiz + an e-signed agreement, all
   versioned and timestamped** — meaningfully strengthen the "informed donor" position, and is the donor agreement
   (Appendix A §C) complete and enforceable?

**On scope:**
8. **Foreign sponsors** — at launch the design assumes Malaysian donors (Malaysian phone/identity). Do overseas donors
   need different wording or terms, or should we exclude them at launch?

---

## 8. What is built vs. planned (so you know what is real)

| Built (mocked money) | Planned / not yet built |
|---|---|
| Sponsor sign-up + the account model | Real payment-gateway donation-in (gateway TBD; currently **mocked**) |
| The anonymised pool + anonymity safeguards | Disbursement-out to institutions |
| Donate → fund → award offer → accept → lapse (the state machine) | The **tranche** schedule + withholding mechanics |
| Student / guardian consent (incl. minors) | Award / decline notification emails |
| The onboarding flow + auto-approval *(in build)* | Multi-sponsor funding of one student |

The real-money and disbursement parts are deliberately **last**, and gated on your review.

---

# Appendix A — Sponsor onboarding content (the donor's words)

> The full disclosures, comprehension quiz, donor agreement, and quick declarations, exactly as the sponsor sees them.

## §A — The seven disclosure cards

Each card is shown on its own, with a single **"I understand"** checkbox; the sponsor cannot continue until it is ticked.
Each acknowledgement is stored with its card code, the agreement version, and a timestamp.

**A1 · This is a donation, not an investment.** When you put money in, it becomes a **donation to myNADI**. It is no
longer your money. You are **not** buying, lending, or investing — no return, no interest, no share of anything. You are
giving, generously, to help a student.
> ☐ I understand that my contribution is a donation, not an investment, and I expect nothing back in return.

**A2 · You cannot get the money back to your bank.** Because it is a donation, it **cannot be refunded to your bank
account** — not if you change your mind, and not if a student declines. What you *can* do is **redirect it within
myNADI**: the money sits in your **giving balance**, and you choose which student it helps. If a match falls through, the
amount returns to that balance for you to give to someone else. It never leaves myNADI back to you.
> ☐ I understand I cannot withdraw my donation to my bank; I can only direct it to students within the platform.

**A3 · You will never know who you helped.** To protect vulnerable students, the programme is **permanently anonymous**.
You will **never** see a student's name, photograph, IC number, home address, or contact details — not while choosing,
not after you fund them, not ever. You will see only a respectful, non-identifying summary of their situation and need.
> ☐ I understand I will never learn the identity of any student I sponsor, and I will not attempt to find out.

**A4 · The money is released in stages, tied to progress.** An award is not handed over in one lump. It is released to
the student's institution in **stages ("tranches")** — for example, part on acceptance and the rest as the student shows
genuine progress. If a student does not progress, a stage can be **withheld**, and that part returns to your giving
balance to help someone else. This protects your generosity and keeps it tied to real effort.
> ☐ I understand awards are paid in stages tied to the student's progress, and a stage may be withheld if they do not progress.

**A5 · You are funding a need, not choosing a person.** You are not "picking" a child or forming a personal relationship.
You are choosing a **need to meet**. You will have no say over the student's choices, no special access to them, and no
role in their life beyond your gift. myNADI manages the relationship, the checks, and the release of funds.
> ☐ I understand I am funding a need, not selecting or mentoring a particular individual, and I will have no relationship with them.

**A6 · This is a charitable gift.** Your donation is a **charitable contribution** to myNADI. Any tax treatment (such as a
receipt for relief, where available) depends on the foundation's status and the rules at the time, and will be confirmed
to you separately — it is **not** a reason for, or a condition of, your gift.
> ☐ I understand this is a charitable gift, and any tax receipt depends on the foundation's status and is confirmed separately.

**A7 · How you will conduct yourself, and how we handle your data.** You agree to act in the student's best interest: you
will **not** try to identify, contact, or influence them, and you will keep anything you see in the programme
confidential. In turn, myNADI handles **your** personal data under the Personal Data Protection Act 2010 — used only to
run your sponsor account and your giving, never sold.
> ☐ I understand the conduct expected of me, and I consent to myNADI handling my personal data under the PDPA 2010 to run my account.

## §B — Comprehension quiz (all five must be answered correctly; retry on a wrong answer)

**Q1.** You donate RM3,000 and later change your mind before funding anyone. Can you get the RM3,000 back to your bank?
A. Yes, on request · B. Yes, within 14 days · **C. No — it stays as a giving balance to direct to a student ✓** · D. Only the unspent part.

**Q2.** After you sponsor a student, what will you be able to learn about them?
A. Their full name and school · B. Their name, once accepted · C. Their contact details · **D. Nothing identifying — only an anonymous summary ✓**

**Q3.** A student you funded stops attending classes and makes no progress. What happens to the not-yet-released part of the award?
A. It is paid out anyway · B. It is refunded to your bank · **C. It can be withheld and returned to your giving balance ✓** · D. myNADI keeps it as a fee.

**Q4.** What are you receiving in return for your contribution?
A. Interest · **B. Nothing financial — it is a charitable donation ✓** · C. A stake in the student's future earnings · D. A guaranteed graduate.

**Q5.** Which of these are you allowed to do?
A. Ask for the student's phone number · B. Choose their course · C. Talk to their parents · **D. None of the above — you fund a need and stay anonymous ✓**

## §C — Donor agreement (e-signed with the sponsor's typed full name)

**myNADI Sponsor Donation Agreement** *(working draft v2026-draft-1)*

By signing, I confirm that:
1. **My contribution is a voluntary, irrevocable donation** to myNADI, made for charitable purposes. It is not an
   investment, loan, or purchase, and I expect no financial return.
2. **It is not refundable to me.** Once donated, the funds are held by myNADI as a directed-giving balance. I may direct
   that balance to support students within the programme; I may not withdraw it to a bank account. Amounts from a lapsed,
   declined, or withheld award return to my giving balance to be redirected, not refunded.
3. **Awards are released in stages tied to a student's progress**, at myNADI's reasonable discretion, and a stage may be
   withheld if a student does not progress — in which case the withheld amount returns to my giving balance.
4. **The programme is anonymous.** I will not receive, and will not seek, any information identifying a student I support,
   and I will keep all programme information confidential.
5. **I have no relationship with, or authority over, any student**, and myNADI manages all student contact, verification,
   and fund release.
6. **My personal data** will be processed by myNADI under the PDPA 2010 solely to operate my sponsor account and giving,
   and will not be sold.
7. **Eligibility:** I am at least 18 years old, the funds are my own and from lawful sources, and the details I have
   provided are true.
8. **No guarantee:** myNADI does not guarantee any student's academic outcome, and my donation's charitable purpose is
   fulfilled by its proper application to the programme, regardless of any individual student's result.

*Signed: ____________________ (typed full name) · date/time + version recorded automatically.*

## §D — Quick declarations (an earlier, lighter step — each a tick)

- ☐ I am **18 years old or over**.
- ☐ The funds I will donate are **my own** (or my organisation's) and come from **lawful sources**.
- ☐ I am sponsoring as: ◯ an **individual**  ◯ on behalf of an **organisation** *(name: __________)*.

*(Email is confirmed at sign-up. We are deliberately **not** doing full identity/AML verification at launch — money flows
**into** a charity, which is lower-risk.)*

---

# Appendix B — Student / guardian consent (the student's words)

**Consent to share an anonymised profile with sponsors** *(version 2026-draft-3)*

**Adult applicant (18+):**
> I, the named applicant (**{student_name}**, NRIC **{student_nric}**), consent to the **B40 Assistance Programme**
> sharing my profile and supporting information with potential sponsors for the purpose of considering me for financial
> assistance. I understand I can withdraw this consent at any time.
>
> ☐ I have read and agree to the above.

**Parent / guardian of a minor (under 18):**
> I confirm that I am the parent or guardian of **{student_name}** (NRIC: **{student_nric}**), who is under 18 years old.
>
> I give permission for the **B40 Assistance Programme** to share {his/her} profile and documents with sponsors. This is
> to help {him/her} get financial aid. I understand that I can cancel this permission at any time.
>
> ☐ As parent or guardian, I have read and agree to the above on the applicant's behalf.

The guardian additionally provides: their full name (as on IC), their NRIC, and their **relationship** to the applicant
(father / mother / legal guardian / grandparent / brother / sister / relative). A non-parent guardian must upload a
guardianship letter (court order or the parent's written authorisation).

*A second consent — **consent to the sponsorship itself** — is recorded when an award is accepted (again, by the guardian
for a minor). Wording to be finalised with you.*
