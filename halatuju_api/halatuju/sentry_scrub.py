"""Sentry event scrubbing (A1.9a follow-up F2).

The admin people-search term (an IC, a name) travels in the ``X-Search-Term`` request header so it
stays out of the URL. Sentry copies request headers into error events, so that header must be
scrubbed or the term would leave us through Sentry. Sentry's default scrubber (kept) already hides
Authorization, cookies and similar; this adds our header to its denylist.

Sentry also sends each stack frame's LOCAL VARIABLES (``include_local_variables`` is on by
default), and ``EventScrubber.scrub_frames`` matches them by name against the same denylist. So the
names that hold the term (or its digits) on its way through ``apps.courses.search`` and
``apps.scholarship.scholars.filter_rows`` are listed too. They are common names (``q``, ``text``):
a variable of that name is hidden in EVERY frame, which is accepted.
"""
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

EXTRA_DENYLIST = ['x-search-term']

# people_search_term: raw; apply_people_search: q, q_digits, cond (a Q whose repr holds q);
# scholars.filter_rows: search, text, digits, cond.
SEARCH_TERM_LOCALS = ['raw', 'q', 'q_digits', 'cond', 'search', 'text', 'digits']


def build_event_scrubber():
    return EventScrubber(denylist=list(DEFAULT_DENYLIST) + EXTRA_DENYLIST + SEARCH_TERM_LOCALS)
