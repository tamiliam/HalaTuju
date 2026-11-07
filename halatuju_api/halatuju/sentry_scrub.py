"""Sentry event scrubbing (A1.9a follow-up F2).

The admin people-search term (an IC, a name) travels in the ``X-Search-Term`` request header so it
stays out of the URL. Sentry copies request headers into error events, so that header must be
scrubbed or the term would leave us through Sentry. Sentry's default scrubber (kept) already hides
Authorization, cookies and similar; this adds our header to its denylist.
"""
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

EXTRA_DENYLIST = ['x-search-term']


def build_event_scrubber():
    return EventScrubber(denylist=list(DEFAULT_DENYLIST) + EXTRA_DENYLIST)
