# Retrospective — four invitation emails, one home, and a donor pitch (2026-08-04)

Commits `087e72d0` (the feature) and `6c0a3998` (the seed fix that made it real).
Migration **`0146`** — choices plus a data rename; no DDL. Two deploys, both api; the second was
backend-only so the web trigger correctly skipped it.

`pytest` **5530** · `jest` **1417** · `next lint` **0 errors** · i18n **4520×3** · `tsc` clean ·
`makemigrations --check` clean. Five guards bite-checked.

## What the owner asked for

1. Two more invitation templates — one for admin, one for source.
2. The joining email exists in two places; remove the one under Reviewers.
3. The sponsor invitation here is the ORGANISATION's, not a peer's. It should pitch the concept and
   invite the reader to become **a donor of the organisation** who then sponsors deserving
   students — *"They do not become the sponsor of the org."*

All three shipped. The Source letter's premise was settled by the owner first: it is written for the
console that comes next.

## What shipped

**Four invitation letters, one per table.** `invite_admin`, `invite_reviewer` (renamed from
`invite_staff`), `invite_source`, `invite_sponsor`. Which letter a staff invite reads is derived
from `invitations.KIND_ROLES` — the same map that groups the page's tables — so finance is written
to as an admin and QC as a reviewer. A `partner` or `super` invite reads no stored template: those
are platform-level, and otherwise an org_admin editing "the admin invitation" would silently change
what a platform account is told.

**Admin and reviewer are seeded identically**, and that is the honest shape: the split is a change
of structure, not of copy. Its value is that the organisation can now make them differ.

**`partner_welcome` left the Reviewers read-only list** (six there now). Editable in one place and
read-only in another is worse than either alone — a reader of the read-only list concludes the
wording is fixed.

**The sponsor letter is a donor pitch** that keeps the nomination clause the 2026-07-28 ruling
requires, and now replies to the sponsor alias rather than general support.

## Three findings worth keeping

### 1. The donor pitch was guarded by the wrong voice guard

The tax-relief ban lived in `sponsor_comms`; this letter is a `PartnerEmailTemplate`, so its save
ran `partner_comms.banned_phrases`, which never banned it. **The one surface on the platform that is
explicitly a donor pitch was the only one not checking for the one sentence that can cost the reader
money** — HalaTuju holds no LHDN s44(6) approval.

The rule that produced it read sensibly and was even written down as a principle: *"each family owns
its own list — what counts as the wrong voice for a partner organisation is not what counts as the
wrong voice for a donor."* It assumed a family's audience matches its table, and stopped being true
the moment a sponsor letter was implemented in the partner table.

Fixed by scoping the split to **what the rule protects** rather than which table the row sits in:
`email_templates.UNIVERSAL_BANNED` holds the claims that are false or manipulative for every
audience; genuinely audience-specific voice rules stay local.

### 2. "Never overwrite an edit" is also a one-way valve

The seed keeps an existing row — right, because six production rows carry real human edits. It also
means **a rewritten built-in reaches nobody once the row exists.** The pitch was rewritten, the
deploy went green, the seed printed `kept`, and the old letter was still what would send. The owner
opened the page and correctly reported nothing had changed.

Every signal said success, which is worse than an error. The blunt fix was unavailable for the
reason the rule exists. So the reset became scopeable — `--kind` locally, `PARTNER_EMAIL_RESET_KINDS`
on the service, because the cron endpoint passes no command arguments.

### 3. A watcher that cannot fire looks exactly like a slow build

The build watch filtered on an 8-character SHA against Cloud Build's 7, so it matched nothing and
span long after both builds had succeeded. Re-armed after the second push, it then waited for two
builds when only one would run — the change was backend-only. Both times the visible effect was a
truthful-sounding "still building" about work that was finished or would never arrive.

## What I would do differently

- **Verify the CONTENT in production after a copy change, not that the job ran.** `kept` and `reset`
  both read as success in a log. One query against the stored subject would have caught it before
  the owner did.
- **Sanity-check a poll predicate before arming it** — run the query once and confirm it returns
  rows today.
- **When moving content onto a shared mechanism, list what that mechanism assumes** — here, that its
  table's audience is uniform. That question was in `lessons.md` already and is what found finding 1;
  it was not applied to the watcher or the seed.

## Owner's, still open

- **ms/ta for the new strings are my first drafts** — six labels plus a note. Particularly
  நன்கொடையாளர் for "donor", which now carries the framing the owner corrected.
- The organisation's sponsor invitation is **English-only** while the peer-to-peer one is
  trilingual. A donor pitch is exactly the letter that benefits from the reader's language. Not a
  regression; worth a decision.
- Unchanged from before: quote on request #2, `paused_by`, the `source_partner` role name, the
  dormancy threshold, Divya Adinarayanan's phone number.
