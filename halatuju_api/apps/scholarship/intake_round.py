"""Where an intake round is in its life - the one reader of that fact.

Moved verbatim from `views_admin/gifts.py` (audit A3.11, RD-05): the programme overview service
(`programme_overview`) imported it sideways from the view layer. `views_admin` still re-exports it,
so every existing importer is unchanged.
"""


def round_state(c):
    """Where an intake round is in its life: `draft` · `open` · `closed` · `finished`.

    ⚠ SERVED, NEVER DERIVED IN THE BROWSER — the same rule as the gift card's `lifecycle`. Two
    copies of this would eventually disagree, and the shape of that disagreement is a badge saying
    one thing beside a control doing another.

    ⚠⚠ THE FOUR STATES ARE THREE BEHAVIOURS, AND THE MIDDLE ONE IS LOAD-BEARING:
      · `open`     — anyone may start an application and submit it.
      · `closed`   — no NEW applications; **anyone already started may still finish**. That is not
                     an oversight, it is where the intake gate sits (`ApplicationCreateView`), and
                     production relied on it: the 2026 round's switch went off on 1 July and THIRTY
                     students who were already part-way through submitted between then and 7 July.
      · `finished` — the grace period is over. A late submission is refused. **TERMINAL.**
      · `draft`    — never opened and nobody has applied. A round on its first day.

    `draft` vs `closed` is a display distinction only (both refuse new applications); it exists so a
    round being set up does not read as one that has run and stopped, which is the same confusion
    "inactive" caused on the gift card.
    """
    from .models import ScholarshipApplication
    if c.finished_at:
        return 'finished'
    if c.is_open:
        return 'open'
    # org-fence: `c` was reached through `_programmes_for` / `_cohort_or_404`, so it is already
    # inside the caller's organisation and this count cannot widen past it.
    if ScholarshipApplication.objects.filter(cohort=c).exists():
        return 'closed'
    return 'draft'
