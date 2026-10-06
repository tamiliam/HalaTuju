# Retrospective — BrightPath #23: a birth certificate that nobody checked

**Date:** 2026-09-08 · **Branch:** `feat/bc-verdict` (worktree `.worktrees/bc-verdict`, base
`origin/main` at `8b9d19f4`, merged forward to `c145b677` at close) · **Migration:** none ·
**Request:** #23, classified **bug / sprint**, planned **9.0h**, **no charge**.

Analysis **52** approved and posted as comment **77**; completion analysis **53** approved and posted
as comment **78**; request closed `done`.

---

## What Was Built

The owner sent two certificates and one sentence: a certificate could be accepted without anyone
really checking it. Three faults sat behind that, and the investigation found a fourth.

**Step 1 — read the child's IC, and make the date of birth vouch for it.** The number is printed
top-right beside the barcode and its first six digits are the date of birth. 21 of 62 certificates
carried a child's name with no number beside it. `vision.nric_dob_agrees` is the guard, and it is
load-bearing rather than belt-and-braces: `bc_child_nric` feeds `_nric_bucket` against the student's
own NRIC, so a misread number is a CONFIDENT mismatch where a blank was nothing.

**Step 2 — unreadable is not clean.** Every row of an unreadable certificate buckets to `no_ref`,
which reads as "nothing disagrees". `income_engine.relationship_doc_unreadable` makes it a
DOCUMENT-level state with its own code and its own words, distinct from wrong-type.

**Step 3 — the owner's merged rule, and the father row stops blocking.** One cell alone is amber,
not green. A red father row holds neither gate.

**Step 4 — proving income no longer settles parentage.** `birth_certificate` and
`guardianship_letter` came out of `services._INCOME_CLUSTER_DOC_TYPES`.

**Step 5 — an explanation-letter document type — was DEFERRED by the owner**, to try the existing
QC override first. That is the right order round: if the override does the job, the document type is
a page nobody needs.

---

## What Went Well

**Every behaviour change was measured on production before it shipped, and each measurement changed
something.** Step 3's blast radius came back as *one live application*, not the 21 the raw count
suggested — 20 of the 21 belong to decided students. Step 4's came back as *one, and it is the test
account*. Neither number was guessable; both were the reason the owner could rule in a sentence.

**Step 4 was put to the owner BEFORE the first line changed, exactly as comment 77 promised.** It
is the only change in the request that could newly stop somebody submitting. The promise was
"SEVEN live applications, named for you first" and that is what was delivered.

**The two open questions were closed with their numbers attached**, not left to drift: the father
row (51 of 62 would go amber, only 11 hold a father's IC) and Lina's own file (verified that nothing
about it blocks her, rather than assumed).

**Guards behaved as guards.** `test_no_new_unverifiable_dynamic_call_site` caught four computed
verdict codes and its own message named both remedies; the code changed, not the guard.

**Five bite-checks landed across four steps.** Step 4's was the cleanest signal in the sprint:
putting the two document types back failed exactly the two tests written for them and nothing else.
Not one pre-existing test broke when the relationship check was switched back on — which is itself
the finding, because it means nothing had ever asserted the check was skipped.

---

## What Went Wrong

**1. A customer-facing analysis stated a cause I had only half established.**
*Symptom:* comment 77 says the 23 blank child ICs exist "because we told the reader not to look".
Mid-step-1 it turned out `bc_parse` — the geometry reader that actually runs first — had been
reading that number from a position bracket all along; only the Gemini fallback carried the "leave
it empty" instruction.
*Root cause:* two code paths produce `bc_child_nric` and I read one of them, then generalised its
instruction into a cause. The prompt was the file I had opened; the reader that runs was not.
*System change:* the lesson is logged — **when a field has more than one producer, establish which
one RUNS before writing its cause into anything a customer reads.** The owner declined a correction
("you don't have to post correction"), so the completion report was written to avoid restating it
rather than to argue with it.

**2. A bite-check broke syntax and therefore proved nothing.**
*Symptom:* replacing `os.environ.get(...)` with a `# BITE` comment swallowed the rest of the line;
all five tests failed.
*Root cause:* treating "the suite went red" as the signal, when the signal is "the RIGHT tests went
red". A file that will not parse fails everything.
*System change:* a bite must leave the file parseable, and **if every test fails, you broke the
module, not the behaviour.** Re-done with `None` in place of the call, giving exactly one failure.

**3. The live cohort moved underneath the measurement.**
*Symptom:* applications 43 and 124 read `recommended` in one query and `awarded` in another taken
minutes later — the owner was funding students while I counted.
*Root cause:* I treated a production read as a snapshot. It is a reading at a time.
*System change:* the brief and the CHANGELOG both record the read time and say the table must not be
carried forward as static. Logged as a lesson.

**4. The report-staging tool cannot run from a worktree, and stamped the wrong commit.**
*Symptom:* `record_request_analysis` reads the gitignored `.env` from the repo root; a worktree has
none, so it had to run from the main checkout — and `_repo_sha()` then recorded main's HEAD
(`04aca637`) as the commit the analysis was read against, when the work is on `feat/bc-verdict`.
*Root cause:* the credential location and the SHA source are the same path, and every sprint is
worked in a worktree.
*System change:* **TD-236** logged, with the fix (resolve `.env` via `git rev-parse
--git-common-dir`, take the SHA from the current tree) and its trigger (the next report staged from
a worktree — i.e. the next one).

**5. The shared checkout's `node_modules` lost `@jest` mid-session.**
*Symptom:* `npx jest` reported "not recognized"; 561 directories where there had been 574, static
across two checks, no npm process running.
*Root cause:* not this sprint's change — a shared checkout worked by more than one agent.
*System change:* recorded in the step-3 CHANGELOG entry so the next person recognises it in seconds
rather than suspecting the branch. Repaired from the committed lockfile; the one-line lockfile churn
was reverted.

---

## Design Decisions

Logged in `docs/decisions.md`:

1. **The relationship documents leave the income cluster** — and why the softening they leave behind
   is not weakened by it.
2. **The father row keeps its one-cell green** — a decision with its numbers, not an oversight.

Two more are recorded in code comments at the lines that carry them, because they are local: the two
BC readers are guarded DIFFERENTLY on purpose (`bc_parse` has a position bracket, the Gemini fallback
does not), and `_usable_relationship_fields` returns a REASON string rather than a boolean because
wrong-type and unreadable owe the student different words.

---

## Numbers

| Gate | Result |
|---|---|
| pytest (merged tree, all apps) | **6027** |
| jest | **1852** / 116 suites |
| tsc | **24** (baseline, TD-221) |
| next lint | **0** errors |
| i18n parity | **4894 × 3** (ms/ta first drafts on the two new codes) |
| `next build` | exit 0 |
| `makemigrations --check` | clean |
| migration ledger vs production | scholarship **151/151**, courses **74/74**, no gaps |
| bite-checks | **5**, each injection verified as landed |

**Effort:** about **3.0h** against **9.0h** planned, four of five steps delivered (step 5 deferred by
the owner). The four fixes shared one seam rather than needing four. No charge — it is a defect.

**Blast radius, measured not estimated:** step 3 moves one live application to amber; step 4 newly
stops one, and it is the owner's test account. **Zero real students are affected by either.**

---

## Still Outstanding

- **NOT DEPLOYED.** Push rebuilds both services. No migration, no env var to keep.
- **At deploy, the re-read must run**: set `REEXTRACT_DOC_TYPE=birth_certificate` and
  `REEXTRACT_PASS=reextract_bc_child_ic` on the api service, run the `reextract-documents` cron job
  until it reports nothing left, then **UNSET both**. Until it runs, some certificates read amber
  where they will settle green afterwards.
- **ms and ta are first drafts** for `birth_cert_unreadable`, `guardianship_letter_unreadable` and
  the `unreadable` fact label.
- **Step 5 is the owner's**: try the QC override on a family whose certificate cannot be corrected,
  and only then decide whether the explanation-letter document type is worth building.
