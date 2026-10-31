"""The READER of a person's own activity list (common profile S4, 2026-10-31; D7, D8).

Served by `GET admin/me/activity/` (`views_admin/me.AdminMeActivityView`). The writer is
`staff_activity.py`; this module only reads, and only the caller's OWN rows — for every role, a
super included. Nobody reads anybody else's list (that is why the rows go with the person, D6).

⚠ D8 — A NAME IS LOOKED UP WHEN THE LIST IS READ, AND SHOWN ONLY IF THE VIEWER MAY SEE THAT SUBJECT
NOW. A row stores ids, never copied text, so what the viewer is told about a subject is decided
today, by today's rules, not by whatever they could see on the day they acted:
  * a student (an application): the staff detail view's own rule — the organisation fence plus the
    B40 scope (`see_all` reads the organisation, `review` only the cases assigned to them NOW), read
    through the view's own helpers (`_b40_scope`, `_org_allows`) so the two cannot drift; for a SOURCE
    user, `source_access.applications_for`. Otherwise "a student".
  * a staff member: the viewer themself, a super, or someone in the viewer's organisation (never for
    a source user, who sees only themself). Otherwise "a team member".
  * an invitation, a payment run, a contract template, an invoice, a request: the subject's
    organisation is the viewer's (or the viewer is a super), and — for a run — the viewer may still
    open Payments (`payments_chain.may_read`). The label is a REFERENCE, never typed text: a run's
    reference, a template's version, an invoice's number, a request's number.
  * a benefactor: a super, or the benefactor is a member of one of the viewer's organisation's gifts.
  * a credit and a shop flag: always the neutral word (a bank reference and a shop name are not
    worth the risk of a leak, and the money screens show them).
  * a MENTOR (student maintenance S7a) is an outsider like a source user: no permission and on no staff
    list, so every subject but themself reads as the neutral word (`_outsider`).
⚠ D7 — a subject whose row is gone (a purged student, a deleted account) reads "… (removed)".

Every subject type is fetched in ONE query per page, whatever the page size (`test_my_activity.py`
pins the count). ``meta`` is re-filtered on the way out to the closed key list.
"""
import base64
from datetime import datetime

from django.db.models import Q

from . import staff_activity
from .models import StaffActivity

PAGE_DEFAULT = 30
PAGE_MAX = 100
#: `?kind=` → the verbs it shows. 'all' is no filter.
FILTERS = ('all', 'students', 'money', 'profile')

#: The neutral words, by subject type: (hidden, removed).
NEUTRAL = {
    'application': ('a student', 'a student (removed)'),
    'staff': ('a team member', 'a team member (removed)'),
    'invitation': ('an invitation', 'an invitation (removed)'),
    'payment_run': ('a payment run', 'a payment run (removed)'),
    'credit': ('a credit', 'a credit (removed)'),
    'contract_template': ('a contract template', 'a contract template (removed)'),
    'sponsor': ('a benefactor', 'a benefactor (removed)'),
    'invoice': ('an invoice', 'an invoice (removed)'),
    'org_request': ('a request', 'a request (removed)'),
    'merchant_flag': ('a shop', 'a shop (removed)'),
}


class BadQuery(ValueError):
    """`bad_kind`, `bad_cursor` or `bad_limit` — the view's 400."""


# ── paging ─────────────────────────────────────────────────────────────────────────────────────
def encode_cursor(row):
    raw = f'{row.created_at.isoformat()}|{row.pk}'.encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


#: The largest id a cursor may carry (a Postgres bigint); anything beyond is `bad_cursor`, never a 500.
MAX_ID = 2 ** 63 - 1


def decode_cursor(cursor):
    """``(created_at, id)`` from a cursor, or `BadQuery('bad_cursor')` — never another exception:
    the id is bounded to a bigint and the moment must carry its time zone (review L5)."""
    try:
        raw = base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)).decode()
        stamp, pk = raw.rsplit('|', 1)
        stamp, pk = datetime.fromisoformat(stamp), int(pk)
    except (ValueError, TypeError, UnicodeDecodeError, OverflowError):
        raise BadQuery('bad_cursor')
    if stamp.tzinfo is None or not 0 < pk <= MAX_ID:
        raise BadQuery('bad_cursor')
    return stamp, pk


def parse_limit(value):
    """1..PAGE_MAX in ASCII digits only — '²' and '٣' satisfy `isdigit()` but not `int()` (review L5)."""
    if value in (None, ''):
        return PAGE_DEFAULT
    text = str(value)
    try:
        limit = int(text) if text.isascii() and text.isdigit() else None
    except (ValueError, OverflowError):
        limit = None
    if limit is None or not 1 <= limit <= PAGE_MAX:
        raise BadQuery('bad_limit')
    return limit


def page(viewer, *, kind='all', cursor=None, limit=PAGE_DEFAULT):
    """``(rows, next_cursor)`` — the viewer's OWN rows, newest first, keyed on (created_at, id)."""
    if kind not in FILTERS:
        raise BadQuery('bad_kind')
    qs = StaffActivity.objects.filter(actor_id=viewer.pk)   # org-fence: own rows only, every role
    if kind != 'all':
        qs = qs.filter(verb__in=[v for v, k in staff_activity.KIND_OF_VERB.items() if k == kind])
    if cursor:
        stamp, pk = decode_cursor(cursor)
        qs = qs.filter(Q(created_at__lt=stamp) | Q(created_at=stamp, id__lt=pk))
    rows = list(qs.order_by('-created_at', '-id')[:limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (encode_cursor(rows[-1]) if more and rows else None)


# ── the subjects, one query per type ───────────────────────────────────────────────────────────
def _subject_ids(rows, kind):
    return {r.subject_id for r in rows if r.subject_type == kind and r.subject_id is not None}


def _outsider(viewer):
    """A source user or a mentor: deny by default, on no staff list — names nothing but themself."""
    return viewer.is_source_user or viewer.is_mentor


def _same_org(viewer, org_id):
    return viewer.is_super or (org_id is not None and org_id == viewer.owning_organisation_id)


def _applications(viewer, ids, view):
    from .models import ScholarshipApplication
    found = {a.pk: a for a in ScholarshipApplication.objects.filter(pk__in=ids)   # org-fence: judged below
             .select_related('profile')} if ids else {}
    if viewer.is_source_user:
        from . import source_access
        visible = set(source_access.applications_for(viewer).filter(pk__in=list(found))
                      .values_list('pk', flat=True)) if found else set()
    elif viewer.is_mentor:
        visible = set()
    else:
        scope = view._b40_scope(viewer)
        visible = {pk for pk, app in found.items()
                   if scope != 'none' and view._org_allows(viewer, app)
                   and (scope == 'all' or app.assigned_to_id == viewer.pk)}
    return {pk: (getattr(app.profile, 'name', '') or None) if pk in visible else False
            for pk, app in found.items()}


def _staff(viewer, ids):
    from apps.courses.models import PartnerAdmin
    out = {}
    for pa in PartnerAdmin.objects.filter(pk__in=ids) if ids else ():   # org-fence: judged below
        mine = pa.pk == viewer.pk
        team = (not _outsider(viewer)) and _same_org(viewer, pa.owning_organisation_id)
        out[pa.pk] = pa.name if (mine or team) else False
    return out


def _by_org(model, ids, viewer, label, org_field='organisation_id', allowed=True, related=()):
    qs = model.objects.filter(pk__in=ids).select_related(*related) if ids else ()  # org-fence: below
    return {o.pk: (label(o) if allowed and not _outsider(viewer)
                   and _same_org(viewer, _attr(o, org_field)) else False) for o in qs}


def _attr(obj, dotted):
    for part in dotted.split('.'):
        obj = getattr(obj, part, None)
    return obj


def _sponsors(viewer, ids):
    from . import surface_gates
    from .models import Sponsor, SponsorProgrammeMembership
    found = list(Sponsor.objects.filter(pk__in=ids)) if ids else []   # org-fence: judged below
    if not surface_gates.may_read_sponsors(viewer):     # review M3: the Sponsors list's own gate
        member = set()
    elif viewer.is_super:
        member = {s.pk for s in found}
    elif _outsider(viewer) or not found or viewer.owning_organisation_id is None:
        member = set()
    else:
        member = set(SponsorProgrammeMembership.objects.filter(
            sponsor_id__in=[s.pk for s in found],
            programme__organisation_id=viewer.owning_organisation_id)
            .values_list('sponsor_id', flat=True))
    return {s.pk: (s.name if s.pk in member else False) for s in found}


def _invoices(viewer, ids):
    """Through the invoice screen's OWN gate and fence (review M3): a tenant sees its own SENT
    invoices only; anyone the screen refuses sees the neutral word."""
    from . import surface_gates
    from .models import Invoice
    if not ids:
        return {}
    found = set(Invoice.objects.filter(pk__in=ids).values_list('pk', flat=True))  # org-fence: below
    shown = {}
    if surface_gates.may_read_invoices(viewer) and not _outsider(viewer):
        from .views_admin.invoices import _InvoiceBase
        shown = dict(_InvoiceBase()._visible_invoices(viewer, viewer.is_super)
                     .filter(pk__in=found).values_list('pk', 'number'))
    return {pk: shown.get(pk, False) for pk in found}


def _neutral_only(model, ids):
    return {pk: False for pk in model.objects.filter(pk__in=ids).values_list('pk', flat=True)} \
        if ids else {}     # org-fence: existence only, no label is ever served


def _labels(viewer, rows, view):
    """``{(subject_type, id): name | False}`` — False = exists but hidden; absent = removed."""
    from . import payments_chain, surface_gates
    from .models import (ContractTemplate, Donation, Invitation, MerchantFlag, OrgRequest,
                         PaymentRun)
    # Review M3: each label is gated by the SAME predicate the subject's own screen asks today, so a
    # viewer demoted since sees the neutral word the moment the screen answers 403.
    tables = {
        'application': _applications(viewer, _subject_ids(rows, 'application'), view),
        'staff': _staff(viewer, _subject_ids(rows, 'staff')),
        'invitation': _by_org(Invitation, _subject_ids(rows, 'invitation'), viewer,
                              lambda i: i.name or None, allowed=surface_gates.may_read_team(viewer)),
        'payment_run': _by_org(PaymentRun, _subject_ids(rows, 'payment_run'), viewer,
                               lambda r: r.reference, allowed=payments_chain.may_read(viewer)),
        'contract_template': _by_org(ContractTemplate, _subject_ids(rows, 'contract_template'), viewer,
                                     lambda t: t.version,
                                     allowed=surface_gates.may_open_contracts(viewer)),
        'invoice': _invoices(viewer, _subject_ids(rows, 'invoice')),
        'org_request': _by_org(OrgRequest, _subject_ids(rows, 'org_request'), viewer,
                               lambda r: f'#{r.pk}', allowed=(surface_gates.requests_live()
                                                              and surface_gates.requests_role(viewer))),
        'sponsor': _sponsors(viewer, _subject_ids(rows, 'sponsor')),
        'credit': _neutral_only(Donation, _subject_ids(rows, 'credit')),
        'merchant_flag': _neutral_only(MerchantFlag, _subject_ids(rows, 'merchant_flag')),
    }
    return {(kind, pk): label for kind, found in tables.items() for pk, label in found.items()}


def _served_subject(row, labels):
    if not row.subject_type:
        return None
    hidden, removed = NEUTRAL.get(row.subject_type, ('something', 'something (removed)'))
    key = (row.subject_type, row.subject_id)
    if row.subject_id is None or key not in labels:
        return {'type': row.subject_type, 'state': 'removed', 'label': removed, 'id': None}
    label = labels[key]
    if label is False:
        return {'type': row.subject_type, 'state': 'hidden', 'label': hidden, 'id': None}
    # TD-445: a visible subject with no name (a purged invitation, a student with no name) is served
    # `label: None`, never the English neutral word: the web puts in its own translated one.
    return {'type': row.subject_type, 'state': 'visible', 'label': label or None,
            'id': row.subject_id}


def _safe_meta(meta):
    """The stored meta, re-filtered to the closed key list (silently: it was checked on the way in)."""
    if not isinstance(meta, dict):
        return {}
    return {k: v for k, v in meta.items()
            if k in staff_activity.META_KEYS
            and staff_activity._allowed(staff_activity.META_KEYS[k], v)}


def items(viewer, rows, view):
    """The served list: an ALLOWLIST of keys per row (`test_my_activity` pins it)."""
    labels = _labels(viewer, rows, view)
    return [{
        'id': row.pk,
        'verb': row.verb,
        'kind': staff_activity.KIND_OF_VERB.get(row.verb, 'other'),
        'created_at': row.created_at.isoformat(),
        'backfilled': row.backfilled,
        'subject': _served_subject(row, labels),
        'meta': _safe_meta(row.meta),
    } for row in rows]
