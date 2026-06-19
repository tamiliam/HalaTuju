# Sponsor Portal — Redesign Proposal (prototype)

**View it:** run `python -m http.server 8090` in this folder → open <http://localhost:8090>
All student data is **fictional and anonymised**. Nothing here touches live data.

---

## The problem with today's portal
It's one long scroll that **leads with "Invite a friend"** and an empty "Your invitations" box — an
admin chore — while the things that actually matter (your impact, the students you support, their
progress) sit below the fold or vanish behind empty states. There's no sense of *what your giving has done*.

## The fix — borrow Linked Finance's spine, keep HalaTuju's soul
Linked Finance leads with **My Portfolio** (your numbers, a donut, recent activity) and keeps the
**Marketplace** and **My Details** as separate, deliberate tabs. We do the same — but the "return" here is
never financial. It's **impact, progress and gratitude**, told with dignity and strict anonymity.

### Three tabs (was: one flat page)
| Tab | Linked Finance analogue | What it leads with |
|-----|------------------------|--------------------|
| **My Giving** (home) | My Portfolio / Summary | Impact numbers → giving donut → recent activity → students you support → community |
| **Students** | Marketplace ("Live Business Loans") | Anonymised cards, filterable; detail → "Support this student" |
| **My Account** | My Details + AutoInvest | Profile + approval/trusted badges, notification cadence, **Standing gift**, thank-you messages, invites, giving statement |

---

## Innovative engagement ideas (in the prototype)
1. **Impact dashboard** — Total given · students supported · semesters completed · graduates. The numbers grow as your students progress, so there's always a reason to return.
2. **Giving donut** — committed / completed / available, framed as a *donation held by the charity* ("redirect", never "withdraw").
3. **Per-student journey** — a Matched → Onboarded → Sem 1 → … → Graduated tracker on each student you support. Dignified, coarse, anonymous (no grades).
4. **Recent activity feed** — "A student you support completed a semester", "Your offer was accepted" — the Linked Finance "throughout the day" freshness that pulls sponsors back.
5. **Standing gift (AutoSponsor)** — Linked Finance's AutoInvest, reimagined: let your balance auto-allocate to the next matching student. *Proposed — needs a small backend.*
6. **Anonymous thank-you wall** — graduation messages surfaced warmly, scanned + human-checked so they can never reveal who wrote them.
7. **Community belonging strip** — "You're 1 of 48 sponsors, together supporting 112 students this term."
8. **Annual giving statement** — a tidy PDF for their files (tax-deductible once Section 44(6) is confirmed).

## What honours the programme's spirit
- Every field shown is **allowlist-safe** (ref, state, field, academic band, institution [trusted only], funding need, award, progress) — **never** name / IC / address / photo / contact, student *or* parents.
- **No hero language** ("change a life"). Humble, matter-of-fact, British English: "You fund a need. The student earns the rest. You never meet."
- Giving is **irrevocable** — "redirect", not "refund". Progress is a **coarse band**, never a report card. **No sponsor↔student channel.**

## Backed by what exists vs new build
- **Already have endpoints for:** impact numbers (wallet), students-you-support (sponsorships), pool browse + detail + fund, thank-you relay, notification cadence, referrals. → Most of this is a **UX refit**, not new plumbing.
- **New (small) build:** Standing gift / AutoSponsor, the activity feed aggregation, community counters, PDF statement.

## Suggested next step
Tweak this prototype with me until it's right, then I'll fold it into the existing **Phase E/F sprint plan**
(it maps cleanly onto Sprint 1 landing, Sprint 2/7 sponsor profile + my-students, Sprint 4 notifications) and
build it **behind `SPONSOR_POOL_ENABLED`** — local-first, Stitch-checked, no blind deploys.
