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
the reason is the check. A3.10 audited the thirteen seeded entries (TD-234, closed) and emptied it.
"""
import os

from django.test import SimpleTestCase

from apps.scholarship.views import CronRunView

_APPS = ('scholarship', 'courses')
_HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

# A3.10 (TD-234 closed): the ledger of door-less commands is EMPTY. Every command below is reachable
# through a DOCUMENTED route rather than a CronRunView.JOBS entry: the release-decisions Cloud Run job
# with an args override (CLAUDE.md, How a change reaches production, item 12). That job runs the
# service image against the live database, so no production credentials ever sit on a laptop (the
# practice TD-206 retired). Each reason says what the command is and why it needs no registered job.
#
# Retired in A3.10 (deleted, kept in git history): `backfill_nric_locks` (IC-lock repair, applied
# before the 2026-07-29 push) and `repair_interview_credit` (TD-216, 25 interviews re-credited
# 2026-08-18). Their tests went with them.
NO_DOOR = {}

# Documented-route commands: name -> why the release-decisions job route is enough.
DOCUMENTED_ROUTE = {
    'backfill_admin_seen': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_higher_results_kind': ('Matric/Diploma M1 (2026-10-29) — hand-run through the release-decisions '
                                     'job args override (CLAUDE.md, How a change reaches production, item 12): '
                                     'report, then --apply. Lead-gated.'),
    'backfill_institution': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_invitations': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_offer_pathways': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_pismp_tags': 'catalogue-row tool; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_pre_u_track': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_referral_attribution': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_reminder_anchors': 'launch one-off, spent; a repeat is a no-op. Route: the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_results_exam_type': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_spm_field_key': 'catalogue-row tool; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_stpm_cgpa': ('STPM CGPA C2 (2026-10-28) — hand-run through the release-decisions job args '
                           'override (CLAUDE.md, How a change reaches production, item 12): preview, '
                           '--apply --koko-only before the deploy, --apply after. Owner-gated.'),
    'repair_chosen_programme': 'one-off; reach it through the release-decisions job args override (CLAUDE.md, How a change reaches production, item 12).',
    'backfill_staff_activity': ('Common profile S4 (2026-10-31) — run ONCE at the S5 deploy point through '
                                'the release-decisions job args override (CLAUDE.md, How a change '
                                'reaches production, item 12): --dry-run, then --apply, AFTER the API '
                                'deploy. Idempotent; lead-gated.'),
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


def _registered_commands():
    """The command NAMES in the registry. A job is a name, or a ``(name, args)`` pair when
    the cron behaviour needs flags (added 2026-09-10 for `spending-ingest`) — this guard asks
    which commands are REACHABLE, so it wants the name either way. Without the unwrap a
    future `repair_*` command registered with flags would read as stranded, which is the
    opposite of what this file is for."""
    return {e[0] if isinstance(e, tuple) else e for e in CronRunView.JOBS.values()}


class TestEveryRepairHasADoor(SimpleTestCase):
    def test_every_repair_command_is_reachable_or_declared(self):
        registered = _registered_commands()
        stranded = sorted(c for c in _repair_commands()
                          if c not in registered and c not in NO_DOOR
                          and c not in DOCUMENTED_ROUTE)
        self.assertEqual(stranded, [], (
            'These repair commands can never run against production: they are not in '
            'CronRunView.JOBS and not declared in NO_DOOR. Register the job (and gate any write '
            'behind an env var — the endpoint passes no arguments), or add the name to NO_DOOR '
            'with the reason it needs no door: ' + ', '.join(stranded)))

    def test_the_ledger_names_only_real_commands(self):
        """A stale NO_DOOR entry is worse than none — it reads as a decision about something that
        no longer exists, and it hides the day a name is reused."""
        ghosts = sorted((set(NO_DOOR) | set(DOCUMENTED_ROUTE)) - _repair_commands())
        self.assertEqual(ghosts, [], f'NO_DOOR names commands that do not exist: {ghosts}')

    def test_a_declared_command_is_not_also_registered(self):
        """The two lists answer the same question and must not both claim a command — a name in
        both says one of them was not read."""
        both = sorted((set(NO_DOOR) | set(DOCUMENTED_ROUTE)) & _registered_commands())
        self.assertEqual(both, [], f'Both registered and declared door-less: {both}')

    def test_no_command_is_declared_door_less(self):
        """A3.10 closed TD-234: the door-less ledger stays empty. A command either has a registered
        job or a DOCUMENTED_ROUTE reason."""
        self.assertEqual(NO_DOOR, {})

    def test_the_scan_actually_finds_the_commands(self):
        """The floor. A path change that silently returned nothing would make every assertion above
        vacuous, and the guard would pass for ever while protecting nothing."""
        found = _repair_commands()
        self.assertGreaterEqual(len(found), 14, f'scan found only {len(found)} repair commands')
        self.assertIn('backfill_untagged_income_docs', found)     # the one that started this

    def test_the_command_that_started_this_has_its_door(self):
        self.assertEqual(CronRunView.JOBS.get('backfill-untagged-income-docs'),
                         'backfill_untagged_income_docs')
