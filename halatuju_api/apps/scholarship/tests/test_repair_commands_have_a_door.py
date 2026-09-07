"""Every repair has a way to reach the data it repairs.

⚠ THE DEFECT THIS EXISTS FOR (BrightPath #20, 2026-08-24 → 2026-09-08).
`backfill_untagged_income_docs` was written, tested, reviewed and shipped — and could not be run.
It writes to production, production is reachable only from the running service, and the only route
a management command has to the service is `CronRunView.JOBS`, which it was never added to. So it
sat finished and unreachable for a fortnight, and from the outside that looks exactly like
finished: nothing was broken, no test failed, no alert fired. A door was simply missing.

The small-change lane already carries the rail this class needed a version of — *"the forward fix
is prompted by the bug report, the backward repair is the half that gets forgotten"* — and #20
obeyed it: the changelog named the five affected documents. It still failed, because stating the
repair is owed is not the same as the repair being runnable. **This is the mechanical half.**

⚠ IT SELF-APPLIES TO THE NEXT ONE. The scan is by NAME (`backfill_*` / `repair_*`, the convention
this project already follows in both apps), so a command written next month is covered with nobody
remembering to add it here. That is the whole point: a rule kept only in the heads of people not
yet on the project is not kept.

⚠ `NO_DOOR` IS A LEDGER, NOT AN EXEMPTION LIST. Adding a name to it is a decision to be read, and
the reason is the check. The thirteen seeded entries are honest about their state rather than
quietly blessed — see TD-233, which carries them.
"""
import os

from django.test import SimpleTestCase

from apps.scholarship.views import CronRunView

_APPS = ('scholarship', 'courses')
_HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

# Commands that write a one-off repair and have NO route to the live service. Each is here with the
# reason it is not a defect today; none is here because nobody looked.
#
# ⚠ The collective reason for the first thirteen: they predate this guard, and each ran (or was
# meant to run) from a local checkout with production `DB_*` exported onto the laptop — the
# practice TD-206 retired precisely because a manual mitigation fails on the day somebody forgets.
# They have NOT been audited one by one for remaining work; TD-233 carries that. The guard's job is
# that the FOURTEENTH cannot be added without somebody deciding.
NO_DOOR = {
    'backfill_admin_seen': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_institution': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_invitations': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_nric_locks': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_offer_pathways': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_pismp_tags': 'TD-233 — catalogue rows; predates the guard.',
    'backfill_pre_u_track': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_referral_attribution': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_reminder_anchors': 'TD-233 — launch one-off, spent; predates the guard.',
    'backfill_results_exam_type': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'backfill_spm_field_key': 'TD-233 — catalogue rows; predates the guard.',
    'repair_chosen_programme': 'TD-233 — predates the guard; ran locally with exported prod creds.',
    'repair_interview_credit': 'TD-233 — predates the guard; ran locally with exported prod creds.',
}


def _repair_commands():
    """Every `backfill_*` / `repair_*` management command, across both apps."""
    found = set()
    for app in _APPS:
        d = os.path.join(_API_ROOT, 'apps', app, 'management', 'commands')
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith('.py') or name.startswith('_'):
                continue
            stem = name[:-3]
            if stem.startswith('backfill_') or stem.startswith('repair_'):
                found.add(stem)
    return found


class TestEveryRepairHasADoor(SimpleTestCase):
    def test_every_repair_command_is_reachable_or_declared(self):
        registered = set(CronRunView.JOBS.values())
        stranded = sorted(c for c in _repair_commands()
                          if c not in registered and c not in NO_DOOR)
        self.assertEqual(stranded, [], (
            'These repair commands can never run against production: they are not in '
            'CronRunView.JOBS and not declared in NO_DOOR. Register the job (and gate any write '
            'behind an env var — the endpoint passes no arguments), or add the name to NO_DOOR '
            'with the reason it needs no door: ' + ', '.join(stranded)))

    def test_the_ledger_names_only_real_commands(self):
        """A stale NO_DOOR entry is worse than none — it reads as a decision about something that
        no longer exists, and it hides the day a name is reused."""
        ghosts = sorted(set(NO_DOOR) - _repair_commands())
        self.assertEqual(ghosts, [], f'NO_DOOR names commands that do not exist: {ghosts}')

    def test_a_declared_command_is_not_also_registered(self):
        """The two lists answer the same question and must not both claim a command — a name in
        both says one of them was not read."""
        both = sorted(set(NO_DOOR) & set(CronRunView.JOBS.values()))
        self.assertEqual(both, [], f'Both registered and declared door-less: {both}')

    def test_the_scan_actually_finds_the_commands(self):
        """The floor. A path change that silently returned nothing would make every assertion above
        vacuous, and the guard would pass for ever while protecting nothing."""
        found = _repair_commands()
        self.assertGreaterEqual(len(found), 15, f'scan found only {len(found)} repair commands')
        self.assertIn('backfill_untagged_income_docs', found)     # the one that started this

    def test_the_command_that_started_this_has_its_door(self):
        self.assertEqual(CronRunView.JOBS.get('backfill-untagged-income-docs'),
                         'backfill_untagged_income_docs')
