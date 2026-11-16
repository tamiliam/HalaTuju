"""H3b (2026-11-16, roadmap H3 Goal B) - an OLD offer or confirmation letter asks for a RECENT one.

When the live offer-slot letter (an offer letter or a confirmation-of-studies letter) was issued more
than the organisation's ``recent_letter_window_months`` ago (platform default 3), Check 2 raises ONE
soft document request, ``CODE``: "please upload a recent confirmation letter from your institution".

SOFT BY DESIGN. It is an ordinary Check-2 doc request (``check2_queries.DOC_SPECS``): it never blocks
submission, never fails a fact, never touches a verdict, the pathway or the money. Like every open
student task it counts toward the assignment floor (``queries_sla.is_ready_for_assignment``) only until
the organisation's answer window lapses - the same as the stale-payslip ask (``income_doc_stale``).

NO GUESSING. The letter's issue date is ``vision_fields['fields']['offer_date']``; a date this strict
reader cannot place exactly (no year, two years, an ambiguous order, no day) means NO ask.

NO LOOP. A recent confirmation letter already on file - live, or kept out of the live slot by the
keep-better promotion (an official offer can outrank it) - means no ask: she has done what we asked.
A failing letter (``offer_fails``) is left to its own, stronger ask.
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


def _month(word):
    from .pathway_engine import _RD_MONTHS
    return {**_RD_MONTHS, 'january': 1}.get(word)


def letter_date(doc):
    """The letter's issue date as a ``date``, or None when it cannot be read EXACTLY. The whole value
    must be one date: D/M/YYYY (``/ . -``), YYYY-MM-DD, "D Month YYYY" or "Month D, YYYY" (Malay or
    English month names). Anything else - a two-digit year, a stray word, an impossible day - is None."""
    vf = getattr(doc, 'vision_fields', None)
    fields = vf.get('fields') if isinstance(vf, dict) else None
    raw = fields.get('offer_date') if isinstance(fields, dict) else None
    if not isinstance(raw, str):
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


def cutoff(today, months):
    """``today`` minus ``months`` calendar months, the day clamped to that month's end. A letter dated
    ON the cutoff is still recent; one day earlier is old."""
    year, month0 = divmod(today.year * 12 + today.month - 1 - int(months), 12)
    return _dt.date(year, month0 + 1, min(today.day, calendar.monthrange(year, month0 + 1)[1]))


def window_months(application):
    from apps.courses import org_config
    return org_config.value(getattr(application, 'owning_organisation', None), WINDOW_KEY)


def _recent_confirmation_on_file(application, edge):
    """A non-failing confirmation letter dated on/after ``edge``, in ANY version of the offer slot."""
    from .pathway_engine import is_confirmation_letter, offer_fails
    # all-versions-read: a confirmation she sent in answer may be KEPT OUT of the live slot by the
    # keep-better promotion (an official offer outranks it); it still answers this ask, so look at all.
    for doc in application.documents.filter(doc_type='offer_letter'):
        when = letter_date(doc)
        if when is not None and when >= edge and is_confirmation_letter(doc) and not offer_fails(doc):
            return True
    return False


_UNREAD = object()


def reporting_date_unknown(offer) -> bool:
    """``pathway_engine.offer_reporting_date_unknown`` for an offer ALREADY READ, so the Check-2 pass
    reads the live offer once for both of its letter asks (the TD-308 query budget). Same body as the
    money module's function, which stays untouched; ``test_recent_letter`` pins the two equal."""
    from .pathway_engine import parse_reporting_date, student_offer_check
    if offer is None:
        return False
    vf = offer.vision_fields if isinstance(getattr(offer, 'vision_fields', None), dict) else {}
    sv = vf.get('student_verdict')
    if not sv or sv == 'review_manually':          # not extracted yet → not this gap
        return False
    return parse_reporting_date(student_offer_check(offer).get('reporting_date')) is None


def wanted(application, today=None, live=_UNREAD) -> bool:
    """Should Check 2 ask this student for a recent confirmation letter? Soft; see the module notes.
    ``live``: the live offer-slot letter when the caller has already read it (None = no letter)."""
    from .document_snapshot import latest_doc
    from .pathway_engine import offer_fails
    if live is _UNREAD:
        live = latest_doc(application, 'offer_letter')
    if live is None or offer_fails(live):
        return False
    when = letter_date(live)
    if when is None:
        return False
    edge = cutoff(today or timezone.localdate(), window_months(application))
    if when >= edge:
        return False
    return not _recent_confirmation_on_file(application, edge)
