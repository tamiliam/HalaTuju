# Retrospective — Gopal + Cockpit Polish Sprint (2026-06-06)

Live-testing follow-up sprint after TD-085. Five shipped changes across the officer cockpit
and the student-facing Cikgu Gopal coach. No migration in the whole sprint.

## What Was Built

1. **Utility-bill facts in the officer cockpit** (`d7e34eb`) — a water/electricity bill row now
   shows **Current** (billing period within ~3 months of the review date), **Reasonable**
   (combined water+electricity per-capita vs RM25/RM40 — water alone greys out with a "water
   only" note, never a faked verdict; high consumption stays amber, never red), and
   **Outstanding** (green only when arrears exceed the current charge), plus an **orange note**
   when the account is in a name that's neither the student nor any uploaded parent IC. All soft.
   Backend `income_engine.utility_check` (+ `utility_reasonable`, billing-period parser);
   `officerCockpit.documentFacts`; i18n `docsDrawer.fact.reasonable/outstanding` + `utilityNote.*`.

2. **Verification verdict panel — green facts collapse to a tick** (`093a4ae`) — a verified
   fact now renders as `● FACT ✓` with no description, and its evidence block is hidden (green =
   done, the receipts are noise). Amber/red keep the lead line + the full detail block, where the
   ✓ evidence + the • gap *is* the story. Officer cockpit page only.

3. **Gopal — distinct "IC number misread" message** (`72377d1`) — on the student's own IC, a
   name-match + IC-number-mismatch is its own verdict (`ic_nric_misread`): "name matched, the
   number's likely a glare misread — re-upload cleanly." When the name *also* fails (wrong card),
   keeps the generic `nric_mismatch`. New verdict + guidance + fix-hint + FE `HELP_VERDICTS` +
   fallback copy (en/ms/ta).

4. **Gopal — diagnose-then-advise tone, system-wide** (`6d40af2`) — the prompt now mandates
   diagnosis first, action second, stop; bans cheerleading openers/sign-offs (at most one
   reassurance, only when informational). All 19 fallback strings (en/ms/ta) rewritten.

5. **One Gopal per income earner** (`4fb5255`) — income is the one *cluster* fact, so the coach
   now speaks once per earner, pinned to the foot of the cluster (after the relationship-proof
   card: father→IC, mother→BC, guardian→letter; per ticked member on the salary route), aware of
   the whole cluster and firing even before the IC arrives. STR-currency + "add the IC" nudges
   folded into the one voice (precedence: relationship → unreadable → STR stale → person-mismatch
   → missing IC). Backend `income_cluster_advice` rewrite + new `IncomeClusterHelpView`; FE shared
   `CoachCard` shell + `IncomeClusterCoach` + `clusterDocsFor`/cluster cache; per-file coaches
   suppressed for cluster docs.

## What Went Well

- **The cluster "brain" already existed.** `income_cluster_advice` was already a per-earner
  verdict; the income-coach change was mostly *placement* (re-anchoring) + folding two stray
  nudges in — not new intelligence. Recognising that kept the change to ~one endpoint + a small FE
  component instead of a rewrite.
- **Designing in conversation before coding.** Each change was confirmed with the user
  (calibration questions for the verdict-panel tick and the Gopal tone; a "what document?" fork for
  the IC-misread case) before a line was written — zero rework.
- **No migration all sprint** — pure logic + serializer/endpoint + FE.

## What Went Wrong

1. **Mis-placed a fix on the wrong document at first.** The user's IC-misread wording ("IC number
   doesn't match the one registered to your account") literally fits the *student's own IC*, but
   the screenshot was the *father's IC* (a cluster check that never compares the number to the
   account). **Root cause:** I started reasoning about copy before confirming which check the user
   meant. **Fix:** for any coach-copy change, first trace which matcher/verdict actually produces
   the message and confirm the target document with the user — don't write copy against an assumed
   check. (Captured as a lesson.)

2. **A heredoc broke on apostrophes** when rewriting the i18n fallbacks inline (`'Lulus'`, English
   contractions). **Root cause:** piping a large multi-line Python script with embedded quotes
   through a bash heredoc. **Fix:** for any non-trivial scripted edit with quotes/unicode, write the
   script to a temp file and run it (then delete), rather than a heredoc. (Already the standing
   lesson #—; reinforced.)

## Design Decisions

- **One coach per income cluster, anchored to the slot (not the document).** See decisions.md.
- **"Income too high" is NOT surfaced in the student coach.** It's not a document fix and cuts
  against never-block/don't-discourage; it stays at the officer verdict + interview. See decisions.md.
- **Utility "Reasonable" needs both bills; high consumption is amber, never red.** A soft proxy
  must not scream; water alone is too weak to judge. See decisions.md.

## Numbers

- **1775 backend pytest** (1037 courses/reports + 738 scholarship) + **262 jest**, 0 failures.
- `next build` clean; i18n parity **2020** × en/ms/ta.
- **No migration** (whole sprint). 5 code commits + this docs commit.
- Scholarship migrations unchanged on prod (through `0040`).
