"""Contract module: the schedule and quiz readers over a given template.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from .. import award


# ─────────────────────────────────────────────────────────────────────────────
# Readers. WHICH template governs an application lives in `contract_scope.py` since
# TD-229 (2026-10-03) — per GIFT, never per organisation. These read a template given.
# ─────────────────────────────────────────────────────────────────────────────
def schedule_row_for(template, application):
    """The schedule row for this application's pathway: pathway + 'continuing'
    (via award._stpm_continuing), falling back to variant='' then ('default','').
    A degree-bound student under a stale 'stpm' code takes the 'university' row, but only while
    her stored award is empty or the default RM2,000 (`pick_schedule_row`)."""
    if template is None:
        return None
    return pick_schedule_row(template.schedule_rows.all(), application)


def pick_schedule_row(rows, application):
    """The one row-choosing rule, shared with the no-template default (`default_schedule.py`).

    A degree-bound student under a stale 'stpm' code (`award._sized_as_stpm` false) is paid on the
    'university' row, as her RM2,000 award is (decision 7, #251). Guard (review, 2026-11-07): the
    row is picked live but a stored award never resizes, so the remap applies only while
    ``award_amount`` is empty or the default RM2,000. A student already holding the STPM RM3,000 /
    continuing RM1,000 keeps the STPM row, so the payments add up to her award and agreement."""
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    if (pathway == 'stpm' and not award._sized_as_stpm(application)
            and getattr(application, 'award_amount', None) in (None, award._DEFAULT_AMOUNT)):
        pathway = 'university'      # degree-bound under a stale code: paid as its RM2,000 (decision 7)
    variant = 'continuing' if award._stpm_continuing(application) else ''
    by_key = {(r.pathway, r.variant): r for r in rows}
    for key in [(pathway, variant), (pathway, ''), ('default', '')]:
        if key in by_key:
            return by_key[key]
    return None


def is_paid_month(row, cohort_year, month, year=None):
    """Whether a calendar (year, month) is a paid month under ``row``. ``year``
    defaults to ``cohort_year`` (the common in-cohort-year call); the STPM
    schedule spans two calendar years, so a second-year month passes ``year``."""
    if row is None:
        return False
    if year is None:
        year = cohort_year
    offset = (year - cohort_year) * 12 + (month - row.start_month)
    return offset in set(row.paid_offsets or [])


_MONTHS = ('', 'January', 'February', 'March', 'April', 'May', 'June',
           'July', 'August', 'September', 'October', 'November', 'December')


def _row_label(row, locale):
    return getattr(row, f'label_{locale}', '') or row.label_en or row.pathway


def schedule_summary_text(row, locale='en'):
    """A one-line plain-text summary of a row (fills BursaryAgreement.payment_schedule)."""
    if row is None:
        return ''
    count = len(row.paid_offsets or [])
    start = _MONTHS[row.start_month] if 1 <= row.start_month <= 12 else ''
    amount = f'RM{int(row.monthly_amount)}' if row.monthly_amount == row.monthly_amount.to_integral() \
        else f'RM{row.monthly_amount}'
    start_phrase = f', starting {start}' if start else ''
    return f'{amount} per month × {count} payments{start_phrase} (total RM{int(row.total)}).'


def schedule_table(template, locale='en'):
    """Structured rows for rendering Schedule 1 (start, count, total, offsets)."""
    if template is None:
        return []
    table = []
    for row in template.schedule_rows.all():
        table.append({
            'pathway': row.pathway,
            'variant': row.variant,
            'label': _row_label(row, locale),
            'monthly_amount': row.monthly_amount,
            'start_month': row.start_month,
            'months': len(row.paid_offsets or []),
            'paid_offsets': list(row.paid_offsets or []),
            'total': row.total,
        })
    return table


def schedule_calendar(row, cohort_year, locale='en'):
    """Month-by-month rows for Schedule 1: every month from the first paid month
    through the last, each flagged paid (with amount) or a gap ('exam month — no
    payment'). Drives the rendered contract's payment table."""
    if row is None or not row.paid_offsets or not cohort_year:
        return []
    offsets = sorted(int(o) for o in row.paid_offsets)
    paid = set(offsets)
    calendar = []
    for off in range(0, offsets[-1] + 1):
        total = (row.start_month - 1) + off
        year = cohort_year + total // 12
        month = total % 12 + 1
        calendar.append({
            'label': f'{_MONTHS[month]} {year}',
            'paid': off in paid,
            'amount': row.monthly_amount if off in paid else None,
        })
    return calendar


def quiz_checkpoints(template, locale='en'):
    """The comprehension checkpoints for the candidate clauses, in order, with a
    per-clause English fallback when the requested locale isn't translated."""
    if template is None:
        return []
    checkpoints = []
    for clause in template.clauses.all().order_by('order'):
        if not clause.is_quiz_candidate:
            continue
        payload = getattr(clause, f'quiz_{locale}', None) or clause.quiz_en
        if payload:
            checkpoints.append(payload)
    return checkpoints


def resolve_locale(locale, template):
    """Clamp a requested locale to one the template actually offers (else 'en')."""
    if template is None:
        return 'en'
    return locale if locale in template.languages_available else 'en'
