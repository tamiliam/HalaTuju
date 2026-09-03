# Sabah S1 — the payment run says which gift

**2026-09-02. web only. No migration.** Branch `feat/sabah-s1-payment-run-programme`.
jest 1618 → **1623**; tsc **24** (baseline); lint **0**; i18n 4644 → **4648 × 3**; build clean.
Two guards bite-checked.

---

## What this actually was

Not a Sabah feature. **A latent regression in the live payout path**, armed and waiting for the
next programme row.

P2b (2026-07-26) made a payment run pay ONE gift and did it properly: `create_run(org, programme,
…)` takes the programme **positionally and required**, and the endpoint refuses with
`programme_required` when the organisation runs more than one — *"never a silent pick"*, as its own
docstring says.

The front end never sent one, and **did not know that error code**. So:

> The day a second active `Programme` row exists, BrightPath's own monthly run stops working from
> the screen, with an unexplained failure on a money form.

P2b's retro recorded that "nothing visible changed for BrightPath". True, and it was true of the
API. Nobody asked the same question of the screen.

**▶ THE API AND ITS SCREEN ARE TWO SURFACES, AND "NOTHING CHANGES TODAY" HAS TO BE ASKED OF BOTH.**
A backend that correctly refuses ambiguity leaves a front end that cannot express the answer. The
refusal is right; the screen was simply behind it, and the gap is invisible until the condition the
refusal was written for actually occurs.

---

## What shipped

- **A picker, only when there is something to pick.** One gift → no control, nothing sent, byte
  identical to today. Two → the operator states which, with **nothing preselected**.
- **`createPaymentRun` takes `programme_id` REQUIRED positionally, NULLABLE in value.** Required so
  no call site can sneak past the new dimension (P2a's lesson). Nullable because absence here
  cannot produce a wrong answer — the server resolves a single gift or **400s** (PF-1's own
  precedent for making `programme_code` optional).
- **`programme_required` has real words** in en/ms/ta. Still reachable with the picker shipped: a
  programme created after the page loaded is not in the list.
- **The options are filtered to the admin's OWN organisation**, because the endpoint reads
  `org = admin.owning_organisation` even for a super. Offering another tenant's gift would build a
  picker whose choices the server answers 404 to.

---

## ▶ THE FALLBACK HAD TO BE SAFE, NOT MERELY QUIET

The scope list is fetched best-effort, like the funding summary beside it. A failed fetch gives an
empty list → no picker → nothing sent → the server resolves the single gift, or refuses. **A failed
fetch can never cause a run to be paid from the wrong fund.** That is a property worth stating,
because "best-effort" usually means "degrades to something", and here it had to degrade to
*exactly today's behaviour* rather than to a guess. Pinned as its own test.

---

## Two things found while here, neither this sprint's

- **The dialog's date and month labels were never associated with their inputs** — a screen reader
  announced an unnamed date field on a money form. Four attributes, no visual change, fixed in
  passing because the picker needed a label anyway and leaving two of three unlabelled would have
  been worse than either state.
- **Every create failure renders twice** — one `error` state feeds both the page banner and the
  open dialog. Pre-existing for `past_date` and `too_early` too. **Pinned as-is rather than
  "fixed"**: asserting only one node would have hidden it.

---

## For S2

S1 was the precondition: a Sabah row may now be created without breaking the flagship's payouts,
**including an inactive one** — so the launch never depends on remembering a flag.

S2 is the Intake years screen (create the Programme + open its first year). **Stitch first.**
