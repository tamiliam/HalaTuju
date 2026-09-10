# Retrospective — a matriculation offer read a DATE as the student's jurusan

**Date:** 2026-09-10 · **Branch:** `fix/matric-offer-jurusan` ·
**Worktree:** `.worktrees/matric-offer` · **Deployable:** api only ·
**Migration:** none · **Env var:** none · **Data step:** ⚠ yes — a cockpit Re-run on 4 documents

---

## What prompted it

The owner, looking at application **#142**:

> *"Why does the pathway chip is red? And the institution not ticked? Investigate."*

Then, after the first answer, the correction that turned the whole investigation around:

> *"These are the two letters. Both were exact reads. What's inside the bracket was inserted
> deliberately. So, we have to ask: is there an error in the instruction given to the code?"*

**They were right and I was wrong.** My first explanation blamed Gemini for putting the reporting
date where the stream belongs. Gemini never read #142. **Our own parser did, and our own f-string
built the bracket.** The owner spotted it by reading the two letters side by side and seeing that
they are the identical KPM template, both printing `Jurusan: SAINS`, neither containing the string
we had stored.

## What was actually wrong

**The label→value pairing is positional and it shipped by one.** `_info_block_pairs` collects the
value lines beneath a block of labels and `zip`s them by INDEX. Nothing asks whether the value
landing in the "Jurusan" slot could possibly be a jurusan. On #142 the value belonging to "Tarikh
Kemasukan ke kolej" landed in the Jurusan slot:

| | #134 (works) | #142 (broken) |
|---|---|---|
| `programme` | `Program Matrikulasi (SAINS)` | `Program Matrikulasi (8 JUN 2026)` |
| `reporting_date` | `8 JUN 2026` | **empty** |

The same date. Right slot on one, the jurusan's slot on the other, and the reporting slot left
empty. **One shift, two wrong fields, no error raised anywhere.** Reproduced exactly in a test from
an interleaved layout — the three stored values come back identical.

**And a second, older fault underneath it.** The Gemini schema states plainly that `"stream"` is
*"the Form-Six Bidang OR the matriculation Jurusan"*. Our parser filed the Jurusan under
`programme` and returned **no `stream` key at all**. So one letter had two readers and two
different homes for one fact, and the pathway check's TRACK axis — built precisely for this
comparison — was empty for every matriculation letter the parser handled. Measured on production:
**26/26** Gemini-read matric letters carried a stream, **0/4** parser-read ones did.

## ⚠ The part that should sting: this bug was already fixed once

App **#125** was the polytechnic version of #142. Same `_info_block_pairs` zip, same shift, the
institution into the programme slot and a "Tarikh…" line into the institution slot. It was fixed by
`_guard_poly_slots`, whose docstring states the right rule in fully general terms:

> *"Anchor to SHAPE, never trust the positional pair blindly."*

…and which is then called from `_parse_poly` and nowhere else. Matriculation uses the same pairing
and got nothing. Six weeks later the identical fault came back through the other door.

`docs/lessons.md` has carried *"a guard written from the instance you just fixed is scoped to that
instance"* since 2026-09-08. It was read at this sprint's start. It did not prevent this — because
**the scoping was invisible**: the helper READS general, and only its call site is narrow.

## What shipped

1. **The guard moved to the shared exit.** A date or a bare ringgit amount in the `stream` /
   `institution` / `programme` slot now defers the whole letter to Gemini, for **all three**
   families, from `parse_govt_offer`'s single return path.
2. **The Jurusan is emitted as `stream`**, its proper home — **and kept inside `programme` too**,
   because five call sites derive the matric track from that string. Retiring the bracket is a
   separate, measurable change and was deliberately not done here.
3. `PARSER_VERSION` 1.2.0 → 1.3.0.

## What went well

- **The owner's correction was accepted on the evidence, not deflected.** Reading the two letters
  as the owner asked is what moved the cause from "the model was inconsistent" to "our instruction
  is wrong" — a different fix in a different file.
- **The blast radius was measured, not estimated.** All 68 live offer-derived records were replayed
  through the real functions. Five read mismatch; four are genuine (three real stream clashes, one
  real institution spelling difference); **#142 was the only spurious one.**
- **The replay found something the bug report could not:** the INSTITUTION axis matched on all 56
  pre-U records, so the programme axis had **never once decided anything**. It was pure risk
  carrying no signal.
- **Both bite-checks bit.** Disabling the shape guard turned the two deferral tests red; dropping
  the `stream` key turned four tests red.

## What to watch

- **⚠ FOUR DOCUMENTS STILL CARRY THE OLD READ** — #77, #101, #134 (stream missing, otherwise fine)
  and **#142** (the date in the jurusan slot). Code alone fixes nothing already stored. They need a
  cockpit **Re-run**, on the live service, never from a local checkout.
- **⚠ `_offer_parser_version` IS WRITTEN BUT NEVER READ.** Bumping it re-processes nothing. It is a
  forensic stamp — it is how the four records were identified — not a cache key. Do not assume a
  version bump triggers anything.
- **#77, #101 and #134 are passing on a coincidence.** Their bracket happens to hold the jurusan,
  which happens to match the declared track. The re-run replaces that luck with a real `stream`.
- **#142 is `awarded`.** Its verdict band is protected (`pathway_confirmed_at` set 2026-08-01), so
  the red chip never docked it — this was a display fault, not a decision fault. A re-run should
  return the ticks without moving the band. Watch that it does.
- **The pathway comparison still pits a TRACK against a PROGRAMME NAME** for pre-U records whose
  declaration came off the offer. Measured: dropping that axis changes exactly one record (#142,
  mismatch → match) and nothing else. **Logged, not built** — the parser fix removes the trigger;
  this would remove the mechanism.
