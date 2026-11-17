"""H6: a document slot takes four student uploads (the first, then three replaces) until a person asks again.

A slot is (application, doc type, household member, request code), the same slot the upload door
supersedes into; a pre-consent STR-route income doc also sweeps the legacy UNTAGGED copy, so its slot is
the earner's key plus the blank one (`slot_members`, from the upload door's own `earner_tag`).

THE RULE (one source of truth; the server decides, the client's `replace` flag changes nothing). Every
upload the door ACCEPTS is counted in `DocumentSlotReplaces.uploads` for its slot, and the count is never
lowered: Remove deletes the copies, not the count. Replaces used = uploads - 1 (the first upload is free).
An upload is refused 409 `replace_limit_reached` once the slot holds `UPLOAD_LIMIT` (4) uploads, whether or
not the slot was emptied by Remove, whatever the read said about the copy (a returned or problem copy counts
too: every accepted upload is a paid read), and whatever system ticket is open.

The one exemption: an ask a PERSON raised for this slot's type (and member, where it names one) AFTER the
slot's last upload. It lets ONE more upload in; that upload moves `last_upload_at` past the ask, so the ask
is answered as far as the cap goes. A person's ask is (`human_asks`):
- an officer's request (`source='officer'`, raised at `created_at`), or
- any doc ask a reviewer re-opened with "Ask again" (`params['asked_again_at']`, stamped by the admin view).
Never a system or Check 2 ticket on its own: those are raised by code, and the `<type>_missing` ticket that
Remove re-opens (`resolution.after_document_deleted`) carries no person's stamp, so the student cannot make
one herself. An officer's request also gives its own slot (its request code), which a student cannot invent:
`request_code_refusal` accepts only '' or the code of an officer document request on the case.

THE BLOCKER ALLOWANCE (owner 2026-11-17, fix round 3). Before consent nobody can ask: the reviewer's
requests are refused until the student consents, so a slot whose copy stops consent would be a dead end
at four. While `profile_completed_at` is unset AND the consent gate holds the student on this slot (its
live copy is a red, unreadable, not-an-offer or stranger's copy, or the slot is empty and the gate asks
for its type: `services.consent_blockers.consent_blocking_slots`), the slot takes up to
`BLOCKER_EXTRA` (4) more uploads, `HARD_LIMIT` (8) in all. It lapses the moment the copy passes or she
consents; a copy that does not block gets nothing extra. At the hard ceiling no ask is possible, so the
409 sends her to support (`replace_limit_support`), not to her reviewer. A person's ask still lets one
more in at any count.

Slots that predate the counter (no row yet) count their stored copies, superseded ones included; the row is
seeded from those copies the first time it is written (an upload or a Remove), so history is never lost.
The documents lock is checked first, in the view, exactly as for any upload.
"""
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response

from .models import ApplicantDocument

REPLACE_LIMIT = 3
UPLOAD_LIMIT = REPLACE_LIMIT + 1    # the first upload is free
BLOCKER_EXTRA = 4                   # pre-consent, while the slot holds the consent gate
HARD_LIMIT = UPLOAD_LIMIT + BLOCKER_EXTRA
REPLACE_LIMIT_REACHED = 'replace_limit_reached'
REPLACE_LIMIT_SUPPORT = 'replace_limit_support'   # the body `code` at the hard ceiling: no ask is possible
BAD_REQUEST_CODE = 'bad_request_code'
ASKED_AGAIN_AT = 'asked_again_at'   # ResolutionItem.params stamp written by the admin "Ask again"
_MESSAGE = ('You have already replaced this document 3 times. If it is still wrong, '
            'your reviewer will ask you for what is needed.')
# The web shows `scholarship.actionCentre.replaceLimitSupport` (en / ms / ta, with {supportEmail}); this is
# the English the 409 carries, with the same "write to us at" line as the account-claim refusals.
_SUPPORT_MESSAGE = ('You have sent this document 8 times and it still stops your application. '
                    'Please write to us at {email} and we will help.')

#: Types the serializer exposes `authenticity` for (single source: serializers/documents.py reads it).
AUTH_TYPES = ('ic', 'parent_ic', 'str', 'results_slip', 'birth_certificate', 'epf', 'offer_letter',
              'salary_slip', 'electricity_bill', 'water_bill', 'school_leaving_cert', 'higher_results')
#: Of those, the types where the student is shown ONLY a wrong-type reject (`not_<type>`); a suspect
#: band is hidden amber noise there.
AUTH_WRONG_TYPE_ONLY = ('salary_slip', 'electricity_bill', 'water_bill', 'school_leaving_cert')

_INCOME_EARNER_DOCS = ('str', 'parent_ic', 'salary_slip', 'epf')


def earner_tag(app, doc_type, member, request_code):
    """(str_income, member): who an STR-route income doc belongs to. The upload door's rule (see
    `DocumentListCreateView._earner_tag` for why): PRE-CONSENT, on the STR route, a blank-request income
    doc is the earner's; an IC the student tagged to someone else keeps that tag."""
    earner = (getattr(app, 'income_earner', '') or '').strip()
    str_income = (doc_type in _INCOME_EARNER_DOCS and not request_code
                  and (getattr(app, 'income_route', '') or '').strip() == 'str'
                  and (doc_type != 'parent_ic' or member in ('', earner))
                  and app.profile_completed_at is None)   # pre-consent only
    return str_income, (earner if str_income else member)


def slot_members(app, doc_type, member, request_code):
    """The member keys an upload of this (type, member, request code) sweeps: the tagged member, plus the
    legacy blank one for a pre-consent STR income doc. The door and the list both read it."""
    str_income, tagged = earner_tag(app, doc_type, member, request_code)
    return [tagged, ''] if str_income and tagged else [tagged]


def human_asks(app):
    """[(doc_type, member or '', raised_at)] for each OPEN doc ask a PERSON raised that the student can see:
    an officer's request (its `created_at`) or any ask re-opened with "Ask again" (its stamp). A set-aside
    auto item (recommended / funded) is not an ask. One query."""
    from django.conf import settings as _settings
    from .models import ResolutionItem
    from .resolution import item_set_aside, item_student_visible
    from .views.common import SET_ASIDE_STATES
    queries_live = getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False)
    aside = app.status in SET_ASIDE_STATES
    out = []
    for item in ResolutionItem.objects.filter(application_id=app.id, status='open', kind='doc').exclude(doc_type=''):
        if not item_student_visible(item, queries_live) or (aside and item_set_aside(item)):
            continue
        params = item.params if isinstance(item.params, dict) else {}
        stamps = [item.created_at] if item.source == 'officer' else []
        again = params.get(ASKED_AGAIN_AT)
        again = parse_datetime(again) if isinstance(again, str) else None
        if again is not None:
            stamps.append(again)
        if stamps:
            out.append((item.doc_type, params.get('household_member') or '', max(stamps)))
    return out


class SlotBook:
    """Every slot's upload count for one application: the counter rows, the stored copies of slots with no
    row yet, and (read only when a slot is full) the open person-raised asks. Two queries, three at most;
    the upload door and the documents list read the same answers from it."""

    def __init__(self, app):
        from .models import DocumentSlotReplaces
        self.app = app
        key = ('doc_type', 'household_member', 'request_code')
        self._rows = {(r['doc_type'], r['household_member'], r['request_code']): (r['uploads'], r['last_upload_at'])
                      for r in DocumentSlotReplaces.objects.filter(application_id=app.id)
                      .values(*key, 'uploads', 'last_upload_at')}
        self._copies = {(r['doc_type'], r['household_member'], r['request_code']): (r['n'], r['last'])
                        for r in ApplicantDocument.objects.filter(application_id=app.id).order_by()
                        .values(*key).annotate(n=Count('id'), last=Max('uploaded_at'))}
        self._asks = None
        self._blocking = None

    def uploads(self, doc_type, members, request_code):
        """(uploads so far, last upload time or None) over the slot's member keys."""
        total, last = 0, None
        for m in dict.fromkeys(members):
            k = (doc_type, m, request_code)
            n, at = self._rows.get(k) or self._copies.get(k) or (0, None)
            total += n
            if at is not None and (last is None or at > last):
                last = at
        return total, last

    def asked_again(self, doc_type, members, request_code):
        """True when a person asked for this slot's type (and member) after its last upload."""
        _n, last = self.uploads(doc_type, members, request_code)
        if self._asks is None:
            self._asks = human_asks(self.app)
        return any(t == doc_type and (not who or who in members) and (last is None or at > last)
                   for t, who, at in self._asks)

    def blocks_consent(self, doc_type, members, request_code):
        """Before consent only: the consent gate holds the student on this slot (its live copy, or its
        type missing). Read once per book, and only once a slot has used its four uploads."""
        if self.app.profile_completed_at is not None:
            return False
        if self._blocking is None:
            from .services.consent_blockers import consent_blocking_slots
            self._blocking = consent_blocking_slots(self.app)
        slots, missing = self._blocking
        return (any((doc_type, m, request_code) in slots for m in members)
                or any(t == doc_type and (who is None or who in members) for t, who in missing))

    def _blocker_left(self, doc_type, members, request_code, n):
        if n >= HARD_LIMIT or not self.blocks_consent(doc_type, members, request_code):
            return 0
        return HARD_LIMIT - n

    def allowed(self, doc_type, members, request_code):
        n, _last = self.uploads(doc_type, members, request_code)
        return (n < UPLOAD_LIMIT or self.asked_again(doc_type, members, request_code)
                or self._blocker_left(doc_type, members, request_code, n) > 0)

    def support_only(self, doc_type, members, request_code):
        """True when the slot is shut and no ask can open it: before consent, at the hard ceiling, its copy
        still holding the gate. The student is sent to support instead of told her reviewer will ask."""
        n, _last = self.uploads(doc_type, members, request_code)
        return (n >= HARD_LIMIT and not self.asked_again(doc_type, members, request_code)
                and self.blocks_consent(doc_type, members, request_code))

    def replaces_used(self, doc_type, members, request_code):
        n, _last = self.uploads(doc_type, members, request_code)
        return max(0, n - 1)

    def replaces_left(self, doc_type, members, request_code):
        """What the student pages show: the replaces left (0..3); once those are used, the blocker allowance
        left (pre-consent, up to the hard ceiling), or 1 when a person's ask lets one more in."""
        n, _last = self.uploads(doc_type, members, request_code)
        left = min(REPLACE_LIMIT, max(0, UPLOAD_LIMIT - n))
        if left:
            return left
        ask = 1 if self.asked_again(doc_type, members, request_code) else 0
        return max(ask, self._blocker_left(doc_type, members, request_code, n))


def _counter(application_id, doc_type, member, request_code, exclude_id=None):
    """The slot's counter row, created (seeded from its stored copies) when there is none yet."""
    from .models import DocumentSlotReplaces
    key = dict(application_id=application_id, doc_type=doc_type, household_member=member, request_code=request_code)
    qs = DocumentSlotReplaces.objects.filter(**key)
    if not qs.exists():
        copies = ApplicantDocument.objects.filter(**key)
        if exclude_id is not None:
            copies = copies.exclude(id=exclude_id)
        seed = copies.aggregate(n=Count('id'), last=Max('uploaded_at'))
        try:
            with transaction.atomic():
                DocumentSlotReplaces.objects.create(**key, uploads=seed['n'] or 0, last_upload_at=seed['last'])
        except IntegrityError:   # a parallel request made it first
            pass
    return qs


def record_upload(application_id, doc_type, member, request_code, doc_id):
    """Count one accepted upload (the new row `doc_id` is not part of the seed)."""
    _counter(application_id, doc_type, member, request_code, exclude_id=doc_id).update(
        uploads=F('uploads') + 1, last_upload_at=timezone.now())


def keep_count_before_remove(application_id, doc_type, member, request_code):
    """Remove hard-deletes the copies: make sure the slot's counter row exists first, so the count stays."""
    _counter(application_id, doc_type, member, request_code)


def request_code_refusal(app, doc_type, member, request_code):
    """A 400 Response unless the request code is '' or an officer document request on this case for this
    type (and member: the request's own, '' when it names none). A student cannot invent a slot. Any status:
    the Done card's Replace sends a resolved request's code, and each code is still one capped slot."""
    if not request_code:
        return None
    from .models import ResolutionItem
    item = ResolutionItem.objects.filter(application_id=app.id, source='officer', kind='doc',
                                         code=request_code, doc_type=doc_type).first()
    want = ((item.params or {}).get('household_member') or '') if item and isinstance(item.params, dict) else ''
    if item is not None and member == want:
        return None
    return Response({'error': BAD_REQUEST_CODE, 'code': BAD_REQUEST_CODE}, status=status.HTTP_400_BAD_REQUEST)


def replace_refusal(app=None, support=False):
    """The 409 for a full slot. `support` (the hard ceiling, `SlotBook.support_only`): the body `code` is
    `replace_limit_support` and the message names the application's support address (`branding`), the
    channel the student's other "write to us" messages give; `error` stays `replace_limit_reached`."""
    if support:
        from . import branding
        email = branding.for_application(app).email_support
        return Response({'error': REPLACE_LIMIT_REACHED, 'code': REPLACE_LIMIT_SUPPORT, 'support_email': email,
                         'message': _SUPPORT_MESSAGE.format(email=email), 'limit': REPLACE_LIMIT},
                        status=status.HTTP_409_CONFLICT)
    return Response({'error': REPLACE_LIMIT_REACHED, 'code': REPLACE_LIMIT_REACHED,
                     'message': _MESSAGE, 'limit': REPLACE_LIMIT}, status=status.HTTP_409_CONFLICT)
