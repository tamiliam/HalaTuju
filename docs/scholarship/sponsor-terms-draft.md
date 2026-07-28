# Sponsor terms — draft v1

**Status:** draft for owner review · **Intended version string:** `2026-sponsor-1` · **Drafted 2026-07-28**

This is the source of record for what a sponsor agrees to when they join. Sprint **T2** turns it into
editable, versioned database rows; **T3** puts it in front of a sponsor with a quiz. Until then, this
file is where the words are edited.

**Why it exists:** a sponsor today ticks one PDPA checkbox and agrees to nothing else. There is no
statement of what a gift is, what we do with it, or what we ask in return — so a suspension can cite
nothing (TD-191) and one shipped feature (AutoSponsor) was cleared against "the existing donation
terms" that do not exist. See `docs/technical-debt.md` TD-186 / TD-191 / TD-192.

**No lawyer pass** (owner decision, 2026-07-28). These are our own words, written to be honest and
readable rather than to be defensive. Worth a professional review eventually; nothing blocks on it.

---

## How to edit this

- **English is authoritative.** Malay and Tamil are courtesy translations of it.
- **Keep it short and second-person.** The whole point is that it gets read. Thirteen sections is
  already at the limit of what someone will read before clicking.
- **★ marks a quiz checkpoint.** Six of the thirteen. If you add or remove a ★, the quiz changes
  length — six feels right; ten would feel like an exam.
- **Some sentences are load-bearing.** They are flagged ⚠ below with the reason. Change the wording
  freely; changing the *meaning* has consequences noted against each.
- **No merge tokens.** The counterparty is named in prose, so "BrightPath Programme" becomes "the
  Foundation" by publishing a new version — no templating to build or maintain.

---

## The terms

### Joining BrightPath as a sponsor

*Thank you for wanting to help. This page explains how it works and what we ask of you. It is short
on purpose.*

---

**1. Your gift is a gift ★**

What you give is a donation, not a loan or an investment. Nothing is repaid to you — not the money,
not interest, not a share of anything. A student owes you nothing.

---

**2. You give to the programme, not to a student**

Your donation goes to the BrightPath Programme, which administers the funds. We record it as credit
in your account, which you then use to nominate a student. Money never passes directly from you to a
student.

---

**3. You choose, and we make the award ★**

You nominate a student from those we have already vetted. We follow your choice wherever we can.
Sometimes we cannot — a student withdraws, their university place falls through, or an award would
breach our own rules — and then we will tell you, and your credit returns to your balance for another
student. The final decision on every award rests with us. This is what keeps your gift a gift.

If you turn on **AutoSponsor**, you are asking us to make these nominations for you, using the
preferences you set. We will only ever do so while your balance covers it, and the student still
accepts it themselves. You can change it or switch it off whenever you like.

> ⚠ **The most load-bearing section in the document.** A donor *recommends*; the charity *retains
> final authority*. That is what makes the contribution a completed gift rather than the sponsor's
> money held on their behalf — and it is the only basis on which we may reallocate unused credit at
> all. If this becomes "you decide who gets it and we pass it on", we are a conduit holding someone
> else's money, which undermines charitable status later and makes §11 unenforceable.
> The AutoSponsor paragraph is what replaces the missing justification in
> `docs/retrospective-sponsor-redesign-r6.md`.

---

**4. The commitment is full and upfront ★**

When you nominate a student you commit their whole amount at once, not month by month. That is what
lets us promise a student their funding is secure for the year ahead, which is the single most useful
thing we can tell them.

---

**5. How the money reaches a student**

Monthly, through Vircle — an app that can only be spent on education. Never as cash. This is how we
keep a gift on the purpose it was given for.

---

**6. What we ask of a student**

Steady progress. We confirm each student is genuinely enrolled and we follow their results. If a
student stops progressing we may pause or stop payments, and anything unspent returns to your
balance.

---

**7. We will tell you how it was used**

You will see your students' progress and how the funds were spent. Enrolment is verified
independently, and the programme's money is audited annually.

> ⚠ Written in the future-facing present because parts of it are not built yet — the Trust &
> Transparency page already says several sections are placeholders "while the organisation is being
> formalised". Do not let this section promise a report that does not exist by the time v1 publishes.

---

**8. You will not know who they are, and that is deliberate ★**

You see an anonymous profile — field of study, region, academic band. Never a name, IC, address,
photograph, or contact details. Please do not try to identify or contact a student. If a student wants
to write to you, we will pass it on. This protects a young person who had no choice about needing
help.

> ⚠ This is the section a suspension is most likely to cite, so the duty must be stated as a duty
> ("please do not") and not merely as a description of the product.

---

**9. Please do not use a student for publicity**

You are very welcome to say that you support the programme. Please do not name, picture or identify a
student you have funded, in anything public.

---

**10. Your money must be clean ★**

We ask you to confirm that what you give is your own and lawfully obtained. We may ask you to
identify yourself or to explain where funds came from, and we may decline or return a donation. This
protects the programme and every other sponsor in it.

> ⚠ This is the hook **TD-192** hangs identity verification on. It states the obligation; it does not
> yet collect anything. Keep "we may ask you to identify yourself" even before TD-192 ships, so the
> first request is not a surprise.

---

**11. Refunds, and credit you do not use ★**

Once given, a donation cannot be refunded — that is what makes it a completed gift. We will of course
put right a genuine error. Credit that sits unused for two years is reallocated by us to other
students in the programme rather than left idle.

> ⚠ The two-year window comes from TD-075(f). The refund carve-out is deliberately narrow — "a
> genuine error" means we sent the wrong amount, not that someone changed their mind.

---

**12. Your own information, and tax**

We hold your name, contact details and giving history to administer your account, as set out in our
privacy notice. You can ask to see, correct or delete it. Separately, and we want to be
straightforward about this: **we are not yet an approved institution for tax deduction, so we cannot
issue a tax-deductible receipt.** We will tell you if that changes.

> ⚠ The tax sentence is not optional politeness. There is no LHDN s44(6) approval, and
> `sponsor_comms.BANNED_PHRASES` already refuses any email that implies otherwise. The document and
> the email guard must not disagree.
> The privacy-notice reference only works once `/privacy` actually describes sponsor data — it
> currently describes students only. That fix is part of T1.

---

**13. Ending, changes, and getting in touch**

You may close your account at any time; gifts already made stand. We may suspend or close an account
if these terms are broken, if we cannot verify where funds came from, or if someone tries to identify
or contact a student. When these terms change materially we will ask you to read and accept the new
version. Questions or complaints: [contact].

> ⚠ The three suspension grounds are the whole reason TD-191 exists. They map to §8/§9 (identify or
> contact), §10 (unverifiable funds), and the terms generally. **Once v1 publishes, S4's mandatory
> reject/suspend reason can finally cite one of these** — and the `suspended` email can safely gain
> its `{reason}` token, which it deliberately ships without today.

---

## Quiz checkpoints

Six, one per ★ section. Written in T2 against `SponsorTermsSection.quiz_{en,ms,ta}`, shape
`{tag, plain, question, options[3], correct, why}` — the same payload the student bursary quiz uses.

| § | Tag | What it must establish |
|---|---|---|
| 1 | Your gift | Nothing is repaid — it is not a loan |
| 3 | Who decides | You nominate; we make the award and may redirect |
| 4 | The commitment | The whole amount at once, not monthly |
| 8 | Anonymity | You will not know them, and must not try to find out |
| 10 | Clean funds | We may ask where the money came from |
| 11 | Unused credit | No refunds; unused credit is reallocated after two years |

**A wrong answer is never penalised** — it explains itself and lets them try again, unlimited times.
Acceptance is gated on getting all six right (owner, 2026-07-28).

---

## What this document deliberately does NOT do

- **It does not collect anything.** No NRIC, no address, no identity document, no source-of-funds
  evidence. That is TD-192, its own roadmap. §10 states the obligation so TD-192 has something to
  enforce.
- **It does not name a legal entity.** There isn't one — "BrightPath Programme" is a programme, not a
  company. When the Foundation exists, that is a new version, not a code change.
- **It does not describe the student's agreement.** The 94-clause bursary agreement is between
  BrightPath and a student, and a sponsor is not a party to it. Do not merge the two.
