# Retrospective — the Documents page offers the IC that settles whose STR it is (TD-309)

**2026-09-30. API + web. Built by a subagent; NOT committed, pushed or deployed — the lead and an
adversarial reviewer own that.** Owner's pick: **option 1 — the slot is offered, the submission
gate is unchanged.** The owner reads the Tamil help line before the push.

## What Was Built

- **One rule, two readers.** `income_str_ownership.str_ic_slots(sc, application)` — pure, reads the
  `student_str_check` reading in hand — holds what `str_owner_ic_asks` used to compute. Check 2's
  ask (`str_owner_ic_asks`) is now a one-line wrapper over it; the Documents page's offer
  (`student_str_payload(doc)`, served as `str_check.ic_slots`) calls it too. The TD-262 F2 lesson,
  applied literally: the demand and the offer are the same function.
- **`serializers.py` held at its ceiling** (1215 → 1215): `get_str_check`'s two body lines swapped
  for two lines; docstring reworded within its three.
- **The wizard.** `incomeWizard.strIcSlotMembers(docs, answers)` — the latest STR's
  `missing ∪ unreadable`, in `MEMBER_ORDER`, minus anyone who already owns an IC card (STR earner /
  ticked member), plus anyone whose tagged IC is on file (an upload never vanishes once the STR is
  settled). `IncomeWizard.tsx` draws a tagged, not-required `parent_ic` card per member: inside the
  STR group box, or as its own block on the salary route. No completeness cue reads it.
- **A drift test** on the one thing the web copies from the api — "latest" is `uploaded_at`
  descending over live rows (`document_snapshot.SNAPSHOT_ORDER` / `latest_doc` / `_live`).

## What Went Well

- **Zero queries.** `student_str_payload` costs exactly what `student_str_check` costs, pinned by
  `TestNoExtraQuery` on four shapes; the extra-query bite reddens all four.
- **The offer and the ask cannot drift** — `test_the_ask_is_the_offer_on_every_shape` and
  `test_check2_raises_exactly_the_offered_members` read both through the real code.

## What Went Wrong

- **The card would have destroyed the IC it was meant to sit beside.** *Symptom:* an api test that
  POSTed the new card's exact body (`parent_ic`, `household_member: 'mother'`, STR route, before
  consent) stored it as **father**, superseding his IC. *Root cause:* the pre-consent STR force-tag
  (TD-115) re-tags every income upload to the earner, whatever the client sent — correct when the
  page only ever offered the earner's card, wrong the moment it offers anyone else's. The web test
  proved `recordDocument` got `mother` and could not see what the server did next. *Fix:* the
  force-tag applies only to a blank tag or the earner's own (`views.py`, +2 lines, a comment and one
  condition; a blank upload still lands on the earner, asserted). A lesson at the top of
  `docs/lessons.md`.
- **Five per-member help lines broke `/scholarship/apply`'s budget** (286 against 285), a route that
  never draws the wizard — it pays for en.json. *Root cause:* the route already sat ~0.45 kB above
  its line numerically and printed 285 by rounding; 128 gz bytes of copy tipped it. *Fix:* one
  member-neutral line (the card title already names the member) and three dead wizard keys deleted
  in all three languages. 285,578 → 285,405 bytes; every en.json route is 173 bytes lighter than the
  first build, and the catalogue is 31 gz bytes lighter than the untouched one.
- **My first comment said the ordering "mirrors" the server's** and the no-unguarded-mirror guard
  refused it. It was right: that IS a copied rule. The drift test was written rather than the word
  changed.

## Bite-checks (byte backup, one unique needle, restore in a `finally`, SHA-256 verified exact)

| Bite | Result |
|---|---|
| 1 `str_ic_slots` returns both lists empty | red — (a) `..._offers_her_ic_as_missing`, (b) `..._offered_as_unreadable`, (i) `test_the_students_documents_payload_carries_ic_slots` (+ subtests) |
| 2 `ic_read_members` no longer stripped | red — (f) `test_the_payload_is_the_str_check_minus_...`, (i) |
| 3 one extra `.exists()` query in `str_ic_slots` | red — (h) `test_the_payload_costs_the_same_queries_as_the_reading`, all four shapes |
| 4 the new card loses `member: m` | red — `an upload into it is TAGGED to the mother`, `her IC on file but unread is offered too` |
| 5 `strIcSlotMembers` stops excluding the earner | red — `the father's IC card is unchanged — one card, not two` + 4 more |
| 7 `SNAPSHOT_ORDER` changed in the api | red — the DRIFT test |
| 8 the force-tag fix reverted | red — `test_the_offered_card_uploads_under_her_name_without_touching_the_earners_ic` |
| 6 comment-only, both source modules | green |

## Numbers

- pytest **7,225 passed / 3 skipped** (lead's pre-sprint count per TD-306: 7,215; +10 new).
- jest **3,167 / 184 → 3,181 / 185** (+14).
- `/scholarship/apply` 285,405 gz bytes (line 285; numerically 0.4 kB above, prints 285);
  `/scholarship/application` 272,943 (line 275; 2.06 kB under); `/profile` 309,901 (line 310).

## Follow-up the same day: the margin back

- The lead asked for every route ≥ 0.5 kB under its line. `/scholarship/apply` 285,405 →
  **270,721** gz bytes: the Form 6 centre list now loads through `LazyStpmSchoolPicker.tsx` (~15 kB,
  needed only after an STPM stream is picked), and 30 dead message keys went (−326 gz bytes of
  en.json). `/scholarship/application` 272,655, `/profile` 309,391 (0.61 kB under 310), median 227.
- **The dead-key scan is conservative by construction** (script kept in the builder's scratchpad):
  a key is live if its full path is any literal, sits under any template head (`t(\`a.b.${x}\`)`,
  the `iq` wrapper), under a namespace literal, under a bracket-read subtree
  (`['scholarship']['apply']`), contains a template tail, or appears anywhere in the web tree's
  text. Its first version read backtick PAIRS and a stray backtick in a comment made it call 1,012
  keys dead; anchored patterns found 58. **Spot-check a scanner's first answer before deleting.**
- **What bit:** deleting all 58 emptied `login.*` and `outcomes.*` below the per-namespace floors in
  `namespaces-i18n.test.ts`. The floor was left alone and those 28 keys kept.
- **A ratchet suggestion is not always a safe value.** After the cut the tool said to lower the lines
  to the printed build (270 / 272), which would put both routes ABOVE their lines numerically —
  TD-306's failure shape. They were recorded at build + 2 kB (272 / 274), the slack the ratchet
  tolerates; both lower than before.

## The adversarial review, fixed (same day)

- **F1 (MEDIUM) — the STR line on a card it was no longer true for.** *Symptom:* a member kept
  only because her tagged IC is on file (her IC settled the STR; or a salary → STR switch) still
  read "a name we could not match". *Root cause:* one help line for two reasons a card exists.
  *Fix:* `strIcNamedMembers` — the server-named members — picks the line; the rest read
  `icHelp.<member>`. Tests: the on-file-only card, and the SAME card switching after the IC lands.
- **F2 — my views.py exemption was wider than the fix.** *Symptom:* a non-earner STR/slip/EPF
  also escaped the pre-consent force-tag, so a mother-tagged STR could become THE STR for the gate
  and Check 2 with no card for it. *Root cause:* I exempted "an explicit non-earner tag" when only
  the IC card needed it. *Fix:* `parent_ic` only; `test_only_an_ic_escapes_the_pre_consent_force_tag`.
- **F3 — no coach on an unreadable non-earner IC.** I had copied `suppressCoach` from the cluster
  cards, but no cluster coach ever covers a non-earner. Dropped; a render test pins the coach.
- **F5 — the web's "latest STR" silently depended on the GET being live-only.** Now pinned by an
  api test with a newer superseded STR.
- **F4 → TD-315, F6 → TD-316** (both pre-existing shapes, LOW).
- Bites: each fix reverted → its test red (F1: 2 tests, F2: 3 subtests, F3: 1, F5: 1), restores
  SHA-256 exact.

## What Is Still Open

- The 9 keys the scan kept only through its loosest rule (`dashboard.title`, `…subtitle`,
  `…quizTitle`, `…quizDesc`, `…quizDone`, `…reportTitle`, `…reportDesc`, `outcomes.title`,
  `outcomes.trackApplicationsDesc`) are probably dead too; not deleted.
- `LazyStpmSchoolPicker.tsx` is not in `theme.test.ts`'s F2a list (its classes are the sibling's).
- **A tagged IC whose STR is later deleted is hidden again** (no STR → no card), as it was before
  TD-309. Owner-visible edge; not changed.
- Option 2 (hold submission until the IC lands) is now buildable and not built.
