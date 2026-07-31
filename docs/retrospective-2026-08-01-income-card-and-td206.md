# Retrospective — request #4's income card, and TD-206 (2026-08-01)

## What Was Built

**One real student's card, and the seam behind it.** Application #106 sat `shortlisted` with a red
income card beside green document chips. Both were right about different questions: the chips judged
the documents on file (the father's IC and payslip — readable, and his), the summary judged the
declared route (STR ticked, no STR letter ever uploaded). The household was banded on what it *said*
rather than what it *supplied*.

`str-proof-spec.md` §6 rule 2 has listed the fall-through trigger as *"`rejected` / `wrong_type` /
**absent**"* since it was written. Only the first two were implemented. An absent STR filed
`income_proof_missing` as a hard gap and returned red several branches before reaching the
fall-through it was entitled to. Fixed by delegating to `_verdict_income_salary`, gated on
`salary_income_satisfied` — the same predicate the submission gate uses.

**TD-206, on its trigger.** Staging an analysis required live `DB_*` on a laptop. The super-only
endpoint already existed (TD-204), so only the transport was wrong: no deploy, no migration.

**The engineer closed the thread.** Request #4 went `scheduled → done` with an approved engineer
comment carrying both figures — estimated 4.0h, actual 1.3h — at the owner's instruction: *"While
the bug is free, effort is not. So it is best to post the estimated hours and the actual hours; so
both sides know the amount of work that is being done."*

## What Went Well

- **The spec was the authority, and reading it changed the work.** This looked like "add a
  fall-through". It was really "finish one that was specified and half-built". That reframing is
  what made the change small, and it is why the CHANGELOG can say the code now matches the spec
  rather than that the spec was amended to fit the code.
- **The gate came from counting, not from taste.** An ungated fall-through moves all ten no-STR
  applications; nine of them have nothing to fall through to and would silently stop being asked
  for the STR they still owe. Gating on the *submission gate's own predicate* keeps the blast radius
  at one AND removes the possibility of the two surfaces diverging again — the same predicate
  cannot disagree with itself.
- **Blast radius measured before AND after, on production.** 59 STR-route → 10 with no letter → 1
  with evidence to reach. Afterwards, live: #106 `verified`, and four controls still `gap` with
  `income_proof_missing` intact. The prediction and the observation were made separately and matched.
- **The suspect-payslip question was answered by the rule, not by nerves.** #106's only income
  document is an informal payslip scored `suspect`. It still greens — because
  `_income_genuineness_docs` caps only the documents a route REQUIRES and the salary route has no
  fingerprint cap. A salary-route household with that identical payslip greens today, so evenness
  demands the same colour. Both halves are now pinned by tests, so the salary-track redesign cannot
  fix one route and forget the other.
- **Bite-checks earned their keep four times.** Removing the completeness gate fails exactly the
  three negative controls; `any_route=False` fails four; letting the transport skip the citation
  guard fails the ordering test; dropping the refresh-token rotation fails the rotation test.

## What Went Wrong

**1. The command answered failures with a guessed cause instead of the one it was handed. Twice.**
- *Symptom:* `--bootstrap-login` reported *"Supabase refused the password grant (400). Check the
  email and password"* — so the owner checked a password. Then a minted token was refused with
  *"tokens expire after about an hour — get a fresh one"*, so the instinct was to fetch another.
- *Root cause:* both messages were written from the failure I **expected** at that line, and both
  discarded the response body that said otherwise. The account is **Google-only**
  (`encrypted_password` is null), so no password grant could ever succeed. The token was valid and
  unexpired; the API had said `Admin access required`, because it belonged to an **anonymous**
  session — my browser snippet took the first storage entry matching `auth-token` and the app keeps
  several. A second token would have had the identical problem.
- *Why it matters more than a bad error string:* a vague message makes someone investigate. A
  confident wrong one makes them act — and both of mine pointed at work that could not possibly
  succeed. This cost several exchanges of the owner's time on a non-technical task.
- *System change:* every refusal now repeats the server's own words before adding any hint, with a
  test each (`test_supabases_OWN_reason_survives_the_trip`,
  `test_a_403_repeats_what_the_API_said_and_does_NOT_blame_expiry`). The transferable habit:
  **when you write an error message for a call you did not make, print the response and add the
  guess second — never instead.**

**2. I designed a credential flow without checking how the account signs in.**
- *Symptom:* the whole `--bootstrap-login` password path, built and tested, was unusable for the one
  account it existed to serve.
- *Root cause:* I reasoned "admins were invited by email, therefore they have passwords" from the
  Supabase-SMTP memory note, and never asked the database. One query on `auth.users` +
  `auth.identities` — the query I eventually ran to diagnose it — would have shown `google` and no
  password before a line was written.
- *System change:* recorded in lessons. **An authentication method is a fact in a table, not an
  inference from how the account was created.**

**3. The browser snippet picked the wrong session, and I asked a non-technical owner to run it.**
- *Symptom:* the stored token authenticated as an anonymous user; the owner did the console dance
  twice.
- *Root cause:* `Object.keys(localStorage).find(k => k.includes('auth-token'))` returns the FIRST
  match, and the app keeps more than one such entry. I wrote a "find the token" heuristic where the
  requirement was "find MY token" — and no part of it verified whose it was.
- *System change:* the corrected snippet scans every entry, takes only the session carrying a user
  email, and **reports that email back** so the owner can confirm it before saving. Habit:
  **a selector that cannot fail loudly must at least report what it selected.**

**4. `getpass` in a management command is unreachable for an agent.** Not a defect, but worth
recording: any interactive prompt is a step only the owner can perform, so an agent-facing command
needs a non-interactive path for every credential it wants. That is what `--bootstrap-file` became.

## Design Decisions

Logged in `docs/decisions.md`: the absent-STR fall-through gated on the submission gate's own
predicate; the uncapped green and why evenness requires it; the refresh token as a deliberate,
smaller concession than a database password; and hours in the prose rather than in the org payload.

## Numbers

| | |
|---|---|
| pytest | **5287** (+29) |
| Files touched | 6 |
| Migration | none |
| Deploys | **1** (the engine fix; TD-206 needed none) |
| Guards bite-checked | **4**, each confirmed to fail then restored |
| Live verification | #106 `verified`; #22 / #44 / #52 / #140 still `gap` with `income_proof_missing` |
| Requests closed | **#4** — `done`, with an approved engineer comment carrying 4.0h estimated / 1.3h actual |

---

# Addendum — TD-205, the same day

## What Was Built

The badge that says a request is waiting on us. Requests **#5–#8** now appear on the Requests row and
in the bell; the query also counts a triaged FEATURE with no approved analysis, which cannot be
quoted at all and was therefore stuck invisibly.

## What Went Wrong

**5. The feature was 90% built and nobody had noticed it was 0% delivered.**
- *Symptom:* TD-205 was written as "extend the queryset". The queryset was already right for super.
- *Root cause:* `useNavProbes` **called the count endpoint and discarded the number**, keeping only
  "did it answer?" as the dark-ship liveness probe. The endpoint was correct, tested, and firing on
  every page load; the value reached no pixel. A stale comment two files away claimed the
  Administration hub needed the COUNT for itself, which made the omission look deliberate — that
  page had stopped calling the endpoint entirely.
- *System change:* the lesson is the generalisation — *stored but never displayed* has an outer
  ring, **fetched but never displayed**, and it hides better because the network tab shows the call.
  Habit: for an endpoint whose purpose is a number, grep the FIELD name through the client and
  confirm something renders it.

**6. I bite-checked a claim in my own comment and the claim was false.**
- *Symptom:* I wrote that a filtered `Count` was necessary because `.exclude()` across a
  multi-valued relation would miscount. Substituting the `exclude` form to watch a test fail — it
  passed everything.
- *Root cause:* I promoted a real war story from an adjacent bug (multi-valued `annotate`s
  multiplying) into a rule about a different construct. Django compiles a single multi-condition
  `exclude()` into one `NOT EXISTS` on the same joined row; the trap belongs to *chained* excludes.
- *Why it matters:* a wrong comment passes every test run, forever, and the next reader inherits it
  as knowledge. This landed hours after entry #1 above, about confident wrong explanations.
- *System change:* **if a comment says "X, not Y, because Y would break" — make Y break before
  writing it.** The comment now states the truth and records that it was corrected.

## Numbers (TD-205)

| | |
|---|---|
| pytest | **5292** (+5) |
| jest | **1252** (+3) |
| `next lint` | 0 errors |
| i18n | 4361 × 3 |
| Migration | none |
| Guards bitten | 3 — discarding the count fails the badge test; dropping the widened clause fails 3; the third **disproved its own premise** |

## Carried

- **TD-205 is now the only deferred follow-up.** Nothing summons the engineer; requests **#5–#8**
  are still four untriaged bugs. ~2h.
- **`clarifications` is still populated on requests 2 and 3** from TD-201; nothing reads it.
- **Tamil first drafts** for the `admin.requests.owner.analysis*` block and `detail.author.engineer`.
- **The salary-track redesign owns the genuineness gap** (V5 known limitation #13) — salary evidence
  carries no fingerprint cap on either route. Pinned by tests on both sides.
