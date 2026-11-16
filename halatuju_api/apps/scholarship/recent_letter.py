"""H3b (2026-11-16, roadmap H3 Goal B) - an OLD offer or confirmation letter asks for a RECENT one.

When the live offer-slot letter (an offer letter or a confirmation-of-studies letter) was issued more
than the organisation's ``recent_letter_window_months`` ago (platform default 3), AND her course should
already have started, Check 2 raises ONE soft document request, ``CODE``: "please upload a recent
confirmation letter from your institution".

SOFT BY DESIGN (the plan: a request, no block). It is an ordinary Check-2 doc request
(``check2_queries.DOC_SPECS``): it never blocks submission, never fails a fact, never touches a
verdict, the pathway or the money, and - unlike every other open student task - it does NOT hold
reviewer assignment (``services.queries_sla`` leaves ``CODE`` out of the open-task hold, fix round 1).

NOT BEFORE THE COURSE STARTS. A letter read with a reporting date still to come (today or later), or a
reporting date that cannot be read to a day and might still be to come, means no ask: an offer letter
is naturally months old before she reports. Only a reporting date in the past (or, read only to its
year, a year before this one) lets the ask fire. A letter with NO reporting date at all (most
confirmation letters) keeps the plain rule: the letter is older than the window.

NO GUESSING. The letter's issue date is ``vision_fields['fields']['offer_date']``; a date this strict
reader cannot place exactly (no year, two years, an ambiguous order, no day) means NO ask.

NO LOOP. ANY recent letter on file closes it: an offer or a confirmation letter, any institution
(polytechnic, university, matriculation, Form 6, ...), live or kept out of the live slot by the
keep-better promotion, dated inside the window and not FAILED (``offer_fails``). A suspect or unscored
letter still counts - she has done what we asked; a person judges the letter itself. A failing live
letter is left to its own, stronger ask.
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
    from apps.courses import org_config
    return org_config.value(getattr(application, 'owning_organisation', None), WINDOW_KEY)


def _recent_letter_on_file(application, edge):
    """Any non-failing letter in the offer slot dated on/after ``edge``, in ANY version of the slot:
    an offer or a confirmation letter, from any institution."""
    from .pathway_engine import offer_fails
    # all-versions-read: a recent letter she sent in answer may be KEPT OUT of the live slot by the
    # keep-better promotion (an official offer outranks it); it still answers this ask, so look at all.
    for doc in application.documents.filter(doc_type='offer_letter'):
        when = letter_date(doc)
        if when is not None and when >= edge and not offer_fails(doc):
            return True
    return False


def wanted(application, today=None) -> bool:
    """Should Check 2 ask this student for a recent confirmation letter? Soft; see the module notes.
    Yes only when the live letter is readable, not failing, dated before the window's edge, its course
    should already have started, and no recent letter of any kind is on file."""
    from .document_snapshot import latest_doc
    from .pathway_engine import offer_fails
    live = latest_doc(application, 'offer_letter')
    if live is None or offer_fails(live):
        return False
    when = letter_date(live)
    if when is None:
        return False
    today = today or timezone.localdate()
    edge = cutoff(today, window_months(application))
    if when >= edge or not course_should_have_started(live, today):
        return False
    return not _recent_letter_on_file(application, edge)


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
