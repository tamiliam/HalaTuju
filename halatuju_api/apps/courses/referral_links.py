"""Referral partners and the course-selector's `?ref=` columns (2026-10-09; Sprint D 2026-10-19).

Owner's model (decisions.md, "The student record has two independent columns: source and referral
partner"). Three categories: ORGANISATIONS (tenants — `PartnerOrganisation.objects.tenants()`),
SOURCES (`scholarship.ReferralSource`, owned by the organisation that added them) and REFERRAL
PARTNERS (platform level, owned by no organisation, `partner_organisations` rows marked
`is_referral_partner`; today only CUMIG). The bursary and the course selector never write each
other's columns:

- the bursary's "Who referred you?" answer lives on each APPLICATION (`ScholarshipApplication
  .referral_code` / `.source`, written once at submit) — never on the profile;
- `StudentProfile.referred_by_org` — the REFERRAL PARTNER whose `?ref=` link brought them, and the
  chip `StudentProfile.referral_source` — the `?ref=` code itself (the partner dashboard's Source
  column). Both written ONLY here (`apply_ref_code`, fed by `ProfileSyncView`), first touch.

Sources-and-referrals Sprint A built the split; Sprint B (2026-10-18) moved sources into their own
table; Sprint C (2026-10-19) moved every bursary reader onto the application's own answer; Sprint D
(2026-10-19) stopped the bursary writing the profile at all (the chip and `StudentProfile.source`,
which left the model) and added the super-only mark / unmark (`mark_refusal`)
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


#: Why an invitation was refused, keyed by the `code` the invite view answers with. The sentence is
#: what the staff screens show (they print the server's `error`), so it is written for a person.
INVITE_REFUSALS = {
    'org_required': 'A partner must belong to an organisation',
    'org_not_found': 'Organisation not found',
    'bad_code': 'The organisation code may use only lower-case letters, digits, - and _.',
    'code_reserved': 'That code is reserved and cannot be a referral partner.',
    'org_is_tenant': 'That organisation runs gifts on HalaTuju, so it cannot have a partner login.',
    'not_a_referral_partner': 'That organisation is not a referral partner, so it cannot have a '
                              'partner login. A referral partner is marked by the platform first.',
    'org_is_referral_partner': 'That organisation is a platform referral partner, so it cannot '
                               'become an organisation that runs gifts.',
    'code_taken': 'That code already belongs to a referral source, so it cannot be used for a new '
                  'organisation. Choose another code.',
    'not_a_tenant': 'That organisation is a referral source, not an organisation that runs gifts.',
}


def tenant_invite_refusal(org, *, new):
    """Why an `org_admin` invitation may NOT install a tenant on this `partner_organisations` row,
    or None (sources Sprint B review, 2026-10-18). The invite reuses an existing row by code
    (`get_or_create`) or by id, and installing an org_admin makes the row a tenant
    (`tenants()`), switches its scholarship module on and bills it. So it is refused for:
    - a platform REFERRAL PARTNER (`org_is_referral_partner`) — owned by no organisation;
    - a source's OLD row — one with a source twin in `referral_sources` (same id AND code), i.e.
      every non-tenant row the Sprint B copy found. On the new-organisation path that reads as
      `code_taken` (the form asked for a NEW organisation); by id as `not_a_tenant`.
    A tenant row (including one whose admins have lapsed) passes, as before."""
    if org.is_referral_partner:
        return 'org_is_referral_partner'
    if source_twin(org.pk) is not None:
        return 'code_taken' if new else 'not_a_tenant'
    return None


def partner_invite_org(org_id=None, new_code='', new_name='', contact_person='', phone=''):
    """The `partner_organisations` row a `partner`-role invitation may bind its login to, or why not.

    Returns `(row, None)` or `(None, refusal code)` (`INVITE_REFUSALS`). Sources Sprint B
    (2026-10-18), owner's choice "refuse, or mark" decided as REFUSE:
    - an EXISTING row must already be an active REFERRAL PARTNER (`referral_partners()`). An
      invitation never marks one — marking changes which students a `?ref=` link collects, so it is
      a platform decision taken on its own, not a side effect of asking someone to sign in. A
      tenant, a source's old row, a switched-off row or a reserved code is refused.
    - a NEW organisation (code + name) is created AS a referral partner: it exists only for this
      login, which is what a referral partner is. A code that already exists is the rule above.
    A partner login never binds to a SOURCE (sources live in their own table since Sprint B)."""
    from .models import PartnerOrganisation
    if new_code and new_name:
        code = _clean_code(new_code)
        if not code:
            return None, 'bad_code'
        if code in RESERVED_CODES:
            return None, 'code_reserved'
        org, created = PartnerOrganisation.objects.get_or_create(code=code, defaults={
            'name': new_name, 'contact_person': contact_person or '', 'phone': phone or '',
            'is_referral_partner': True})
        if created:
            return org, None
    elif org_id:
        try:
            org = PartnerOrganisation.objects.filter(pk=int(org_id)).first()
        except (TypeError, ValueError):
            org = None
        if org is None:
            return None, 'org_not_found'
    else:
        return None, 'org_required'
    if PartnerOrganisation.objects.tenants().filter(pk=org.pk).exists():
        return None, 'org_is_tenant'
    if not referral_partners().filter(pk=org.pk).exists():
        return None, 'not_a_referral_partner'
    return org, None


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
    - the `referral_source` chip (the course-selector partner dashboard's Source column) — only
      when it is still empty. Sprint D (2026-10-19): the bursary no longer writes the chip, so
      the old "only while she has no application" condition, which protected the bursary answer
      on it, went with it; first touch still means a resend can never move it.
    Returns the fields changed."""
    code = _clean_code(code)
    if not code:
        return []
    changed = []
    if profile.referred_by_org_id is None:
        partner = referral_partners().filter(code=code).first()
        if partner is not None:
            profile.referred_by_org = partner
            changed.append('referred_by_org')
    if not profile.referral_source:
        profile.referral_source = code
        changed.append('referral_source')
    if changed:
        profile.save(update_fields=changed + ['updated_at'])
    return changed


def _source_model():
    """`scholarship.ReferralSource`, looked up in the app registry rather than imported — the
    courses → scholarship back-edge may not grow (`test_code_standards.py`). Until Sprint D it was
    reached through `StudentProfile.source`, which left the model then."""
    from django.apps import apps
    return apps.get_model('scholarship', 'ReferralSource')


def source_twin(partner_id):
    """The SOURCE row copied from this `partner_organisations` row, or None.

    Sources Sprint B (2026-10-18) copied every source out of `partner_organisations` KEEPING ITS ID,
    so a source's old row has a twin with the same id AND the same code. Both must match: ids
    allotted after the copy come from two separate sequences, so an id alone could pair two
    unrelated organisations. Read ONLY by `tenant_invite_refusal` above (is this a source's old
    row?). Sprint C (2026-10-19) retired the witness bridge that also read it: the witness is the
    application's source, never the referral partner, so nothing pairs CUMIG's two rows any more."""
    from .models import PartnerOrganisation
    if partner_id is None:
        return None
    return _source_model().objects.filter(
        pk=partner_id,
        code__in=PartnerOrganisation.objects.filter(pk=partner_id).values('code')).first()


#: Why a super's mark / unmark was refused (sources Sprint D, roadmap item 1b). Sentences, like
#: `INVITE_REFUSALS`, because a screen prints the server's `error`.
MARK_REFUSALS = {
    'org_is_tenant': 'That organisation runs gifts on HalaTuju, so it cannot be a referral partner.',
    'code_reserved': 'That code is reserved and cannot be a referral partner.',
    'org_inactive': 'That organisation is switched off (a retired source row, or suspended), so '
                    'it cannot be marked a referral partner.',
    'org_is_source': 'That row is a referral source\'s old row, so it cannot be marked a referral '
                     'partner. Invite the partner as a new organisation instead.',
    'bad_code': 'That organisation\'s code is not one a ?ref= link can carry (only lower-case '
                'letters, digits, - and _), so it cannot be a referral partner.',
    'has_partner_logins': 'That referral partner still has partner logins. Revoke them on '
                          'Referral partners first, then unmark it.',
}


def mark_refusal(org, mark):
    """Why `org` may NOT be marked (`mark` true) or unmarked (false) a referral partner, or None.

    Marking decides which students a `?ref=` link collects for the partner logins (who see NRIC,
    phone, address and income), so it is a platform decision a SUPER takes on its own — the view
    is super-only. Never a tenant, a reserved code, or a switched-off row (Sprint D retired the
    sources' old rows by switching them off; marking one would quietly revive its `?ref`). An
    unmark is refused while the row still has active `partner` logins: they would go on seeing
    their students from a row that is no longer a referral partner — the one state the invite
    refuses to create. Existing `referred_by_org` links are never touched by either."""
    from .models import PartnerAdmin, PartnerOrganisation
    if mark:
        if PartnerOrganisation.objects.tenants().filter(pk=org.pk).exists():
            return 'org_is_tenant'
        if org.code in RESERVED_CODES:
            return 'code_reserved'
        if not org.is_active:
            return 'org_inactive'
        # Review backstops: a source's old row (a twin in `referral_sources`) is a SOURCE's, so it
        # is never newly marked (CUMIG, already marked, may stay); and a code a `?ref=` link could
        # never carry (`_clean_code` would change it) could never link anyone.
        if not org.is_referral_partner and source_twin(org.pk) is not None:
            return 'org_is_source'
        if _clean_code(org.code) != org.code:
            return 'bad_code'
        return None
    if PartnerAdmin.objects.filter(org=org, role='partner', is_active=True).exists():
        return 'has_partner_logins'
    return None
