"""The student's open Action Centre items, counted ONE way, for the query-raised email and the
reminder (Sprint SUP1, 2026-11-14).

Before this the two disagreed: the reminder counted only the open Check-2 clarify items
(`queries_sla.query_sla()['open_count']`), the raised email counted clarify + pathway confirm +
the missing-document requests + the reviewer's items. A student could be told "2 items" by one and
"5" by the other, and the Action Centre showed a third list. Both now call `open_items_for_email`,
and recount JUST BEFORE sending, so a student is never mailed about something she has since done.

What counts (open ones only; a resolved or waived item never does):
  - every Check-2 item (`source='check2'`: clarify, pathway confirm, promoted document asks);
  - a system document request she can act on (`STUDENT_DOC_REQUEST_CODES`);
  - a reviewer-raised item.
A `human` item (reviewer-only) never counts: it is hidden from her.

Each is named by its student-facing TITLE only, never a description or any document content.
A private item (a parent's death or status, guardianship, income, STR, a sibling's funding) and
every reviewer-typed item read as the plain `TEAM_QUESTION` title: an email can be read by
someone else in the family. The full title stays in the Action Centre, behind the sign-in.
"""
from .query_item_titles import GENERIC, PLACEHOLDER_FREE, SENSITIVE_CODES, TEAM_QUESTION, TITLES

_LANG_INDEX = {'en': 0, 'ms': 1, 'ta': 2}


def open_student_items(application):
    """The open items the student is being asked for, oldest first (a list, not a queryset)."""
    from django.db.models import Q
    from ..resolution import STUDENT_DOC_REQUEST_CODES   # lazy: resolution imports services
    wanted = (Q(source='check2')
              | Q(source='system', code__in=STUDENT_DOC_REQUEST_CODES)
              | Q(source='officer'))
    return list(application.resolution_items
                .filter(wanted, status='open').exclude(kind='human').order_by('created_at', 'id'))


def item_title(item, lang='en'):
    """One item's student-facing title in `lang` (en / ms / ta; anything else reads English)."""
    idx = _LANG_INDEX.get(lang, 0)
    if item.source == 'officer' or item.code in SENSITIVE_CODES:
        # Never a reviewer's free text, never a private subject, in an email.
        return TEAM_QUESTION[idx]
    row = TITLES.get(item.code)
    if row is None:
        return GENERIC[idx]
    title = row[idx]
    if item.code in PLACEHOLDER_FREE or '{' not in title:
        return title
    # A title with a subject placeholder: fill it from the item's own params, or drop to generic.
    params = item.params or {}
    try:
        filled = title.format(**{k: (', '.join(map(str, v)) if isinstance(v, (list, tuple)) else v)
                                 for k, v in params.items()})
    except (KeyError, IndexError, ValueError):
        return GENERIC[idx]
    return filled


def open_items_for_email(application, lang='en'):
    """Recount NOW and return the titles, one per open item: `[]` means nothing is open and the
    caller must send nothing. `len()` of the result is THE count both emails state."""
    from ..emails.student_decisions import normalise_lang
    lang = normalise_lang(lang)
    return [item_title(i, lang) for i in open_student_items(application)]
