"""H3b (2026-11-16, roadmap H3 Goal B) - an OLD confirmation letter asks for a RECENT one.

When the student's newest CONFIRMATION-of-studies letter (``pathway_engine.is_confirmation_letter``; the
offer slot holds both kinds) was issued more than the organisation's ``recent_letter_window_months`` ago
(platform default 6; owner, 2026-11-18), AND her course should already have started, Check 2 raises ONE soft document
request, ``CODE``: "please upload a recent confirmation letter from your institution".

SOFT BY DESIGN (the plan: a request, no block). It is an ordinary Check-2 doc request
(``check2_queries.DOC_SPECS``): it never blocks submission, never fails a fact, never touches a
verdict, the pathway or the money, and - unlike every other open student task - it does NOT hold
reviewer assignment (``services.queries_sla`` leaves ``CODE`` out of the open-task hold, fix round 1).

NOT BEFORE THE COURSE STARTS. A letter read with a reporting date still to come (today or later), or a
reporting date that cannot be read to a day and might still be to come, means no ask: a letter
is naturally months old before she reports. Only a reporting date in the past (or, read only to its
year, a year before this one) lets the ask fire. A letter with NO reporting date at all (most
confirmation letters) keeps the plain rule: the letter is older than the window.

NO GUESSING. The letter's issue date is ``vision_fields['fields']['offer_date']``; a date this strict
reader cannot place exactly (no year, two years, an ambiguous order, no day) means NO ask.

CONFIRMATION LETTERS ONLY (owner, 2026-11-18: "The recent requirement only applies to confirmation
letter. Not to offer letters."). An offer letter, of any age, never raises the ask. A confirmation
letter only stands in for a missing offer letter (owner, same day: "When the student doesn't have an
offer letter he or she uploads a confirmation letter in its stead. That must be recent."), so ANY
non-failing offer letter on file, in any version of the slot, means no ask at all.

NO LOOP. A recent CONFIRMATION letter on file closes it: any institution, live or kept out of the live
slot by the keep-better promotion (so every version of the slot is read), dated inside the window and
not FAILED (``offer_fails``). A suspect or unscored letter still counts - she has done what we asked; a
person judges the letter itself. A failing newest letter is left to its own, stronger ask.
"""
import calendar
import datetime as _dt
import re

from django.utils import timezone

#: The Check-2 doc-request code (``check2_queries.DOC_SPECS`` / ``GOVERNED_BY``).
CODE = 'recent_letter_needed'
#: The organisation tunable (``apps.courses.org_config_registry``).
WINDOW_KEY = 'recent_letter_window_months'

_ORDINAL = re.compile(r'(\d)(?:st|nd|rd|th|hb)\b')
_DMY = re.compile(r'(\d{1,2})[./-](\d{1,2})[./-](20\d{2})')
_YMD = re.compile(r'(20\d{2})-(\d{1,2})-(\d{1,2})')
_D_MON_Y = re.compile(r'(\d{1,2})[ .-]+([a-z]+)\.?[ .-]+(20\d{2})')
_MON_D_Y = re.compile(r'([a-z]+)\.? (\d{1,2}) (20\d{2})')
_YEAR = re.compile(r'\b(20\d{2})\b')


def _month(word):
    from .pathway_engine import _RD_MONTHS
    return {**_RD_MONTHS, 'january': 1}.get(word)


def _field(doc, key):
    vf = getattr(doc, 'vision_fields', None)
    fields = vf.get('fields') if isinstance(vf, dict) else None
    raw = fields.get(key) if isinstance(fields, dict) else None
    return raw if isinstance(raw, str) else None


def letter_date(doc):
    """The letter's issue date as a ``date``, or None when it cannot be read EXACTLY. The whole value
    must be one date: D/M/YYYY (``/ . -``), YYYY-MM-DD, "D Month YYYY" or "Month D, YYYY" (Malay or
    English month names). Anything else - a two-digit year, a stray word, an impossible day - is None
    (TD-644: forms such as "5 Mac 2026M" or a date followed by its Hijri date are not read)."""
    raw = _field(doc, 'offer_date')
    if raw is None:
        return None
    s = ' '.join(_ORDINAL.sub(r'\1', raw.strip().lower()).replace(',', ' ').split())
    parts = None
    if m := _DMY.fullmatch(s):
        parts = (m.group(3), m.group(2), m.group(1))
    elif m := _YMD.fullmatch(s):
        parts = (m.group(1), m.group(2), m.group(3))
    elif m := _D_MON_Y.fullmatch(s):
        parts = (m.group(3), _month(m.group(2)), m.group(1))
    elif m := _MON_D_Y.fullmatch(s):
        parts = (m.group(3), _month(m.group(1)), m.group(2))
    if parts is None or parts[1] is None:
        return None
    try:
        return _dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def course_should_have_started(doc, today) -> bool:
    """May the course on this letter already have started? ``reporting_date`` is the letter's
    report / registration date (``student_offer_check``), read by the money module's own
    ``pathway_engine.parse_reporting_date`` (imported, not copied):
      * no reporting date on the letter at all  -> True (the plain rule: only the letter's age counts);
      * read to a day                            -> True only when that day is BEFORE today;
      * not read to a day                        -> True only when every year it names is before this
                                                    one (else it might still be to come: no ask)."""
    from .pathway_engine import parse_reporting_date
    raw = (_field(doc, 'reporting_date') or '').strip()
    if not raw:
        return True
    when = parse_reporting_date(raw)
    if when is not None:
        return when < today
    years = [int(y) for y in _YEAR.findall(raw)]
    return bool(years) and max(years) < today.year


def cutoff(today, months):
    """``today`` minus ``months`` calendar months, the day clamped to that month's end. A letter dated
    ON the cutoff is still recent; one day earlier is old."""
    year, month0 = divmod(today.year * 12 + today.month - 1 - int(months), 12)
    return _dt.date(year, month0 + 1, min(today.day, calendar.monthrange(year, month0 + 1)[1]))


def window_months(application):
    from apps.courses import public as courses_public   # the courses door (F2b), not org_config directly
    return courses_public.org_config.value(getattr(application, 'owning_organisation', None), WINDOW_KEY)


def _slot_letters(application):
    """``(confirmation letters, offer letters)`` in ANY version of the offer slot, each newest first
    (the live one and any kept out of the live slot by the keep-better promotion). Served from the open
    document snapshot (unfiltered, so superseded rows are there) when one is open; else one query."""
    from . import document_snapshot as snap
    from .pathway_engine import is_confirmation_letter
    rows = snap._rows(application)
    if rows is None:
        # all-versions-read: a letter may be KEPT OUT of the live slot (keep-better); every version counts.
        rows = application.documents.filter(doc_type='offer_letter').order_by(*snap.SNAPSHOT_ORDER)
    slot = [d for d in rows if d.doc_type == 'offer_letter']
    confirmations = [d for d in slot if is_confirmation_letter(d)]
    offers = [d for d in slot if not is_confirmation_letter(d)]
    return confirmations, offers


def wanted(application, today=None) -> bool:
    """Should Check 2 ask this student for a recent confirmation letter? Soft; see the module notes.
    No when any non-failing OFFER letter is on file (owner, 2026-11-18: a confirmation letter is
    uploaded only "when the student doesn't have an offer letter ... in its stead"). Otherwise yes only
    when her newest confirmation letter (any version of the slot) is readable, not failing, dated before
    the window's edge, its course should already have started, and no confirmation letter dated inside
    the window is on file. An offer letter never raises the ask."""
    from .document_snapshot import has_live_doc
    from .pathway_engine import offer_fails
    if not has_live_doc(application, 'offer_letter'):
        return False
    letters, offers = _slot_letters(application)
    if not letters or any(not offer_fails(d) for d in offers):
        return False
    today = today or timezone.localdate()
    edge = cutoff(today, window_months(application))
    for doc in letters:
        when = letter_date(doc)
        if when is not None and when >= edge and not offer_fails(doc):
            return False                                  # a recent confirmation letter closes it
    newest = letters[0]
    when = letter_date(newest)
    if when is None or offer_fails(newest):
        return False
    return when < edge and course_should_have_started(newest, today)


def offer_asks(application):
    """``(reporting_date_unknown, recent_letter_wanted)`` for the Check-2 gap pass, reading the
    application's documents ONCE for both letter asks (the TD-308 query budget): the money module's
    own ``pathway_engine.offer_reporting_date_unknown`` and ``wanted`` above, under one
    ``document_snapshot`` (joined when one is already open). Pure reads; the block closes before
    Check 2 writes anything."""
    from .document_snapshot import snapshot_unless_open
    from .pathway_engine import offer_reporting_date_unknown
    with snapshot_unless_open(application):
        return offer_reporting_date_unknown(application), wanted(application)
