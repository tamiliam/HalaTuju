"""Sprint M1a (2026-11-10): every reader of a staff row knows about archived rows (brief §5, census).

An ARCHIVED `PartnerAdmin` (`staff_archive`) is kept for its name and its records, but it is on no list
and out of reach by id; the one way back is a re-invite of the address. This guard walks every
non-test, non-migration module under `apps/` and finds each `PartnerAdmin.objects` /
`Invitation.objects` site, keyed ``path::qualname`` with the number of sites in it. It FAILS on a site
not classified below (a new reader: decide what an archived row means to it) and on a stale entry
(a reader that moved or went: update the table). The pattern is `test_t2_footprint_drift.py`'s.

The classes:

- ``FILTERED``   a list, picker or one-off command that excludes archived rows explicitly (M1a).
- ``FENCED``     reached by id only through a fence that refuses an archived row with a 404
                 (`staff_fence._staff_target_manageable`, `staff_tables_admin.may_act`, the Mentors
                 tab's `_in_scope`) or re-reads the locked row with ``archived_at=None``.
- ``ACTIVE``     reads ``is_active=True`` rows only (or an `eligible` that does): an archived row is
                 always inactive, and Restore (`AdminRevokeView`) cannot revive one (it is fenced).
- ``SHAPE``      cannot meet an archived row by the archive's own shape: it cleared the login UID and
                 cancelled every waiting invitation.
- ``KEEPS``      reads names or history: an archived person's name staying on past records is the
                 point of archiving (owner O7). Or a refusal that must keep refusing.
- ``OWN_ROW``    a row already in hand (by pk after a fence, the caller's own, a lock inside a flow).
- ``ARCHIVE``    the archive and restore doors themselves (they handle archived rows on purpose).
- ``NOT_STAFF``  sponsor and source-partner flows: those rows are never archived (the archive is
                 reached only through the staff and mentor Delete doors).
"""
import ast
import os
import re

from django.test import SimpleTestCase

APPS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SITE = re.compile(r'\b(PartnerAdmin|Invitation)\.objects\b')
CLASSES = {'FILTERED', 'FENCED', 'ACTIVE', 'SHAPE', 'KEEPS', 'OWN_ROW', 'ARCHIVE', 'NOT_STAFF'}

C, S = 'courses/', 'scholarship/'
#: ``path::qualname`` -> (sites in it, class, why).
CENSUS = {
    # ── courses ────────────────────────────────────────────────────────────────────────────────────
    C + 'admin.py::PartnerAdminAdmin.save_model': (1, 'OWN_ROW',
        'M3a review: locks the row the Django admin screen is saving, to audit its role change'),
    C + 'management/commands/backfill_admin_seen.py::Command.handle': (3, 'FILTERED', 'uid set AND not archived'),
    C + 'management/commands/expire_temp_passwords.py::Command.handle': (1, 'SHAPE', 'needs a login UID'),
    C + 'models/organisations.py::PartnerOrganisationQuerySet.tenants': (1, 'ACTIVE', 'an active org admin'),
    C + 'referral_links.py::mark_refusal': (1, 'ACTIVE', 'active referral partners'),
    C + 'staff_archive.py::archive_locked': (2, 'ARCHIVE', 'the archive itself'),
    C + 'staff_archive.py::before_delete': (1, 'ARCHIVE', 'the Delete door; the fence refuses archived'),
    C + 'staff_archive.py::lock_mentor_of': (1, 'OWN_ROW', "a lock peek by id; the door's fence refuses archived"),
    C + 'staff_archive.py::restore': (2, 'ARCHIVE', 'the restore; the address check'),
    C + 'staff_delete_rules.py::_org_admins': (1, 'ACTIVE', 'active org admins'),
    C + 'staff_delete_rules.py::sole_org_admin_ids': (1, 'ACTIVE', 'active org admins'),
    C + 'staff_gift.py::unchosen_rows': (1, 'FILTERED', 'the gift report'),
    C + 'staff_permissions.py::org_staff': (1, 'ACTIVE', 'active staff'),
    C + 'staff_permissions.py::team_holding': (1, 'OWN_ROW', 'a Q builder; each caller is classified'),
    C + 'staff_reinvite.py::bring_back': (2, 'ARCHIVE', 'refuses an archived row (restore takes it)'),
    C + 'staff_reinvite.py::is_withdrawn': (2, 'KEEPS', 'a sign-in refusal: an archived row stays refused'),
    C + 'staff_reinvite.py::provision': (1, 'ARCHIVE', 'hands an archived row to restore'),
    C + 'supabase_admin.py::link_login': (2, 'ACTIVE', 'links an active row only'),
    C + 'views_admin.py::PartnerAdminMixin._find_admin': (2, 'ACTIVE', 'the caller: active only'),
    C + 'views_admin.py::_invitations_for': (1, 'OWN_ROW', 'rows of an already filtered list'),
    C + 'views_admin.py::_touch_seen': (2, 'OWN_ROW', "the caller's own row"),
    C + 'views_staff.py::AdminDeleteView._delete_locked': (1, 'FENCED', '_deletable_now -> the fence'),
    C + 'views_staff.py::AdminInviteView.post': (1, 'ARCHIVE', 'archived -> restore or not_invitable'),
    C + 'views_staff.py::AdminListView.get': (1, 'FILTERED', 'the staff list'),
    C + 'views_staff_list.py::StaffListView.get': (1, 'FILTERED', 'the M1a Staff list'),
    C + 'views_staff.py::AdminResendView.post': (1, 'FENCED', 'the fence'),
    C + 'views_staff.py::AdminRevokeView.patch': (1, 'FENCED', 'the fence: Restore never revives one'),
    # ── scholarship ────────────────────────────────────────────────────────────────────────────────
    S + 'activity_people.py::Actors.__init__': (1, 'KEEPS', 'names on the activity log'),
    S + 'award_withdrawal_chain.py::_mail_checkers': (1, 'OWN_ROW', 'checker ids chosen by the chain'),
    S + 'bursary.py::foundation_notify_emails': (1, 'ACTIVE', 'active supers'),
    S + 'emails/payment_mail.py::_instruction_cc': (1, 'ACTIVE', 'active org admins'),
    S + 'invitations.py::accept_for_admin': (2, 'SHAPE', 'a sign-in: an archived row has no login'),
    S + 'invitations.py::create_or_refresh': (1, 'OWN_ROW', 'the caller passes the row'),
    S + 'invitations.py::open_invitation': (1, 'SHAPE', 'open ones only; the archive cancelled them'),
    S + 'invitations.py::purge_expired': (1, 'SHAPE', 'housekeeping by age'),
    S + 'management/commands/backfill_invitations.py::Command.handle': (3, 'FILTERED', 'staff not archived'),
    S + 'management/commands/bursary_e2e.py::Command._walk': (1, 'OWN_ROW', 'a seed it creates'),
    S + 'management/commands/send_review_nudges.py::Command.handle.escalation_recipients':
        (1, 'ACTIVE', 'active org admins'),
    S + 'mentor_archive.py::archive': (1, 'ARCHIVE', 'the mentor archive itself'),
    S + 'mentor_invite.py::_move_address': (3, 'FENCED', "the Mentors tab's _in_scope"),
    S + 'mentor_invite.py::_newest_invitation': (1, 'OWN_ROW', 'a login in hand'),
    S + 'mentor_invite.py::_reinvite': (1, 'FENCED', 'invite sends an archived address to mentor_archive'),
    S + 'mentor_invite.py::_switch_off': (3, 'FENCED', "the Mentors tab's _in_scope"),
    S + 'mentor_invite.py::delete_mentor': (2, 'FENCED', 'an archived login answers not_found'),
    S + 'mentor_invite.py::edit': (2, 'FENCED', "the Mentors tab's _in_scope"),
    S + 'mentor_invite.py::invite': (1, 'ARCHIVE', 'archived -> mentor_archive.reinvite'),
    S + 'mentor_invite.py::login_of': (1, 'FENCED', 'a mentor already in scope'),
    S + 'mentor_invite.py::reactivate': (1, 'FENCED', "the Mentors tab's _in_scope"),
    S + 'mentoring.py::mentor_facts': (2, 'KEEPS', "facts of mentors in hand; a past mentor's are history"),
    S + 'mentoring_read.py::_people': (1, 'KEEPS', 'names on mentoring records'),
    S + 'my_pending.py::_invitations': (1, 'SHAPE', 'waiting counts; the archive cancelled them'),
    S + 'payments_chain.py::fallback_approvers': (1, 'ACTIVE', 'active org admins'),
    S + 'scholars.py::_mentor_name': (1, 'KEEPS', "the current mentor's name (an archived one has none)"),
    S + 'serializers_admin/names.py::_admin_name_by_email': (1, 'KEEPS', 'a name on a record'),
    S + 'services/assignment.py::_locked': (1, 'OWN_ROW', 'a reviewer already picked'),
    S + 'source_invite.py::_reactivate': (1, 'NOT_STAFF', 'source partner'),
    S + 'source_invite.py::has_joined': (1, 'NOT_STAFF', 'source partner'),
    S + 'source_invite.py::has_person': (1, 'NOT_STAFF', 'source partner'),
    S + 'source_invite.py::invite': (1, 'NOT_STAFF', 'an archived staff address is already_staff'),
    S + 'source_invite.py::people_of': (1, 'NOT_STAFF', 'source partner'),
    S + 'source_invite.py::revoke': (3, 'NOT_STAFF', 'source partner'),
    S + 'source_invite.py::sign_in_states': (1, 'NOT_STAFF', 'source partner'),
    S + 'sponsor_invite_gifts.py::joined_on_registration': (2, 'NOT_STAFF', 'sponsor invitations'),
    S + 'sponsor_invite_gifts.py::set_gifts': (1, 'NOT_STAFF', 'sponsor invitations'),
    S + 'sponsor_invite_gifts.py::stating_invitation': (1, 'NOT_STAFF', 'sponsor invitations'),
    S + 'staff_activity_backfill.py::_first_sign_ins': (1, 'KEEPS', 'history'),
    S + 'staff_activity_backfill.py::_invitations': (1, 'KEEPS', 'history'),
    S + 'staff_activity_backfill.py::email_index': (1, 'KEEPS', 'history'),
    S + 'staff_activity_read.py::_staff': (1, 'KEEPS', 'names on the activity log'),
    S + 'staff_footprint.py::footprint': (1, 'OWN_ROW', 'a row in hand'),
    S + 'staff_lifecycle.py::adoptable_login': (1, 'SHAPE', 'by login UID; the archive cleared it'),
    S + 'staff_lifecycle.py::change_role': (3, 'FENCED', 'locked re-read with archived_at=None'),
    S + 'staff_lifecycle.py::credential_was_issued': (1, 'OWN_ROW', 'a row in hand'),
    S + 'staff_mentor.py::add': (2, 'FENCED', 'AdminStaffMentorsView.post refuses archived'),
    S + 'staff_mentor.py::add_member': (2, 'ACTIVE', 'an active, signed-in member'),
    S + 'staff_mentor.py::candidates': (1, 'ACTIVE', 'active staff'),
    S + 'staff_mentor.py::leave': (1, 'OWN_ROW', 'inside a delete, archive or role change'),
    S + 'staff_mentor.py::remove_mentor_login': (2, 'FENCED', 'staff_tables_admin.may_act'),
    S + 'staff_mentor.py::resume': (1, 'ACTIVE', 'eligible() needs is_active'),
    S + 'staff_mentor.py::stop': (1, 'FENCED', 'locked re-read with archived_at=None'),
    S + 'staff_permissions_admin.py::change_permissions': (2, 'FENCED', 'locked re-read with archived_at=None'),
    S + 'staff_tables_admin.py::candidates': (1, 'ACTIVE', 'active staff'),
    S + 'staff_tables_admin.py::change': (3, 'FENCED', 'may_act refuses archived'),
    S + 'views_admin/invitations.py::AdminInvitationCancelView.post': (2, 'FILTERED', "an archived person's"),
    S + 'views_admin/invitations.py::AdminInvitationsView.get': (1, 'FILTERED', 'the Invitations list'),
    S + 'views_admin/lifecycle.py::AdminAssignableAdminsView.get': (2, 'ACTIVE', 'picks active; past = names'),
    S + 'views_admin/mentors.py::AdminMentorView.get': (1, 'FENCED', "the Mentors tab's _in_scope"),
    S + 'views_admin/mentors.py::AdminStaffMentorsView.post': (1, 'FILTERED', 'add a staff member as mentor'),
    S + 'views_admin/mentors.py::_is_addable_team_member': (1, 'ACTIVE', 'eligible() needs is_active'),
    S + 'views_admin/mentors.py::mentor_rows': (2, 'FENCED', "mentors from the tab's _in_scope"),
    S + 'views_admin/reviewers.py::ReviewerProfileView.patch': (2, 'OWN_ROW', "the caller's own row"),
    S + 'views_admin/reviewers.py::_ReviewersBase._reviewers': (1, 'FILTERED', 'the Reviewers list'),
    S + 'views_admin/scholars.py::_staff_names': (1, 'KEEPS', 'names on records'),
    S + 'views_admin/source_users.py::_SourceUserBase._target': (1, 'NOT_STAFF', 'source partner'),
    S + 'views_admin/source_users.py::source_kind_extras': (2, 'NOT_STAFF', 'source partner'),
    S + 'views_admin/staff.py::AdminStaffPermissionsView._target': (1, 'FENCED', 'the fence'),
    S + 'views_admin/staff.py::AdminStaffRoleView.patch': (1, 'FENCED', 'the fence'),
    S + 'views_admin/staff.py::AdminTeamTableView.post': (1, 'FENCED', 'may_act refuses archived'),
    S + 'views_admin/staff.py::_permission_history': (1, 'KEEPS', 'names on the history'),
    S + 'views_admin/verdict.py::AdminAssignReviewerView.post': (1, 'ACTIVE', 'an active assignee'),
    S + 'views_sponsor.py::_close_admin_invitation': (1, 'NOT_STAFF', 'sponsor invitations'),
}


def _spans(tree):
    out = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                out.append((child.lineno, child.end_lineno, name))
                walk(child, name + '.')
            else:
                walk(child, prefix)
    walk(tree, '')
    return out


def census():
    """``{path::qualname: number of sites}`` over the live tree."""
    found = {}
    for folder, dirs, files in os.walk(APPS):
        dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__')]
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            if not SITE.search(src):
                continue
            spans = _spans(ast.parse(src))
            rel = os.path.relpath(path, APPS).replace(os.sep, '/')
            for n, line in enumerate(src.splitlines(), 1):
                if SITE.search(line):
                    inside = [s for s in spans if s[0] <= n <= s[1]]
                    key = rel + '::' + (max(inside)[2] if inside else '<module>')
                    found[key] = found.get(key, 0) + 1
    return found


class TestArchiveReaderCensus(SimpleTestCase):
    def test_every_site_is_classified(self):
        found = census()
        unclassified = sorted(k for k in found if k not in CENSUS)
        self.assertEqual(unclassified, [], 'A new PartnerAdmin/Invitation reader: decide what an ARCHIVED row '
                                           'means to it (filter it, or say why not) and add it to CENSUS.')
        moved = sorted(k for k, n in found.items() if CENSUS[k][0] != n)
        self.assertEqual(moved, [], 'A classified reader gained or lost a site: re-judge it, then fix the count.')

    def test_no_stale_entries(self):
        stale = sorted(set(CENSUS) - set(census()))
        self.assertEqual(stale, [], 'These readers moved or went: update CENSUS.')

    def test_every_entry_has_a_known_class_and_a_reason(self):
        for key, (count, kind, why) in CENSUS.items():
            with self.subTest(key=key):
                self.assertIn(kind, CLASSES)
                self.assertGreater(count, 0)
                self.assertTrue(why.strip())
