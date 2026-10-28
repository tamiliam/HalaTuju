"""ONE definition of "awarded" for a count (Consolidation Review 2026-10-28, from `a8ccea58`).

⚠ THE DEFECT. A gift's Programmes card read 66 awarded against the applicant list's 65: the card
counted any row with `awarded_at`, and an award that FALLS THROUGH (the sponsor withdrew, the
student declined, a lapse, a hold) keeps that stamp, goes back to the pool and may later be
rejected or closed. The card and the list each derived "awarded" for themselves, and they
disagreed. The fix made `closure.ever_awarded_q` the one answer and pointed the card and the
Overview's awards-per-month chart at it.

That fix is a convention unless something stops the next count from deriving its own: the shape
is easy to rewrite (`Q(awarded_at__isnull=False)` reads like the obvious answer, and a decision
of 2026-09-08 once said it was). This guard is the "made loud" half (`small-change-lane.md` Part
A: a fix that depends on every future caller remembering is a convention, not a fix).

What it holds, both halves (H19 rule 1: pair every negative with a positive):
  * NEGATIVE — no api source outside `closure.py` filters on `awarded_at__isnull`. "Has this
    student been awarded?" is `ever_awarded_q()`. A filter on WHEN (`awarded_at__gte`, the pool's
    funded-grace window) is a different question and is not matched.
  * POSITIVE — the two counts the defect was found in still read `ever_awarded_q`, so the negative
    cannot go green because the counts were deleted or renamed away.
"""
import re

from django.test import SimpleTestCase

from .source_walk import API_ROOT, floor_count, read_source, walk_sources

_APPS = API_ROOT / 'apps'
_WHY = ('"has been awarded" has ONE definition, closure.ever_awarded_q; a count that derives its '
        'own from awarded_at counts an award that fell through (a8ccea58, 66 vs 65)')
_AWARDED_AT_NULL = re.compile(r'\bawarded_at__isnull\b')
_HOME = 'apps/scholarship/closure.py'


def _source_files():
    return [p for p in walk_sources(_APPS, '*.py', floor=400, why=_WHY)
            if 'tests' not in p.parts]


class TestAwardedHasOneDefinition(SimpleTestCase):
    def test_no_count_derives_awarded_from_the_stamp(self):
        files = floor_count(_source_files(), 300, 'non-test api source files', _WHY)
        offenders = []
        for path in files:
            rel = path.relative_to(API_ROOT).as_posix()
            if rel == _HOME:
                continue
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if _AWARDED_AT_NULL.search(line):
                    offenders.append(f'{rel}:{n}: {line.strip()}')
        self.assertEqual(offenders, [], (
            'A filter on awarded_at__isnull decides "was this student awarded?" for itself. An '
            'award that fell through keeps its awarded_at, so this counts it. Use '
            'closure.ever_awarded_q() instead (and if the question is genuinely different, say '
            'why in decisions.md and narrow this guard beside the reason).'))

    def test_the_two_counts_still_read_the_one_definition(self):
        closure = read_source(_APPS / 'scholarship' / 'closure.py', _WHY)
        self.assertIn('def ever_awarded_q(', closure)
        for rel in ('scholarship/views_admin/gifts.py', 'scholarship/programme_overview.py'):
            text = read_source(_APPS / rel, _WHY)
            self.assertGreaterEqual(
                len(re.findall(r'\bever_awarded_q\(\)', text)), 1,
                f'{rel} no longer calls ever_awarded_q() — follow the count that moved and point '
                'this guard at it; never delete the assertion.')
