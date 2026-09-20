"""How old a proof is allowed to be, and which of several documents of one kind wins:
`stale_income_proof` and the de-duplication ranking.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import datetime
import re

from .salary_figures import _doc_fields, _parse_rm
from .utilities import _parse_billing_month, _reconciled_holder_name, _utility_name_unrelated


# ``declared_income_gaps`` — the Check-2 ask about a DECLARED informal wage — now lives in
# ``income_declared_gaps.py`` (TD-262 F2), where it gained the "already shown another way" arm
# that ends the dead-end chase. Its importers name that module directly: a re-export here would
# have been a second home for the name, and a suppression to keep the linter quiet about it.


# ── Stale income document (reviewer-query automation S2) ─────────────────────
# A salary slip is monthly; reviewers routinely ask "this slip is from December — do you
# have one from the last three months?". Deterministic: if a salary slip is on file but the
# MOST RECENT one is older than ~3 months, ask for a current one. (STR staleness is already
# handled by _str_currency → 'stale'; EPF statements are often annual, so this targets
# salary slips only — exactly the reviewer behaviour.)
_INCOME_DOC_CURRENT_MONTHS = 3


def _salary_period_age_months(f, today):
    """Months between *today* and a salary slip's pay period (from its OCR'd 'period'),
    or None when the period can't be read. Reuses the tolerant month-year parser."""
    ym = _parse_billing_month(f.get('period'))
    if not ym:
        return None
    year, month = ym
    return (today.year - year) * 12 + (today.month - month)


def stale_income_proof(application, today=None):
    """True when a salary slip is on file but NONE is current (every readable one is older
    than ~3 months) — the student should upload a recent slip. False when there is a current
    slip, no salary slip at all, or no slip period could be read (never guess from an
    unreadable date). Pure; tolerant of a test double without `.documents`."""
    if today is None:
        today = datetime.date.today()
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    slips = list(docs.filter(doc_type='salary_slip', superseded_at__isnull=True))
    if not slips:
        return False
    ages = []
    for s in slips:
        age = _salary_period_age_months(_doc_fields(s), today)
        if age is not None:
            ages.append(age)
    if not ages:                                   # no readable period → don't guess
        return False
    return min(ages) > _INCOME_DOC_CURRENT_MONTHS  # the freshest slip is still stale


# ── One-live-copy dedup for income proof (owner 2026-07-05) ──────────────────────────────
# The student re-uploads the same/older salary slip or STR screenshot repeatedly; each officer
# re-request lands it in its own slot, so several LIVE copies of one person's proof pile up in the
# cockpit. We only need ONE — the most recent. This collapses a person's copies to a single live
# doc (the newest) and supersedes the rest into the Old / Replaced history. Recency:
#   salary_slip → the pay period (newest month wins); str → the shown year; epf → the statement
#   date (newest wins). A copy whose date can't be read never outranks a dated one; a non-genuine
#   copy never outranks a genuine one; ties fall to the latest upload (id).
_DEDUP_DOC_TYPES = ('salary_slip', 'str', 'epf', 'water_bill', 'electricity_bill')
# Dedup scope: these types are HOUSEHOLD-level (one per household, carry no reliable member tag),
# so they collapse across ALL members; salary_slip / epf are per-member (each earner has their own).
_HOUSEHOLD_WIDE_DEDUP = ('str', 'water_bill', 'electricity_bill')


def _doc_genuine_rank(doc):
    """1 when the doc is NOT flagged non-genuine (genuine / never-scored), 0 when its genuineness is
    suspect / not_<type> / wrong-type / low-confidence. Dedup ranks this FIRST so a non-genuine copy
    (a SARA letter in the STR slot, an EPF filed as a payslip) can NEVER supersede a genuine one — we
    keep the real document even when a fake / wrong-type copy is newer."""
    vf = getattr(doc, 'vision_fields', None)
    st = ''
    if isinstance(vf, dict) and isinstance(vf.get('authenticity'), dict):
        st = (vf['authenticity'].get('status') or '').strip()
    return 1 if st in ('', 'genuine', 'likely_genuine') else 0


def _income_doc_recency(doc):
    """A sortable recency value for a de-dupable income-proof doc (higher = keep), or None when no
    date can be read. salary_slip → (year, month) pay period; str → (year, 0) of the shown year;
    epf → (year, month) of the statement date (year-only if that's all that reads); water/electricity
    bill → (year, month) of the billing period."""
    dt = getattr(doc, 'doc_type', '')
    f = _doc_fields(doc)
    if dt == 'salary_slip':
        return _parse_billing_month(f.get('period'))          # (y, m) or None
    if dt in ('water_bill', 'electricity_bill'):
        return _parse_billing_month(f.get('billing_period'))  # newest billing month wins
    if dt == 'epf':
        ym = _parse_billing_month(f.get('statement_date'))
        if ym:
            return ym
        m = re.search(r'(20\d{2})', str(f.get('year') or f.get('statement_date') or ''))
        return (int(m.group(1)), 0) if m else None
    if dt == 'str':
        m = re.search(r'(20\d{2})', str(f.get('year') or ''))
        return (int(m.group(1)), 0) if m else None
    return None


def _dedup_clean_rank(doc):
    """A quality gate used ONLY for utility bills in the dedup sort (owner 2026-07-08): a genuine,
    readable bill in a KNOWN holder's name (student / declared parent / roster) outranks a
    stranger-named or unreadable one — so a newer wrong-name / unreadable scan can never bury a
    clean, verified bill. Returns 1 for every NON-utility doc, so the salary / STR / EPF ordering is
    unchanged."""
    dt = getattr(doc, 'doc_type', '')
    if dt not in ('water_bill', 'electricity_bill'):
        return 1
    app = getattr(doc, 'application', None)
    f = _doc_fields(doc)
    name = (f.get('name', '') or '').strip()
    if app is not None and _utility_name_unrelated(app, _reconciled_holder_name(app, name)):
        return 0                                              # a stranger's bill — demote
    if not (f.get('address', '') or '').strip():
        return 0                                              # address unreadable
    if _parse_rm(f.get('amount')) is None:
        return 0                                              # amount unreadable
    return 1


def income_dedup_rank(doc):
    """Which live copy of an income proof KEEPS the slot — HIGHER wins. Pure; reads stored fields.

    ⚠ GENUINENESS LEADS, and that is the whole point: a non-genuine copy may never supersede a
    genuine one. It is deliberately a DIFFERENT order from ``promotion.doc_quality``, which leads
    with ``usable`` — and the difference is not academic. Application 73 holds a genuine payslip
    whose OCR misread one digit of the earner's IC (so it reads NOT usable) beside a WhatsApp photo
    scored ``not_salary`` that read no identity at all (so nothing contradicts, and it reads
    usable). By ``doc_quality`` the photo wins; by this rank the payslip does. At upload both run —
    promotion first, then ``dedupe_income_proof`` — so the de-dup is what makes the promote proxy
    safe for these types, and any OTHER caller settling an income slot must run this one too.
    """
    return (_doc_genuine_rank(doc), _dedup_clean_rank(doc),
            1 if _income_doc_recency(doc) else 0,
            _income_doc_recency(doc) or (0, 0), doc.id)


def dedupe_income_proof(application, member, doc_type):
    """Collapse LIVE copies of ``doc_type`` to a SINGLE best live doc, superseding the rest into
    Old / Replaced. Ranks by (genuine, has-a-date, recency, id): a genuine copy is never superseded
    by a non-genuine one, then the newest pay month / latest-dated STR wins, then the latest upload.
    Runs across request_codes (an officer re-request no longer leaves a parallel live copy). Retains
    the superseded rows + blobs — never a hard delete. Returns the superseded ids.

    Scope differs by type: salary_slip / epf are PER-MEMBER (each earner has their own), so they
    dedup within ``member``. STR + utility bills are HOUSEHOLD-level (``_HOUSEHOLD_WIDE_DEDUP``) —
    STR pays ONE recipient per household, and utility bills / STR screenshots are re-uploaded under
    an inconsistent (often blank) member tag — so they collapse across ALL members of the
    application, ignoring the passed ``member``. Utility bills additionally rank a clean, readable,
    known-holder bill above a stranger-named / unreadable one (``_dedup_clean_rank``) so a newer bad
    scan never buries a verified bill (owner 2026-07-08)."""
    if doc_type not in _DEDUP_DOC_TYPES:
        return []
    docs = getattr(application, 'documents', None)
    if docs is None:
        return []
    q = docs.filter(doc_type=doc_type, superseded_at__isnull=True)
    if doc_type not in _HOUSEHOLD_WIDE_DEDUP:   # salary/epf: per-member; STR + utility: household-wide
        q = q.filter(household_member=member)
    live = list(q)
    if len(live) < 2:
        return []
    live.sort(key=income_dedup_rank, reverse=True)
    keep, losers = live[0], live[1:]
    # Preserve recipient attribution: if the kept STR copy is blank-tagged but a superseded sibling
    # names the recipient, inherit it so the cockpit still shows e.g. "Mother's STR proof".
    if doc_type == 'str' and not (getattr(keep, 'household_member', '') or '').strip():
        for d in losers:
            m = (getattr(d, 'household_member', '') or '').strip()
            if m:
                keep.household_member = m
                keep.save(update_fields=['household_member'])
                break
    ids = [d.id for d in losers]
    from django.utils import timezone as _tz
    docs.filter(id__in=ids).update(superseded_at=_tz.now(), superseded_by=keep)
    return ids
