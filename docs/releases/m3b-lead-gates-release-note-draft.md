# Release-note draft — sprint M3b, the organisation admin's pages read keys; nobody gives a case to themselves (2026-11-14)

**DRAFT. Branch m3b, not pushed, not published. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-14, M3b). Brief: `docs/plans/2026-11-14-m3-lead-keys-brief.md`.

## What changes for people

- **One rule changes (owner E3): nobody can give a case to themselves.** This applies to supers too. An
  organisation admin who sits at the Reviewers table can still be given cases, by a super or by the other
  organisation admin. In the assign picker, your own name still shows but cannot be chosen. A case you already
  hold keeps you as its holder.
- **Until M3c, the web shows its general "could not assign" message** for this refusal (the server answers
  code `self_assign`). M3c adds the proper wording: "Give cases to reviewers and nudge them. Never to yourself."
- **Nothing else anybody can do changes.** The organisation admin's pages (Team, Settings, Programmes,
  Applications assign / decide / nudge / parent call, sponsor vetting, billing, Requests, contracts) now check
  the admin's stored keys instead of the label. Every organisation admin holds all of these keys (M3a), and
  none can be taken away until M3c, so every page answers as before.

## Migration

**None.** M3b relies on M3a's data step `0098` having run: an organisation admin's row must hold the full key
set. M3a and M3b go live together, in the same `live` publish, after M3a's migrate-first steps (see
`m3a-org-admin-keys-release-note-draft.md`). Do NOT publish M3b on a database where 0098 has not run.

Done: M3a went live at the 14 Nov 16:00 window and the owner ran 0098 (DATA block re-run after 100% traffic, 0 rows).
Checked 14 Nov after that (read-only): the 0098 POST-DEPLOY CHECK returns 0 rows over the 2 organisation admin rows,
and 0098 is in the ledger. Just before the M3b publish, run that check once more (read-only) and publish only on zero.
Why it matters (adversarial review): an organisation admin row whose stored list lacks the keys (for example only
`["review"]`) loses Settings, Programmes, assigning, Students, Requests edit, Contracts and its Overview under M3b. A
NULL row reads as the full set and is safe.

## Owner's phone check (after the publish)

1. As a super: open a ready case, try to assign it to yourself. It is refused, with the general assign error.
2. As a super: assign the same case to the organisation admin who is in Reviewers. It works.
3. As that organisation admin: open the assign picker. Your name is listed but greyed out / not choosable.
   The other organisation admin, if in Reviewers, is choosable.
4. As an organisation admin: open Settings, a gift's settings, Team, Requests, Billing and Contracts, and
   approve or nudge one case. All behave as before.
5. As an admin (view-only) or a reviewer: nothing new appears, and the same pages are still refused.
