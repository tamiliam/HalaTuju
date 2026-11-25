"""Sprint S4a review round: which sub-state moves are money acts, and the offer equals the door.

  * S1: only placing a hold (-> `on_hold`) and lifting it to `on_track` ask the money rule (View scholars +
    Payments: Prepare, owner Q-B); every other target, from a hold or not, asks Manage scholar files, and a
    move from a hold still needs Payments: Prepare. The file's served `can_set_substate` / `can_hold` agree.
  * S2: the cockpit serves `maintenance_controls.can_hold` as the door's rule (`may_hold`), never as
    Payments: Prepare alone.
  * Review round 2, S2: the door judges the move on the sub-state it read, and the write is refused
    `changed_meanwhile` when the stored value moved since (a hold's lift judged as a money move must not
    land as `probation` -> `on_track`, a Manage move).
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import maintenance
from apps.scholarship.models import ScholarshipApplication, StudentActivity
from apps.scholarship.models.activity import EVENT_SUBSTATE_CHANGED
from apps.scholarship.tests.factories import authed_client, make_admin
from apps.scholarship.tests.test_on_hold_review_fixes import API, _Org
from apps.scholarship.views_admin.base import hold_is_money_move

VIEW, MANAGE, PREPARE = 'scholars', 'scholars.approve', 'payments_prepare'


class TheMoneyMoves(SimpleTestCase):
    def test_only_placing_a_hold_and_lifting_it_to_on_track(self):
        for current, target, money in (
                ('on_track', 'on_hold', True), ('probation', 'on_hold', True), ('on_hold', 'on_track', True),
                ('on_hold', 'probation', False), ('on_hold', 'ready_to_close', False),
                ('on_track', 'probation', False), ('probation', 'on_track', False),
                ('on_track', 'ready_to_close', False),
                ('on_hold', 'on_hold', True),                                 # same state: placing a hold
                ('on_hold', None, False), ('on_track', None, False),          # no target
                ('on_hold', 'nonsense', False), ('on_track', 'nonsense', False)):   # unknown target
            with self.subTest(current=current, target=target):
                self.assertIs(hold_is_money_move(current, target), money)


class _Switches(_Org):
    def setUp(self):
        super().setUp()
        org = self.cohort.owning_organisation
        # `pre_s4`: the factory would otherwise apply 0101 and give a `scholars` list Manage.
        self.viewer_prepare = make_admin('admin', owning_org=org, permissions=[VIEW, PREPARE], pre_s4=True)
        self.manager = make_admin('admin', owning_org=org, permissions=[VIEW, MANAGE], pre_s4=True)
        self.manager_prepare = make_admin('admin', owning_org=org, permissions=[VIEW, MANAGE, PREPARE],
                                          pre_s4=True)
        self.see_all_prepare = make_admin('admin', owning_org=org, permissions=['see_all', PREPARE], pre_s4=True)

    def _hold(self):
        maintenance.set_substate(self.app, 'on_hold', by_email='x@example.test')

    def _code(self, admin, substate):
        r = self._substate(admin, substate)
        return r.status_code, (r.json().get('code') if r.status_code == 403 else None)


class TestTheSubstateDoor(_Switches):
    def test_view_and_prepare_place_and_lift_a_hold_and_nothing_else(self):
        self.assertEqual(self._code(self.viewer_prepare, 'probation')[0], 403)
        self.assertEqual(self._code(self.viewer_prepare, 'ready_to_close')[0], 403)
        self.assertEqual(self._code(self.viewer_prepare, 'on_hold'), (200, None))
        self.assertEqual(self._code(self.viewer_prepare, 'probation')[0], 403)       # from the hold: Manage
        self.assertEqual(self._code(self.viewer_prepare, 'ready_to_close')[0], 403)
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'on_hold')
        self.assertEqual(self._code(self.viewer_prepare, 'on_track'), (200, None))

    def test_manage_without_prepare_keeps_the_other_substates_and_never_touches_a_hold(self):
        self.assertEqual(self._code(self.manager, 'probation'), (200, None))
        self.assertEqual(self._code(self.manager, 'on_hold'), (403, 'hold_needs_payments'))
        self._hold()
        self.assertEqual(self._code(self.manager, 'probation'), (403, 'hold_needs_payments'))
        self.assertEqual(self._code(self.manager, 'on_track'), (403, 'hold_needs_payments'))

    def test_manage_and_prepare_move_a_hold_anywhere(self):
        self._hold()
        self.assertEqual(self._code(self.manager_prepare, 'probation'), (200, None))
        self.assertEqual(self._code(self.manager_prepare, 'on_hold'), (200, None))
        self.assertEqual(self._code(self.manager_prepare, 'ready_to_close'), (200, None))

    def test_the_applications_read_with_prepare_moves_nothing(self):
        self.assertEqual(self._code(self.see_all_prepare, 'on_hold')[0], 403)
        self._hold()
        self.assertEqual(self._code(self.see_all_prepare, 'on_track')[0], 403)


class TestTheOfferEqualsTheDoor(_Switches):
    def _controls(self, admin):
        r = authed_client(admin).get(f'{API}scholars/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        c = r.json()['controls']
        return c['can_set_substate'], c['can_hold']

    def _cockpit_can_hold(self, admin):
        r = authed_client(admin).get(f'{API}applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        return r.json()['maintenance_controls']['can_hold']

    def test_the_file_serves_the_door(self):
        """`can_set_substate`: the Manage moves; `can_hold`: placing and lifting a hold (the screen offers a
        move from a hold elsewhere only with both)."""
        self.assertEqual(self._controls(self.viewer_prepare), (False, True))
        self.assertEqual(self._controls(self.manager), (True, False))
        self.assertEqual(self._controls(self.manager_prepare), (True, True))

    def test_the_cockpit_serves_the_door_not_prepare_alone(self):
        self.assertIs(self._cockpit_can_hold(self.see_all_prepare), False)          # was True: Prepare alone
        self.assertEqual(self._code(self.see_all_prepare, 'on_hold')[0], 403)
        # The cockpit is the applications read; with View scholars and Prepare beside it, the hold is offered.
        reads_and_holds = make_admin('admin', owning_org=self.cohort.owning_organisation,
                                     permissions=['see_all', VIEW, PREPARE], pre_s4=True)
        self.assertIs(self._cockpit_can_hold(reads_and_holds), True)


class TestTheJudgedSubstateIsReCheckedAtTheWrite(_Switches):
    """S4a review round 2, S2: someone holding View scholars and Payments: Prepare (no Manage) asks to lift a
    hold; meanwhile someone holding Manage moves the file `on_hold` -> `probation`. The lift was judged a
    money move on the value read, so the write must refuse rather than make `probation` -> `on_track`."""

    def _changes(self):
        return StudentActivity.objects.filter(application=self.app, event=EVENT_SUBSTATE_CHANGED).count()

    def test_a_move_judged_on_a_stale_hold_is_refused_and_writes_nothing(self):
        self._hold()
        before = self._changes()
        real = hold_is_money_move

        def judged_then_moved_meanwhile(current, target):
            answer = real(current, target)
            ScholarshipApplication.objects.filter(pk=self.app.pk).update(maintenance_substate='probation')
            return answer

        with mock.patch('apps.scholarship.views_admin.lifecycle.hold_is_money_move',
                        side_effect=judged_then_moved_meanwhile):
            r = self._substate(self.viewer_prepare, 'on_track')
        self.assertEqual((r.status_code, r.json().get('error')), (400, 'changed_meanwhile'))
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'probation')
        self.assertEqual(self._changes(), before)

    def test_the_service_refuses_when_the_stored_value_is_not_the_judged_one(self):
        self._hold()
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(maintenance_substate='probation')
        before = self._changes()
        with self.assertRaises(maintenance.MaintenanceError) as caught:
            maintenance.set_substate(self.app, 'on_track', by_email='x@example.test', expected='on_hold')
        self.assertEqual(caught.exception.code, 'changed_meanwhile')
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'probation')
        self.assertEqual(self._changes(), before)

    def test_the_judged_value_still_stored_moves_as_before(self):
        self._hold()
        maintenance.set_substate(self.app, 'on_track', by_email='x@example.test', expected='on_hold')
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'on_track')
