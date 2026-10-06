"""org-timing Sprint 1 — the student-message timings became organisation settings.

Roadmap: `docs/plans/2026-10-07-org-timing-settings-roadmap.md`. What matters here, in order:

1. **The registry says exactly what the owner approved** — 13 new keys, their unit, default,
   min and max; the narrowed ranges of ten existing keys; every platform default inside its own
   range and the full default set passing every rule (so an env-var default can never ship a
   combination the tab would refuse).
2. **The rules bite.** One test per rule (R1–R7 and the interview window) that breaks it and one
   that keeps it. R1, R2, R4, R6 and R7 cannot be broken inside today's narrow ranges, so they
   are driven through `check_rules` with values placed OUTSIDE the ranges — the guard still has
   to say no when a range is widened one day.
3. **Every wired read site follows an organisation's STORED, non-default value**, and a
   tenant that stored nothing (or has no organisation at all) keeps the platform default.
"""
import io
from datetime import timedelta

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import org_config
from apps.courses.org_config_rules import RULES, check_rules
from apps.scholarship.models import ScholarshipApplication, Sponsor, Sponsorship
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_shortlistable_student, make_student,
)

from .test_org_config import _configure

NEW_KEYS = {
    # key: (group, unit, default, min, max) — the roadmap's table, owner 2026-10-07
    'shortlist_email_delay_minutes': ('decisions', 'minutes', 60, 30, 180),
    'not_shortlisted_email_delay_hours': ('decisions', 'hours', 48, 24, 48),
    'reminder_1_days': ('profile_completion', 'days', 2, 1, 3),
    'reminder_2_days': ('profile_completion', 'days', 9, 7, 14),
    'reminder_3_days': ('profile_completion', 'days', 23, 18, 30),
    'reminder_4_days': ('profile_completion', 'days', 53, 45, 60),
    'auto_close_after_final_reminder_days': ('profile_completion', 'days', 5, 3, 7),
    'query_answer_days': ('check2', 'days', 5, 3, 7),
    'query_reminder_lead_days': ('check2', 'days', 2, 1, 2),
    'decline_hold_days': ('decisions', 'days', 7, 3, 10),
    'qc_decline_hold_hours': ('decisions', 'hours', 24, 12, 48),
    'award_email_delay_hours': ('awards', 'hours', 24, 12, 48),
    'award_confirm_hold_days': ('awards', 'days', 2, 1, 3),
}

NARROWED = {
    'nudge_auto_delay_minutes': (15, 60), 'query_email_delay_hours': (1, 6),
    'interview_min_lead_hours': (12, 48), 'interview_reschedule_cutoff_hours': (6, 24),
    'sign_accept_deadline_days': (14, 45), 'review_sla_days': (7, 14),
    'review_nudge_soon_days': (1, 3), 'review_escalate_grace_days': (2, 7),
    'nudge_cooldown_hours': (12, 48), 'sign_reminder_days': (2, 7),
}

RULE_CODES = {'window_inverted', 'decline_before_shortlist', 'reminders_too_close',
              'reminder_outside_window', 'questions_after_reminder', 'cutoff_beyond_lead',
              'qc_hold_too_long', 'nudge_after_due'}


def _org_cohort(org):
    return make_cohort(owning_organisation=org)


def _close_to(test, actual, expected, seconds=120):
    test.assertAlmostEqual(actual.total_seconds(), expected.total_seconds(), delta=seconds)


# ─── 1. the registry ─────────────────────────────────────────────────────────

class TestTheRegistry(TestCase):
    def test_the_thirteen_new_keys_are_exactly_the_approved_table(self):
        for key, (group, unit, default, lo, hi) in NEW_KEYS.items():
            spec = org_config.SETTINGS[key]
            self.assertEqual((spec['group'], spec['unit'], spec['min'], spec['max']),
                             (group, unit, lo, hi), key)
            self.assertEqual(org_config.default(key), default, key)

    def test_the_existing_timings_narrowed_as_approved(self):
        for key, bounds in NARROWED.items():
            spec = org_config.SETTINGS[key]
            self.assertEqual((spec['min'], spec['max']), bounds, key)

    def test_every_platform_default_sits_inside_its_own_range_and_passes_every_rule(self):
        """⚠ THE GUARD. A default moved by an env var to a value the tab would refuse would put
        every organisation that never chose on a setting nobody could save."""
        defaults = {}
        for key, spec in org_config.SETTINGS.items():
            value = org_config.default(key)
            self.assertTrue(spec['min'] <= value <= spec['max'], f'{key}={value}')
            if spec.get('allowed') is not None:
                self.assertIn(value, spec['allowed'], key)
            defaults[key] = value
        check_rules(defaults)                     # raises on any broken rule
        self.assertGreaterEqual(len(defaults), 36)

    def test_the_rule_table_is_the_approved_set_and_names_real_keys(self):
        self.assertEqual({r.code for r in RULES}, RULE_CODES)
        for rule in RULES:
            self.assertIn(rule.blames, rule.keys, rule.code)
            for key in rule.keys:
                self.assertIn(key, org_config.SETTINGS, rule.code)

    @override_settings(DECLINE_COOLOFF_DAYS=4.0, DECLINE_QC_COOLOFF_HOURS=36.0,
                       AWARD_OFFER_EMAIL_COOLOFF_HOURS=30, AWARD_COOLOFF_DAYS=3.0)
    def test_the_hold_defaults_delegate_to_the_platform_settings_live(self):
        self.assertEqual(org_config.default('decline_hold_days'), 4)
        self.assertEqual(org_config.default('qc_decline_hold_hours'), 36)
        self.assertEqual(org_config.default('award_email_delay_hours'), 30)
        self.assertEqual(org_config.default('award_confirm_hold_days'), 3)
        self.assertIsInstance(org_config.default('decline_hold_days'), int)

    @override_settings(DECLINE_COOLOFF_DAYS=2.5)
    def test_a_fractional_platform_hold_is_refused_loudly_never_rounded(self):
        with self.assertRaises(ImproperlyConfigured):
            org_config.default('decline_hold_days')

    def test_the_ladder_defaults_read_the_one_platform_home(self):
        from apps.scholarship import services
        self.assertEqual(
            tuple(org_config.default(f'reminder_{n}_days') for n in (1, 2, 3, 4)),
            services.REMINDER_THRESHOLDS_DAYS)
        self.assertEqual(org_config.default('auto_close_after_final_reminder_days'),
                         services.FINAL_REMINDER_GRACE_DAYS)


# ─── 2. the rules ────────────────────────────────────────────────────────────

class TestTheRules(TestCase):
    def _refused(self, values, code, key, *, fence=True):
        with self.assertRaises(org_config.OrgConfigError) as caught:
            (org_config.validate_values if fence else check_rules)(values)
        self.assertEqual((caught.exception.code, caught.exception.key), (code, key))

    # Breakable inside the ranges — driven through the real storage fence.
    def test_window_inverted(self):
        self._refused({'interview_window_start_min': 18 * 60, 'interview_window_end_min': 9 * 60},
                      'window_inverted', 'interview_window_end_min')
        org_config.validate_values({'interview_window_start_min': 9 * 60,
                                    'interview_window_end_min': 18 * 60})

    def test_r3_questions_after_reminder_resolves_the_unstored_keys_from_the_defaults(self):
        # Answer 3 days with the default 2-day lead leaves 24 hours; the default 2-hour
        # questions email + a day does not fit. Only ONE key is stored — the rest are defaults.
        self._refused({'query_answer_days': 3}, 'questions_after_reminder',
                      'query_email_delay_hours')
        org_config.validate_values({'query_answer_days': 4})
        org_config.validate_values({'query_answer_days': 3, 'query_reminder_lead_days': 1})

    def test_r5_cutoff_beyond_lead(self):
        self._refused({'interview_reschedule_cutoff_hours': 24, 'interview_min_lead_hours': 12},
                      'cutoff_beyond_lead', 'interview_reschedule_cutoff_hours')
        org_config.validate_values({'interview_reschedule_cutoff_hours': 12,
                                    'interview_min_lead_hours': 12})

    # Unbreakable inside the ranges — the rule itself must still say no.
    def test_r1_decline_before_shortlist(self):
        self._refused({'shortlist_email_delay_minutes': 180, 'not_shortlisted_email_delay_hours': 2},
                      'decline_before_shortlist', 'not_shortlisted_email_delay_hours', fence=False)
        check_rules({'shortlist_email_delay_minutes': 180, 'not_shortlisted_email_delay_hours': 3})

    def test_r2_reminders_too_close_blames_the_later_rung(self):
        self._refused({'reminder_1_days': 2, 'reminder_2_days': 3}, 'reminders_too_close',
                      'reminder_2_days', fence=False)
        self._refused({'reminder_2_days': 20, 'reminder_3_days': 21}, 'reminders_too_close',
                      'reminder_3_days', fence=False)
        self._refused({'reminder_3_days': 50, 'reminder_4_days': 51}, 'reminders_too_close',
                      'reminder_4_days', fence=False)
        check_rules({'reminder_1_days': 2, 'reminder_2_days': 4, 'reminder_3_days': 6,
                     'reminder_4_days': 8})

    def test_r4_reminder_outside_window(self):
        self._refused({'query_reminder_lead_days': 5, 'query_answer_days': 5},
                      'reminder_outside_window', 'query_reminder_lead_days', fence=False)
        check_rules({'query_reminder_lead_days': 1, 'query_answer_days': 5})

    def test_r6_qc_hold_too_long(self):
        self._refused({'qc_decline_hold_hours': 73, 'decline_hold_days': 3},
                      'qc_hold_too_long', 'qc_decline_hold_hours', fence=False)
        check_rules({'qc_decline_hold_hours': 72, 'decline_hold_days': 3})

    def test_r7_nudge_after_due(self):
        self._refused({'review_nudge_soon_days': 7, 'review_sla_days': 7},
                      'nudge_after_due', 'review_nudge_soon_days', fence=False)
        check_rules({'review_nudge_soon_days': 6, 'review_sla_days': 7})

    def test_a_rule_none_of_whose_keys_is_stored_is_not_checked(self):
        # An organisation is never refused for a combination it did not choose.
        check_rules({'pool_funded_grace_days': 30})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheEndpointNamesTheRule(TestCase):
    URL = '/api/v1/admin/scholarship/organisation/configuration/'

    def test_a_rule_refusal_returns_its_code_its_key_and_says_it_is_a_rule(self):
        org = make_org()
        client = authed_client(make_admin('org_admin', owning_org=org))
        r = client.put(self.URL, {'values': {'query_answer_days': 3}}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual((r.json()['code'], r.json()['key'], r.json()['rule']),
                         ('questions_after_reminder', 'query_email_delay_hours', True))
        r = client.put(self.URL, {'values': {'query_answer_days': 9}}, format='json')
        self.assertEqual((r.json()['code'], r.json()['rule']), ('out_of_range', False))
        # …and the same pair, made to fit, saves.
        r = client.put(self.URL, {'values': {'query_answer_days': 3,
                                             'query_reminder_lead_days': 1}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)


# ─── 3. the read sites ───────────────────────────────────────────────────────

class TestTheDecisionDelay(TestCase):
    def test_score_application_uses_the_organisations_delays(self):
        from apps.scholarship.services import score_application
        org = make_org()
        _configure(org, 'shortlist_email_delay_minutes', 30)
        _configure(org, 'not_shortlisted_email_delay_hours', 24)
        cohort = _org_cohort(org)
        good = make_application('submitted', cohort=cohort, student=make_shortlistable_student())
        poor = make_application('submitted', cohort=cohort,
                                student=make_student(receives_str=True, grades={}))
        self.assertEqual(score_application(good).verdict, 'shortlisted')
        self.assertEqual(score_application(poor).verdict, 'rejected')
        good.refresh_from_db(); poor.refresh_from_db()
        _close_to(self, good.decision_due_at - good.submitted_at, timedelta(minutes=30), 5)
        _close_to(self, poor.decision_due_at - poor.submitted_at, timedelta(hours=24), 5)

    def test_a_tenant_that_chose_nothing_gets_the_platform_60_minutes(self):
        from apps.scholarship.services import rescore_pending_decisions
        configured = make_org()
        _configure(configured, 'shortlist_email_delay_minutes', 30)
        app = make_application('submitted', cohort=_org_cohort(make_org()),
                               student=make_shortlistable_student())
        rescore_pending_decisions()                     # the second road into score_application
        app.refresh_from_db()
        _close_to(self, app.decision_due_at - app.submitted_at, timedelta(minutes=60), 5)


class TestTheAnswerWindow(TestCase):
    """`query_answer_days` is the answer window AND the reviewer-assignment floor."""

    def _with_open_task(self, org, days_ago):
        from apps.scholarship.models import ResolutionItem
        app = make_application('profile_complete', cohort=_org_cohort(org),
                               profile_completed_at=timezone.now() - timedelta(days=days_ago))
        ResolutionItem.objects.create(application=app, code='ask', source='officer',
                                      kind='clarify', status='open')
        return app

    def test_the_deadline_and_the_assignment_floor_follow_the_organisation(self):
        from apps.scholarship.services import is_ready_for_assignment, query_sla
        quick = make_org()
        _configure(quick, 'query_answer_days', 4)
        _configure(quick, 'query_reminder_lead_days', 1)
        ours = self._with_open_task(quick, days_ago=4.5)
        theirs = self._with_open_task(make_org(), days_ago=4.5)
        self.assertTrue(is_ready_for_assignment(ours))      # 4.5 days > the org's 4
        self.assertFalse(is_ready_for_assignment(theirs))   # < the platform's 5
        # The officer task is not a clarify query, so the deadline is the SUBMIT clock.
        _close_to(self, query_sla(ours)['deadline'] - ours.profile_completed_at, timedelta(days=4))
        _close_to(self, query_sla(theirs)['deadline'] - theirs.profile_completed_at,
                  timedelta(days=5))

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_the_query_reminder_goes_the_organisations_lead_before_the_deadline(self):
        from apps.scholarship.models import ResolutionItem
        from apps.scholarship.services import send_query_reminders
        late = make_org()
        _configure(late, 'query_reminder_lead_days', 1)
        apps_ = []
        for org in (late, make_org()):
            app = make_application('profile_complete', cohort=_org_cohort(org))
            item = ResolutionItem.objects.create(application=app, code='q', source='check2',
                                                 kind='clarify', status='open')
            # Raised 3 days ago on a 5-day window: 2 days left.
            ResolutionItem.objects.filter(pk=item.pk).update(
                created_at=timezone.now() - timedelta(days=3))
            apps_.append(app)
        send_query_reminders()
        ours, theirs = (ScholarshipApplication.objects.get(pk=a.pk) for a in apps_)
        self.assertIsNone(ours.query_reminder_at)          # the org waits until 1 day is left
        self.assertIsNotNone(theirs.query_reminder_at)     # the platform's 2 days


class TestTheReminderLadder(TestCase):
    def _shortlisted(self, org, *, anchor_days, **kw):
        return make_application('shortlisted', cohort=_org_cohort(org),
                                reminder_anchor_at=timezone.now() - timedelta(days=anchor_days),
                                **kw)

    def test_the_sweep_and_its_dry_run_follow_the_organisations_ladder(self):
        from apps.scholarship.services import send_application_reminders
        slow = make_org()
        _configure(slow, 'reminder_1_days', 3)
        ours = self._shortlisted(slow, anchor_days=2)
        theirs = self._shortlisted(make_org(), anchor_days=2)
        # The dry run reports exactly what the live run then does.
        out = io.StringIO()
        call_command('send_application_reminders', '--dry-run', stdout=out)
        self.assertIn(f'would send R1 (day 2) to app #{theirs.pk}', out.getvalue())
        self.assertNotIn(f'app #{ours.pk}', out.getvalue())
        send_application_reminders()
        ours.refresh_from_db(); theirs.refresh_from_db()
        self.assertEqual(ours.reminder_stage, 0)           # the org's R1 is day 3
        self.assertEqual(theirs.reminder_stage, 1)         # the platform's R1 is day 2

    def test_the_auto_close_follows_the_organisations_grace(self):
        from apps.scholarship.services import send_application_reminders
        brisk = make_org()
        _configure(brisk, 'auto_close_after_final_reminder_days', 3)
        warned = timezone.now() - timedelta(days=4)
        ours = self._shortlisted(brisk, anchor_days=57, reminder_stage=4, last_reminder_at=warned)
        theirs = self._shortlisted(make_org(), anchor_days=57, reminder_stage=4,
                                   last_reminder_at=warned)
        out = io.StringIO()
        call_command('send_application_reminders', '--dry-run', stdout=out)
        self.assertIn(f'would CLOSE app #{ours.pk}', out.getvalue())
        self.assertNotIn(f'app #{theirs.pk}', out.getvalue())
        send_application_reminders()
        ours.refresh_from_db(); theirs.refresh_from_db()
        self.assertEqual(ours.status, 'expired')           # 4 days > the org's 3
        self.assertEqual(theirs.status, 'shortlisted')     # < the platform's 5

    def test_the_final_reminder_states_the_organisations_close(self):
        from apps.scholarship.services import send_application_reminders
        brisk = make_org()
        _configure(brisk, 'auto_close_after_final_reminder_days', 3)
        ours = self._shortlisted(brisk, anchor_days=53, reminder_stage=3)
        theirs = self._shortlisted(make_org(), anchor_days=53, reminder_stage=3)
        mail.outbox = []
        send_application_reminders()
        bodies = {m.to[0]: m.body for m in mail.outbox}
        self.assertIn('within 3 days', bodies[ours.notify_email])
        self.assertIn('within 5 days', bodies[theirs.notify_email])


class TestTheDeclineHolds(TestCase):
    def test_a_decline_is_held_for_the_organisations_days(self):
        from apps.scholarship.services import admin_reject
        quick = make_org()
        _configure(quick, 'decline_hold_days', 3)
        for org, days in ((quick, 3), (make_org(), 7)):
            app = make_application('shortlisted', cohort=_org_cohort(org))
            admin_reject(app, make_admin('org_admin', owning_org=org), 'interview')
            app.refresh_from_db()
            _close_to(self, app.decline_due_at - timezone.now(), timedelta(days=days))

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_a_qc_confirmed_decline_is_held_for_the_organisations_hours(self):
        quick = make_org()
        _configure(quick, 'qc_decline_hold_hours', 12)
        for org, hours in ((quick, 12), (make_org(), 24)):
            reviewer = make_admin('reviewer', owning_org=org)
            app = make_application('awaiting_qc', outcome='decline', cohort=_org_cohort(org),
                                   reviewer=reviewer)
            qc = authed_client(make_admin('qc', owning_org=org))
            r = qc.post(f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
                        {'decision': 'accept'}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
            app.refresh_from_db()
            self.assertEqual(app.status, 'rejected')
            _close_to(self, app.decline_due_at - timezone.now(), timedelta(hours=hours))

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_a_qc_outright_rejection_is_held_for_the_organisations_hours(self):
        # The SECOND QC site: QC rejects a reviewer's recommendation outright.
        quick = make_org()
        _configure(quick, 'qc_decline_hold_hours', 12)
        for org, hours in ((quick, 12), (make_org(), 24)):
            reviewer = make_admin('reviewer', owning_org=org)
            app = make_application('awaiting_qc', outcome='recommend', cohort=_org_cohort(org),
                                   reviewer=reviewer)
            qc = authed_client(make_admin('qc', owning_org=org))
            r = qc.post(f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
                        {'decision': 'reject', 'comments': 'Income evidence does not hold up.'},
                        format='json')
            self.assertEqual(r.status_code, 200, r.content)
            app.refresh_from_db()
            self.assertEqual(app.status, 'rejected')
            _close_to(self, app.decline_due_at - timezone.now(), timedelta(hours=hours))


class TestTheAwardTimings(TestCase):
    def _offer(self, app, *, hours_ago):
        sponsor = Sponsor.objects.create(
            supabase_user_id=f'ot-spon-{app.id}', name='Jane Sponsor',
            email=f'jane{app.id}@sponsor.example', phone='0123', source='friend',
            consent_at=timezone.now(), status='approved')
        sp = Sponsorship.objects.create(application=app, sponsor=sponsor, status='offered',
                                        amount=5000)
        # `offered_at` is auto_now_add, so the age is set AFTER the row exists.
        Sponsorship.objects.filter(pk=sp.pk).update(
            offered_at=timezone.now() - timedelta(hours=hours_ago))
        return sp

    def test_the_award_email_release_is_per_organisation_and_keeps_null_org_awards(self):
        """⚠ A NULL-ORG AWARD IS NEVER DROPPED. Two organisations store a delay AND NULL-org
        awards sit beside them, released on the platform default — or that student would never
        be told they had won. (Bite-checked 2026-10-07: the window's explicit `isnull` arm is
        belt-and-braces on this Django, which already emits `IS NOT NULL` inside the NOT; this
        test pins the outcome whichever half provides it.)"""
        from apps.scholarship import sponsorship
        short, long_ = make_org(), make_org()
        _configure(short, 'award_email_delay_hours', 12)
        _configure(long_, 'award_email_delay_hours', 48)
        rows = {
            'short_13h': (short, 13, True),       # past the org's 12h
            'long_30h': (long_, 30, False),       # inside the org's 48h
            'null_25h': (None, 25, True),         # past the platform's 24h
            'null_20h': (None, 20, False),        # inside the platform's 24h
        }
        offers = {}
        for name, (org, hours, _due) in rows.items():
            app = make_application('awarded', cohort=_org_cohort(org or make_org()))
            if org is None:
                ScholarshipApplication.objects.filter(pk=app.pk).update(owning_organisation=None)
            offers[name] = self._offer(app, hours_ago=hours)
        self.assertEqual(sponsorship.release_award_offer_emails(), 2)
        for name, (_org, _hours, due) in rows.items():
            offers[name].refresh_from_db()
            self.assertEqual(offers[name].offer_emailed_at is not None, due, name)

    def test_the_acceptance_hold_is_the_organisations(self):
        from apps.scholarship import sponsorship
        brisk = make_org()
        _configure(brisk, 'award_confirm_hold_days', 1)
        for org, days in ((brisk, 1), (make_org(), 2)):
            app = make_application('awarded', cohort=_org_cohort(org))
            self._offer(app, hours_ago=1)
            sponsorship.respond_to_award(app, action='accept')
            app.refresh_from_db()
            self.assertEqual(app.status, 'awarded')        # held, not yet confirmed
            _close_to(self, app.award_due_at - timezone.now(), timedelta(days=days))
