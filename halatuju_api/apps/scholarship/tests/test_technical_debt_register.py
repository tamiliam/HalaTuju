"""No two tickets may claim the same TD number.

⚠ THE DEFECT THIS EXISTS FOR (2026-09-08). Two agents working the same repo raised a ticket within
hours of each other, both took the next free number by reading the register, and both got **233** —
one for an interview slot overlapping a reviewer's own proposals, one for thirteen repair commands
with no route to production. Neither could see the other: ids are allocated by reading a file, and
the file each read was correct when they read it. The clash only surfaced at a push, and only
because the merge happened to be a fast-forward refusal rather than a clean auto-merge — with a
different edit order it would have merged silently and the register would carry two TD-233s for
ever, each cross-referenced from different code.

⚠ HEADINGS ONLY, AND THE CURATED INDEX EXCLUDED. The register has two eras: `### [TD-NNN]`
headings (the 2026-03 audit and TD-144 onward) and a bullet log (TD-053–143). **Only headings are
scanned.** In the bullet era a `- **TD-NNN**` line is used for a definition, a resolution, a
pointer AND a side-by-side comparison inside somebody else's entry — four jobs, one shape, so it
cannot be read mechanically. It is also closed history: every new ticket is a heading, and the
collision this guard exists for was two headings. The Open Items Index writes its pointers in that
same bullet form, so it is cut out too.

⚠ **I wrote the first version of this scan without heeding the register's own counting note, which
says both of those things in as many words. It failed on 19 false duplicates, my own two among
them.** Read that note before touching this.

This does not reserve numbers, and cannot: nothing here can stop two people picking the same one.
It makes the collision LOUD at the first test run after a merge, which is early enough to renumber
before anything cites it.
"""
import os
import re

from django.test import SimpleTestCase

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, *([os.pardir] * 4)))
_REGISTER = os.path.join(_REPO_ROOT, 'docs', 'technical-debt.md')

# A DEFINING line: a heading naming a ticket. See the docstring for why bullets are not scanned.
_DEFINING = re.compile(r'^#{2,4}\s.*?\[TD-(\d+)')

# A heading may deliberately continue an entry rather than define a new one.
_CONTINUATION = 'superseded detail'

# ⚠ COLLISIONS ALREADY IN THE REGISTER, both from 2026-07-03 and neither noticed until this guard
# was written. They are NOT renumbered: each has been cited from retros, commits and the index for
# two months, and rewriting history to satisfy a new test is how a citation quietly starts pointing
# at the wrong ticket. They are declared instead, so the register's state is visible and the guard
# still fires on a NEW clash.
#   TD-151 — "document-extraction robustness" (open, promoted at the 2026-08-19 review)
#            vs "booked interviews kept phantom holds" (resolved 2026-07-03)
#   TD-152 — "bursary agreement is a named-personal-donor contract" (accepted interim)
#            vs "student had no channel to the reviewer inside the 12h cutoff" (resolved 2026-07-03)
# ⚠ When citing either number, say WHICH — the index means the first of each pair.
KNOWN_COLLISIONS = {151, 152}


def _body_lines():
    """The register with the curated Open Items Index cut out — from its heading to the next `##`.

    The index is a list of POINTERS written in the same bullet form as a bullet-era definition, so
    leaving it in makes every listed ticket a duplicate of itself.
    """
    lines = open(_REGISTER, encoding='utf-8').read().split('\n')
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith('## Open Items Index'))
    except StopIteration:
        return lines                      # index renamed or gone — scan everything, loudly correct
    end = next((i for i, l in enumerate(lines[start + 1:], start + 1) if l.startswith('## ')),
               len(lines))
    return lines[:start] + lines[end:]


def _defined_ids():
    """Every TD id with a defining entry, in file order — duplicates KEPT, they are the point."""
    ids = []
    for line in _body_lines():
        m = _DEFINING.match(line)
        if m and _CONTINUATION not in line.lower():
            ids.append(int(m.group(1)))
    return ids


class TestTechnicalDebtRegister(SimpleTestCase):
    def test_no_td_number_is_defined_twice(self):
        seen, dupes = set(), []
        for n in _defined_ids():
            (dupes.append(n) if n in seen else seen.add(n))
        new = sorted(set(dupes) - KNOWN_COLLISIONS)
        self.assertEqual(new, [], (
            f'Two entries define the same TD number: {new}. Two people picked it from the same '
            'register at the same time. Renumber the one that was pushed SECOND — including every '
            'cross-reference in code, docs and the curated index — and leave the first alone.'))

    def test_the_known_collisions_are_still_there(self):
        """A declared collision that has quietly gone means somebody renumbered history — which is
        what this list exists to prevent — or the scan stopped seeing it. Either way, look."""
        dupes = {n for n in _defined_ids() if _defined_ids().count(n) > 1}
        self.assertEqual(sorted(KNOWN_COLLISIONS - dupes), [], (
            'A declared collision is no longer in the register. If it was renumbered, every '
            'existing citation of that number now points somewhere else — check before removing '
            'it from KNOWN_COLLISIONS.'))

    def test_the_scan_actually_reads_the_register(self):
        """The floor. If the path or the format moved, the assertion above would pass over an empty
        list for ever — a guard that protects nothing while looking green."""
        ids = _defined_ids()
        self.assertGreater(len(ids), 100, f'only {len(ids)} defining entries found — check the path')
        self.assertIn(1, ids)     # TD-001, the original audit's first entry
        self.assertIn(234, ids)   # the entry this guard was written alongside
