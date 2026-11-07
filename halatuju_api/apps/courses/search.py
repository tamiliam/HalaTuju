"""Shared people-search for the admin list endpoints (B40 applicants + Students directory).

One place so the two lists can't drift. Matches a free-text ``q`` across name / NRIC /
phone / email, with two robustness rules learned from real data:

* **Phone & NRIC are matched digits-only on both sides.** They're stored with separators
  ("016-243 9706", "710829-02-5709") but officers type plain digits — a raw substring match
  misses ~76% of phones. We strip the real separators from the stored value with a cross-DB
  ``Replace`` chain (no Postgres-only ``regexp_replace`` — the test DB is SQLite).
* **Email can live in more than one column.** Most applicants have an email only in the
  application's ``notify_email`` (captured at apply), not the profile's ``contact_email`` —
  so callers pass ``extra_email`` to cover the second home.

**The term travels in a header, not the URL (TD-421, A1.9).** An officer searching by IC types the
student's full NRIC; in a query string it lands in Cloud Run's request log, which records the URL
and not custom headers. ``people_search_term`` reads ``X-Search-Term`` (URI-encoded by the web, so a
Tamil name survives the header's Latin-1 rule) and falls back to the old query parameter, so an
older web build keeps working until it is replaced.
"""
import re
from urllib.parse import unquote

from django.db.models import F, Q, Value
from django.db.models.functions import Replace

# The separators that actually appear in our stored phone/NRIC values.
_SEPARATORS = (' ', '-', '+', '(', ')', '.')

SEARCH_HEADER = 'X-Search-Term'


def people_search_term(request, param='q'):
    """The people-search text: the ``X-Search-Term`` header when sent, else ``?<param>=``."""
    raw = request.headers.get(SEARCH_HEADER)
    if raw is not None:
        return unquote(raw)
    return request.GET.get(param, '')


def _digits_expr(col):
    """ORM expression that strips separators from a column → digits only (cross-DB)."""
    expr = F(col)
    for ch in _SEPARATORS:
        expr = Replace(expr, Value(ch), Value(''))
    return expr


def apply_people_search(qs, q, *, name, nric, phone, email, extra_email=None,
                        needs_distinct=False):
    """Filter ``qs`` by ``q`` across the given ORM field paths. No-op for a blank ``q``.

    ``name``/``nric``/``phone``/``email`` (and optional ``extra_email``) are lookup paths
    relative to ``qs``. Set ``needs_distinct=True`` when ``extra_email`` crosses a to-many
    join (e.g. a profile's reverse ``scholarship_applications``) so rows aren't duplicated.
    """
    q = (q or '').strip()
    if not q:
        return qs
    cond = (Q(**{f'{name}__icontains': q}) | Q(**{f'{nric}__icontains': q})
            | Q(**{f'{email}__icontains': q}))
    if extra_email:
        cond |= Q(**{f'{extra_email}__icontains': q})
    q_digits = re.sub(r'\D', '', q)
    if q_digits:
        qs = qs.annotate(_phone_digits=_digits_expr(phone), _nric_digits=_digits_expr(nric))
        cond |= Q(_phone_digits__icontains=q_digits) | Q(_nric_digits__icontains=q_digits)
    qs = qs.filter(cond)
    return qs.distinct() if needs_distinct else qs
