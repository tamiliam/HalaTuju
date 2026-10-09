"""The student record's two referral columns: SOURCE and REFERRAL PARTNER (2026-10-09).

Owner's model (decisions.md, "The student record has two independent columns: source and referral
partner"). Three categories share `partner_organisations` today: ORGANISATIONS (tenants —
`PartnerOrganisation.objects.tenants()`), SOURCES (owned by the organisation that added them) and
REFERRAL PARTNERS (platform level, owned by no organisation, marked `is_referral_partner`; today only
CUMIG, whose row is also a source). A student carries two INDEPENDENT columns, and NEITHER WRITER
EVER TOUCHES THE OTHER:

- `StudentProfile.source` — the source the student named on the bursary "Who referred you?" form.
  Written ONLY by the bursary submit (`scholarship.services.profile_sync`); NULL for a fixed choice.
- `StudentProfile.referred_by_org` — the REFERRAL PARTNER whose `?ref=` link brought them. Written
  ONLY here (`apply_ref_code`, fed by `ProfileSyncView`): first touch, referral-partner rows only.

Sources-and-referrals Sprint A built this; Sprint B moves sources into their own table, Sprint C
moves every reader of the legacy chip (`referral_source`) onto the per-application answer
(`docs/plans/2026-10-09-sources-and-referrals-roadmap.md`).

⚠ NOT ACCESS CONTROL. The partner role's course-selector list is scoped by `referred_by_org` — that
is the `partner` role's purpose — and nothing else may use either column as a fence.
"""

import re

#: What a `?ref=` code may look like: the shape every stored code has (Sources POST lower-cases;
#: the existing rows are `cumig`, `smc`, `sathya_sai`, …) and no longer than the chip column (50).
_CODE_SHAPE = re.compile(r'[a-z0-9_-]{1,50}')

#: Codes a referral partner may never carry: the three fixed form choices
#: (`scholarship.gift_sources.FIXED_CODES`) and the house organisation (`partner_comms.HOUSE_ORG_CODE`).
#: A COPY, on purpose — importing them would grow the courses → scholarship back-edge, which may not
#: grow. `test_two_referral_columns.py` asserts the copy still equals both originals.
RESERVED_CODES = ('halatuju', 'social', 'other', 'brightpath')


def referral_partners():
    """Every ACTIVE platform referral partner — the only rows a `?ref=` link may link. Never a tenant,
    never a row carrying one of the three fixed form codes or the house organisation's code (review
    fix, 2026-10-09): a mis-marked row must not be able to collect those students."""
    from .models import PartnerOrganisation
    return (PartnerOrganisation.objects.filter(is_referral_partner=True, is_active=True)
            .exclude(code__in=RESERVED_CODES)
            .exclude(pk__in=PartnerOrganisation.objects.tenants().values('pk')))


def _clean_code(code):
    """A usable code, or '' — ASCII, lower-cased, `[a-z0-9_-]`, 1 to 50 characters. Anything else
    (not a string, a NUL or control character, spaces inside, too long) links and writes nothing,
    and never raises."""
    if not isinstance(code, str) or not code.isascii():
        return ''
    code = code.strip().lower()
    return code if _CODE_SHAPE.fullmatch(code) else ''


def apply_ref_code(profile, code):
    """A `?ref=` code the sign-in sync resends from the browser (it resends it on EVERY sign-in).

    FIRST TOUCH on both things it may write, so a resend can never move either:
    - `referred_by_org` — only when it is still empty, and only to an active REFERRAL PARTNER. An
      unknown code, a source, a tenant or a switched-off row links nothing.
    - the legacy `referral_source` chip (kept so its course-selector readers behave as before until
      Sprint C) — only when it is still empty AND the student has no bursary application. The
      bursary answer owns the chip once she has applied, so a `?ref` can never overwrite it or move
      what the bursary counts and partner emails see.
    It NEVER touches `source`. Returns the fields changed."""
    code = _clean_code(code)
    if not code:
        return []
    changed = []
    if profile.referred_by_org_id is None:
        partner = referral_partners().filter(code=code).first()
        if partner is not None:
            profile.referred_by_org = partner
            changed.append('referred_by_org')
    if not profile.referral_source and not profile.scholarship_applications.exists():
        profile.referral_source = code
        changed.append('referral_source')
    if changed:
        profile.save(update_fields=changed + ['updated_at'])
    return changed


def referring_org(profile):
    """The ONE organisation the witness chain and the cockpit read as "who referred this student",
    until Sprint C splits them: the SOURCE she named on the bursary form, else her REFERRAL PARTNER.

    Before the two columns existed, `referred_by_org` held whichever of the two was written last,
    and three readers used it: the witness request (`bursary._resolve_witness_org`), the witness
    authority check (`views_admin/graduation.py`) and the cockpit's `referred_by_org` (its referral
    pill and the "sourceless" witness dropdown). This answer keeps each of them where it was for every
    student whose bursary answer named a source. Sprint C makes the witness read the source only
    (owner: never the referral partner)."""
    if profile is None:
        return None
    return getattr(profile, 'source', None) or getattr(profile, 'referred_by_org', None)
