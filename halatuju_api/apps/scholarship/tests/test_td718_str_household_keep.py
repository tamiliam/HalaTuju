"""TD-718 repair — an approved STR is never replaced by a page that is not approved (owner 2026-11-25).

The owner's ruling (d)/(e): nothing approved today may lose its approval, and a received page, an
application details page or an unread page must never replace a live APPROVED STR.

The hole: the household STR de-dupe (``dedupe_income_proof``) collapses the STR across ALL members and
ranked (genuine, has-a-date, year, id). A father's "Lulus" with no year lost to a mother's newer
"Permohonan Diterima 2026"; so did a father's "Lulus 2026" (same year, newer id). The repair (R1):
``income_dedup_rank`` ranks STR approval second, after genuineness.

Also here: R2 (a body "berjaya" never overrides a label-anchored pending value, nor keeps a page out
of the application details signature), R3 (the strict approved words) and R4 (Unicode spaces in the
application page labels).

Round 2 (R6): the household rank in THREE tiers — approved 2, rejected / unread 1, every failing state
0 — so a rejection under one member no longer buries an unread (amber) page under another. R7: the
rejection wordings "Tidak Diluluskan" / "Not Approved" and the reader's whole "Tidak Lulus" phrase.

Round 4: tier 2 is only for an approval a household card MATCHED (the twin of
``promotion._str_matched(doc, counting=True)``); every other approval — not judged yet, pending, or a
stranger's — is tier 1 with rejections and unread pages, where the base order decides. Round 3's
stranger tier 0 is gone.

Round 5: tier 2 reads only the page's OWN name / NRIC against the household's IC cards. The IC-number
chain (birth certificate ↔ the NEWEST live STR) let an outsider's approval borrow the family's newer
page's match during the de-dupe; a chain-only match is tier 1 now (it still counts at the TD-409
same-slot guard, so tier 2 implies ``promotion._str_matched(doc, counting=True)`` but not the reverse).

The R1 and R6 tests drive the REAL upload path — ``slot_writes.create_in_slot`` → ``upload_read.judge`` —
with the read already stored (no OCR, no Gemini). All names and numbers are invented.
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.doc_parse import parse_by_labels
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

STUDENT, STUDENT_NRIC = 'Vimal A/L Rasanthiran', '070303-10-2468'
FATHER, FATHER_NRIC = 'Rasanthiran A/L Velappan', '720202-10-5135'
MOTHER, MOTHER_NRIC = 'Shalini A/P Kumaresan', '750404-10-6248'
OUTSIDER, OUTSIDER_NRIC = 'Gunalan A/L Muthiah', '660606-10-7351'     # nobody in this household


def _app(ics=('father', 'mother')):
    app = make_application(
        'shortlisted', income_route='str', income_earner='father', income_working_members=[],
        father_name=FATHER, mother_name=MOTHER, father_occupation='private',
        mother_occupation='homemaker', other_family_members=[],
        student=make_student(nric=STUDENT_NRIC, name=STUDENT))
    now = timezone.now()
    for member, name, nric in (('father', FATHER, FATHER_NRIC), ('mother', MOTHER, MOTHER_NRIC)):
        if member not in ics:
            continue
        ApplicantDocument.objects.create(
            application=app, doc_type='parent_ic', storage_path=f'test/ic/{member}',
            household_member=member, vision_name=name.upper(), vision_nric=nric, vision_run_at=now)
    return app


def _fields(name, nric, status, year, source_type):
    return {'fields': {'recipient_name': name.upper(), 'recipient_nric': nric, 'status': status,
                       'year': year, 'source_type': source_type}, 'student_verdict': 'ok', 'error': ''}


def _who(member, who):
    return who or ((FATHER, FATHER_NRIC) if member == 'father' else (MOTHER, MOTHER_NRIC))


def _live_str(app, member, *, status, year, source_type='semakan_status', who=None):
    name, nric = _who(member, who)
    return ApplicantDocument.objects.create(
        application=app, doc_type='str', storage_path=f'test/str/live/{member}', household_member=member,
        vision_run_at=timezone.now(), vision_fields=_fields(name, nric, status, year, source_type))


def _upload_str(app, member, *, status, year, source_type='semakan_status', who=None):
    """The upload view's own steps (views/documents.py), the read already stored: the slot sweep
    [member, ''], the staged create, then the judge (tag guard → promote → household de-dupe)."""
    from apps.scholarship import slot_writes, upload_read
    from apps.scholarship.document_snapshot import SNAPSHOT_ORDER
    name, nric = _who(member, who)
    slot_filter = dict(application=app, doc_type='str', household_member__in=[member, ''],
                       request_code='', superseded_at__isnull=True)
    stale_ids = list(ApplicantDocument.objects.filter(**slot_filter).values_list('id', flat=True))
    existing_live = ApplicantDocument.objects.filter(id__in=stale_ids).order_by(*SNAPSHOT_ORDER).first()
    data = dict(doc_type='str', storage_path=f'test/str/up/{ApplicantDocument.objects.count()}',
                household_member=member, request_code='', vision_run_at=timezone.now(),
                vision_fields=_fields(name, nric, status, year, source_type))
    doc = slot_writes.create_in_slot(app, data, staged=True, existing_live=existing_live,
                                     stale_ids=stale_ids, slot_filter=slot_filter)
    upload_read.judge(app, doc, staged=True, stale_ids=stale_ids, existing_live=existing_live)
    doc.refresh_from_db()
    return doc


def _status(doc):
    from apps.scholarship.income_engine import student_str_check
    return student_str_check(doc)['current_status']


# (the father's live approved copy, the mother's upload) — the brief's three combinations, plus the
# blank, stale and unread states that also must never win.
_APPROVED_KEPT = [
    (('Lulus', '2026'), ('Permohonan Diterima', '2026', 'semakan_status'), 'not_approved'),
    (('Lulus', ''), ('Permohonan Diterima', '2026', 'semakan_status'), 'not_approved'),
    (('Lulus', ''), ('', '', 'unknown'), 'wrong_type'),             # an application details page
    (('Lulus', ''), ('', '2026', 'semakan_status'), 'unreadable'),  # a genuine page, status unread
    (('Lulus', '2026'), ('Dalam Proses Kelulusan', '2026', 'semakan_status'), 'not_approved'),
]


class AnApprovedStrKeepsItsHouseholdSlot(TestCase):
    """R1 on the real upload path, cross-member."""

    def test_a_not_approved_page_under_the_mother_never_replaces_the_fathers_approval(self):
        from apps.scholarship.income_engine import str_not_breached
        for (f_status, f_year), (m_status, m_year, m_source), m_state in _APPROVED_KEPT:
            with self.subTest(father=(f_status, f_year), mother=(m_status, m_year, m_source)):
                app = _app()
                father = _live_str(app, 'father', status=f_status, year=f_year)
                self.assertIn(_status(father), ('current', 'unconfirmed'))
                self.assertIs(str_not_breached(app), True)
                mother = _upload_str(app, 'mother', status=m_status, year=m_year, source_type=m_source)
                self.assertEqual(_status(mother), m_state)
                father.refresh_from_db()
                self.assertIsNone(father.superseded_at, 'the approved copy must stay live')
                self.assertIsNotNone(mother.superseded_at, 'the not-approved page goes to Replaced')
                self.assertEqual(list(ApplicantDocument.objects.filter(
                    application=app, doc_type='str', superseded_at__isnull=True)), [father])
                self.assertIs(str_not_breached(app), True)

    def test_the_reverse_an_approved_upload_replaces_a_not_approved_live_copy(self):
        from apps.scholarship.income_engine import str_not_breached
        # (the father's live copy, does it pass on its own) — an unread status is amber and passes.
        for f_status, f_year, f_source, passes in (('Permohonan Diterima', '2026', 'semakan_status', False),
                                                   ('', '', 'unknown', False),
                                                   ('', '2026', 'semakan_status', True)):
            for m_year in ('2026', ''):
                with self.subTest(father=(f_status, f_year, f_source), mother_year=m_year):
                    app = _app()
                    father = _live_str(app, 'father', status=f_status, year=f_year, source_type=f_source)
                    self.assertIs(str_not_breached(app), passes)
                    mother = _upload_str(app, 'mother', status='Lulus', year=m_year)
                    father.refresh_from_db()
                    self.assertIsNone(mother.superseded_at, 'the approval takes the household slot')
                    self.assertIsNotNone(father.superseded_at)
                    self.assertEqual(father.superseded_by_id, mother.id)
                    self.assertIs(str_not_breached(app), True)


class TheHouseholdDedupeRank(TestCase):
    """R1 on the de-dupe itself (both copies already live — a legacy pile-up, the backfill, a sweep)."""

    def _both_live(self, older, newer):
        app = _app()
        a = _live_str(app, 'father', status=older[0], year=older[1])
        b = _live_str(app, 'mother', status=newer[0], year=newer[1])
        return app, a, b

    def _dedupe(self, app):
        from apps.scholarship.income_engine import dedupe_income_proof
        return dedupe_income_proof(app, 'mother', 'str')

    def test_an_older_approval_beats_a_newer_not_approved_copy(self):
        for newer in (('Permohonan Diterima', '2026'), ('Dalam Proses', ''), ('', '2026'),
                      ('Lulus', '2024'), ('Lulus', '2027')):           # not_approved, unread, stale, future
            with self.subTest(newer=newer):
                app, a, b = self._both_live(('Lulus', ''), newer)
                self.assertEqual(self._dedupe(app), [b.id])

    def test_an_approval_holds_against_a_rejection_across_members_whatever_the_dates(self):
        """Round 2 (three tiers): an approval is tier 2, a rejection tier 1, so across household
        members the approval holds even against a NEWER rejection (owner 2026-07-07: an approved STR
        wins regardless of the member tag). Before round 2 a newer rejection superseded it here. A
        newer approval still supersedes a rejection; a received page never buries a rejection."""
        app, a, b = self._both_live(('Lulus', '2026'), ('Ditolak', '2026'))
        self.assertEqual(self._dedupe(app), [b.id])
        app, a, b = self._both_live(('Tidak Layak', '2026'), ('Lulus', '2026'))
        self.assertEqual(self._dedupe(app), [a.id])
        app, a, b = self._both_live(('Ditolak', '2026'), ('Permohonan Diterima', '2026'))
        self.assertEqual(self._dedupe(app), [b.id])

    def test_a_rejection_and_an_unread_page_rank_by_date_then_upload_as_on_base(self):
        app, a, b = self._both_live(('Ditolak', '2026'), ('', '2026'))
        self.assertEqual(self._dedupe(app), [a.id])           # the newer unread page wins
        app, a, b = self._both_live(('', '2026'), ('Ditolak', '2026'))
        self.assertEqual(self._dedupe(app), [a.id])           # the newer rejection wins (news)
        app, a, b = self._both_live(('Ditolak', '2026'), ('', ''))
        self.assertEqual(self._dedupe(app), [b.id])           # a dated copy beats an undated one

    def test_genuineness_still_leads(self):
        app, a, b = self._both_live(('Permohonan Diterima', '2026'), ('Lulus', '2026'))
        vf = b.vision_fields
        vf['authenticity'] = {'status': 'suspect'}
        b.vision_fields = vf
        b.save(update_fields=['vision_fields'])
        from apps.scholarship.income_engine.freshness import _doc_genuine_rank
        self.assertEqual(_doc_genuine_rank(b), 0)
        self.assertEqual(self._dedupe(app), [b.id])

    def test_two_approvals_still_rank_by_year_then_upload(self):
        app, a, b = self._both_live(('Lulus', '2026'), ('Lulus', ''))
        self.assertEqual(self._dedupe(app), [b.id])          # a dated copy beats an undated one
        app, a, b = self._both_live(('Lulus', '2026'), ('Diluluskan', '2026'))
        self.assertEqual(self._dedupe(app), [a.id])          # same year → the latest upload


class NonStrRankingIsUnchanged(SimpleTestCase):
    def test_the_str_tier_is_one_for_every_other_type(self):
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        for dt in ('salary_slip', 'epf', 'water_bill', 'electricity_bill'):
            doc = ApplicantDocument(doc_type=dt, vision_fields={'fields': {}})
            self.assertEqual(_dedup_str_rank(doc), 1)


# ── Round 2 (R6): the household rank in three tiers ───────────────────────────────────────────
def _live_strs(app):
    return list(ApplicantDocument.objects.filter(application=app, doc_type='str', superseded_at__isnull=True))


_UNREAD = [('', '2026', 'semakan_status'), ('', '', 'semakan_status')]       # amber 'unreadable'
_FAILING = [(('Permohonan Diterima', '2026', 'semakan_status'), 'not_approved'),
            (('', '', 'unknown'), 'wrong_type'),                           # an application details page
            (('Lulus', '2025', 'semakan_status'), 'stale'),
            (('Lulus', '2027', 'semakan_status'), 'future')]


class TheHouseholdRankInThreeTiers(TestCase):
    """R6 on the real upload path (``create_in_slot`` → ``upload_read.judge``), cross-member."""

    def _check(self, app, live_doc, gate):
        from apps.scholarship.income_engine import str_not_breached
        live_doc.refresh_from_db()
        self.assertEqual(_live_strs(app), [live_doc], 'exactly one live STR, the expected one')
        self.assertIs(str_not_breached(app), gate)

    def test_case1_an_unread_page_under_the_mother_replaces_the_fathers_rejection(self):
        for year in ('2026', ''):
            with self.subTest(year=year):
                app = _app()
                father = _live_str(app, 'father', status='Ditolak', year=year)
                self.assertEqual(_status(father), 'rejected')
                mother = _upload_str(app, 'mother', status='', year=year)
                self.assertEqual(_status(mother), 'unreadable')
                self._check(app, mother, True)

    def test_case2_a_rejection_under_the_mother_replaces_the_fathers_unread_page(self):
        app = _app()
        father = _live_str(app, 'father', status='', year='2026')
        self.assertEqual(_status(father), 'unreadable')
        mother = _upload_str(app, 'mother', status='Ditolak', year='2026')
        self._check(app, mother, False)

    def test_case3_a_failing_page_under_the_mother_never_replaces_the_fathers_unread_page(self):
        for f_status, f_year, f_source in _UNREAD:
            for (m_status, m_year, m_source), m_state in _FAILING:
                with self.subTest(father_year=f_year, mother=m_state):
                    app = _app()
                    father = _live_str(app, 'father', status=f_status, year=f_year, source_type=f_source)
                    self.assertEqual(_status(father), 'unreadable')
                    mother = _upload_str(app, 'mother', status=m_status, year=m_year, source_type=m_source)
                    self.assertEqual(_status(mother), m_state)
                    self._check(app, father, True)

    def test_case4_a_newer_received_page_never_replaces_a_rejection(self):
        app = _app()
        father = _live_str(app, 'father', status='Ditolak', year='2026')
        _upload_str(app, 'mother', status='Permohonan Diterima', year='2026')
        self._check(app, father, False)

    def test_case5_an_approval_holds_against_a_later_rejection_under_another_member(self):
        for (m_status, m_year, m_source), (f_status, f_year) in (
                (('Lulus', '2026', 'semakan_status'), ('Ditolak', '2026')),
                (('Lulus', '', 'semakan_status'), ('Ditolak', '')),
                (('Lulus', '', 'dashboard'), ('Ditolak', '2026'))):
            with self.subTest(mother=(m_status, m_year, m_source), father=(f_status, f_year)):
                app = _app()
                mother = _live_str(app, 'mother', status=m_status, year=m_year, source_type=m_source)
                self.assertIn(_status(mother), ('current', 'unconfirmed'))
                father = _upload_str(app, 'father', status=f_status, year=f_year)
                self.assertEqual(_status(father), 'rejected')
                self._check(app, mother, True)

    def test_case6_a_later_approval_under_the_mother_replaces_the_fathers_rejection(self):
        app = _app()
        _live_str(app, 'father', status='Ditolak', year='2026')
        mother = _upload_str(app, 'mother', status='Lulus', year='2026')
        self._check(app, mother, True)

    def test_case7_same_member_a_rejection_still_replaces_the_approval_in_its_own_slot(self):
        """The news rule is not gone: in the SAME slot ``promotion.should_promote`` promotes a
        rejection over a live approval (str_proof_quality None)."""
        app = _app()
        approved = _live_str(app, 'father', status='Lulus', year='2026')
        rejection = _upload_str(app, 'father', status='Ditolak', year='2026')
        approved.refresh_from_db()
        self.assertIsNotNone(approved.superseded_at)
        self._check(app, rejection, False)


class TheTierOfEveryState(TestCase):
    """R6 unit rows: ``_dedup_str_rank`` maps every currency state to its tier."""

    def test_every_currency_state(self):
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        app = _app()
        for (status, year, source), state, tier in (
                (('Lulus', '2026', 'semakan_status'), 'current', 2),
                (('Lulus', '', 'semakan_status'), 'unconfirmed', 2),
                (('Ditolak', '2026', 'semakan_status'), 'rejected', 1),
                (('', '2026', 'semakan_status'), 'unreadable', 1),
                (('Permohonan Diterima', '2026', 'semakan_status'), 'not_approved', 0),
                (('', '', 'unknown'), 'wrong_type', 0),
                (('Lulus', '2025', 'semakan_status'), 'stale', 0),
                (('Lulus', '2027', 'semakan_status'), 'future', 0)):
            with self.subTest(state=state):
                doc = ApplicantDocument(application=app, doc_type='str', household_member='father',
                                        vision_fields=_fields(FATHER, FATHER_NRIC, status, year, source))
                self.assertEqual(_status(doc), state)
                self.assertEqual(_dedup_str_rank(doc), tier)

    def test_blank_unknown_or_no_state_is_tier_zero(self):
        from unittest import mock
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        doc = ApplicantDocument(doc_type='str', vision_fields={'fields': {}})
        for ret in (None, {}, {'current_status': None}, {'current_status': ''},
                    {'current_status': 'unknown'}):
            with self.subTest(ret=ret), mock.patch(
                    'apps.scholarship.income_engine.str_route.student_str_check', return_value=ret):
                self.assertEqual(_dedup_str_rank(doc), 0)

    def test_no_fields_and_no_cohort_year_do_not_crash(self):
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        app = _app()
        self.assertEqual(_dedup_str_rank(ApplicantDocument(application=app, doc_type='str',
                                                           household_member='father', vision_fields=None)), 0)
        app.cohort = None
        doc = ApplicantDocument(application=app, doc_type='str', household_member='father',
                                vision_fields=_fields(FATHER, FATHER_NRIC, 'Lulus', '', 'semakan_status'))
        self.assertEqual(_dedup_str_rank(doc), 2)


# ── Rounds 3-4: only a household-MATCHED approval holds the slot ──────────────────────────────
# Round 3 gave a stranger's copy (``str_check_names_a_stranger``) tier 0. Round 4 removed that rule: a
# stranger verdict depends on which ICs are on file and how they read, so it can be wrong or late, and
# an approval nobody had judged yet kept tier 2 and blocked a real family. Now tier 2 needs POSITIVE
# evidence — a household card matched the recipient (round 4: the twin of ``promotion._str_matched``;
# round 5: the page's own card hit, minus the chain) — and every other approval, a stranger's
# included, is tier 1, where the base order decides.
_OUT = (OUTSIDER, OUTSIDER_NRIC)


def _blockers(app):
    from apps.scholarship.services.blockers import income_doc_blockers
    return income_doc_blockers(app)


def _add_ic(app, member):
    name, nric = (FATHER, FATHER_NRIC) if member == 'father' else (MOTHER, MOTHER_NRIC)
    ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'test/ic/{member}/late',
        household_member=member, vision_name=name.upper(), vision_nric=nric, vision_run_at=timezone.now())


class AnOutsidersApprovalFollowsTheBaseOrder(TestCase):
    """Round 4 on the real upload path: an outsider's approval is tier 1, so against the family's own
    unread (tier 1) page the base order decides — has-a-date, then recency, then the newer upload."""

    def _live_one(self, app, want):
        want.refresh_from_db()
        self.assertEqual(_live_strs(app), [want])

    def test_1_the_familys_unread_page_and_an_outsiders_approval_rank_as_on_base(self):
        """Reworked (round 3 expected the family's page to win in every order: stranger tier 0). Now
        the base order decides: a dated outsider approval beats an undated family page, and between
        two pages of the same year the newer upload wins."""
        for order, year, winner in (('outsider first', '2026', 'family'),
                                    ('outsider first', '', 'outsider'),     # dated beats undated
                                    ('family first', '2026', 'outsider'),   # same year, newer upload
                                    ('family first', '', 'outsider')):
            with self.subTest(order=order, year=year):
                app = _app()
                if order == 'outsider first':
                    outsider = _live_str(app, 'father', status='Lulus', year='2026', who=_OUT)
                    self.assertEqual(_status(outsider), 'current')
                    self.assertIn('str_not_household', _blockers(app), 'the fixture is a true stranger')
                    mother = _upload_str(app, 'mother', status='', year=year)
                    self.assertEqual(_status(mother), 'unreadable')
                else:
                    mother = _live_str(app, 'mother', status='', year=year)
                    outsider = _upload_str(app, 'father', status='Lulus', year='2026', who=_OUT)
                self._live_one(app, mother if winner == 'family' else outsider)
                if winner == 'family':
                    self.assertNotIn('str_not_household', _blockers(app))

    def test_2_the_familys_approval_takes_the_slot_from_an_outsiders_dated_approval(self):
        """Unchanged from round 3, now for the round-4 reason: the family's approval is MATCHED (tier
        2), the outsider's is not (tier 1)."""
        with self.subTest(order='outsider first'):
            app = _app()
            _live_str(app, 'father', status='Lulus', year='2026', who=_OUT)
            mother = _upload_str(app, 'mother', status='Lulus', year='')     # undated: "older" by rank
            self.assertEqual(_status(mother), 'unconfirmed')
            self._live_one(app, mother)
            self.assertNotIn('str_not_household', _blockers(app))
        with self.subTest(order='family first'):
            app = _app()
            mother = _live_str(app, 'mother', status='Lulus', year='')
            _upload_str(app, 'father', status='Lulus', year='2026', who=_OUT)
            self._live_one(app, mother)
            self.assertNotIn('str_not_household', _blockers(app))

    def test_3_an_approval_nobody_has_judged_yet_yields_to_a_newer_unread_page(self):
        """Reworked (round 3: "keeps tier two"). An approval no card has matched yet is tier 1, so a
        newer unread page under another member takes the slot — exactly the base order."""
        from apps.scholarship.income_engine import student_str_check
        from apps.scholarship.income_str_ownership import str_check_names_a_stranger, str_unjudged_members
        app = _app(ics=('father',))
        mother = _live_str(app, 'mother', status='Lulus', year='2026')
        sc = student_str_check(mother)
        self.assertEqual(str_unjudged_members(app, sc), ['mother'])
        self.assertIs(str_check_names_a_stranger(sc, app), False)
        father = _upload_str(app, 'father', status='', year='2026')
        self._live_one(app, father)

    def test_4_the_familys_unread_page_and_an_outsiders_rejection_rank_as_on_base(self):
        """Reworked (round 3: the family's page won in both orders). Both are tier 1: the base order."""
        for order, year, winner in (('outsider first', '2026', 'family'),
                                    ('outsider first', '', 'outsider'),     # dated beats undated
                                    ('family first', '2026', 'outsider')):  # same year, newer upload
            with self.subTest(order=order, year=year):
                app = _app()
                if order == 'outsider first':
                    outsider = _live_str(app, 'father', status='Ditolak', year='2026', who=_OUT)
                    self.assertEqual(_status(outsider), 'rejected')
                    mother = _upload_str(app, 'mother', status='', year=year)
                else:
                    mother = _live_str(app, 'mother', status='', year=year)
                    outsider = _upload_str(app, 'father', status='Ditolak', year='2026', who=_OUT)
                self._live_one(app, mother if winner == 'family' else outsider)


class Round4OnlyAMatchedApprovalHoldsTheSlot(TestCase):
    """Round 4 on the real upload path (``create_in_slot`` → ``upload_read.judge``)."""

    def _live_one(self, app, want):
        want.refresh_from_db()
        self.assertEqual(_live_strs(app), [want])

    def test_the_reproduction_the_familys_page_stays_live_when_the_mothers_ic_lands(self):
        """The adversary's round-4 case. The mother's IC is not on file (and, second, no IC at all), so
        the outsider's approval under the father is "not judged yet". On the base the mother's newer
        page of the same year took the slot; round 3 kept the outsider's copy (tier 2) and, once her IC
        landed, the case blocked on ``str_not_household`` with nothing to re-run the de-dupe."""
        for ics in (('father',), ()):
            with self.subTest(ics=ics):
                app = _app(ics=ics)
                outsider = _live_str(app, 'father', status='Lulus', year='2026', who=_OUT)
                self.assertEqual(_status(outsider), 'current')
                mother = _upload_str(app, 'mother', status='', year='2026')
                self.assertEqual(_status(mother), 'unreadable')
                self._live_one(app, mother)
                _add_ic(app, 'mother')
                self._live_one(app, mother)
                blockers = _blockers(app)
                self.assertNotIn('str_not_household', blockers)
                if ics == ('father',):
                    self.assertEqual(blockers, [], 'as on the base: amber, the family can submit')

    def test_a_matched_approval_holds_against_a_newer_unread_page(self):
        for year in ('2026', ''):
            with self.subTest(year=year):
                app = _app()
                father = _live_str(app, 'father', status='Lulus', year=year)
                mother = _upload_str(app, 'mother', status='', year='2026')
                self.assertEqual(_status(mother), 'unreadable')
                self._live_one(app, father)

    def test_a_matched_dashboard_approval_holds_against_a_newer_unmatched_approval(self):
        """TD-409 parity: the mother's IC is not on file, so her dated approval matches no card (tier
        1); the father's matched, undated dashboard approval (tier 2) holds although the base order
        (dated beats undated) would have let hers win."""
        app = _app(ics=('father',))
        father = _live_str(app, 'father', status='Lulus', year='', source_type='dashboard')
        self.assertEqual(_status(father), 'unconfirmed')
        mother = _upload_str(app, 'mother', status='Lulus', year='2026')
        self.assertEqual(_status(mother), 'current')
        self.assertNotIn('match', (_check(mother)['name_status'], _check(mother)['nric_status']))
        self._live_one(app, father)

    def test_an_unjudged_approval_still_holds_against_a_newer_not_approved_page(self):
        """Round 1's protection covers an approval nobody has matched yet: tier 1 beats tier 0."""
        for ics in ((), ('mother',)):
            with self.subTest(ics=ics):
                app = _app(ics=ics)
                father = _live_str(app, 'father', status='Lulus', year='2026')
                self.assertNotIn('match', (_check(father)['name_status'], _check(father)['nric_status']))
                mother = _upload_str(app, 'mother', status='Permohonan Diterima', year='2026')
                self.assertEqual(_status(mother), 'not_approved')
                self._live_one(app, father)

    def test_an_unjudged_approval_and_a_newer_unread_page_follow_the_base_order(self):
        """This equals the base (before TD-718): both tier 1, same year, so the newer upload wins."""
        for ics in ((), ('mother',)):
            with self.subTest(ics=ics):
                app = _app(ics=ics)
                _live_str(app, 'father', status='Lulus', year='2026')
                mother = _upload_str(app, 'mother', status='', year='2026')
                self._live_one(app, mother)


def _check(doc):
    from apps.scholarship.income_engine import student_str_check
    return student_str_check(doc)


class TheTierOfAnUnmatchedCopy(TestCase):
    """Round 4 unit rows (reworked from round 3's stranger rows): an approval is tier 2 only when a
    card matched it; a stranger's, an unjudged or a pending approval is tier 1; nothing else moves."""

    def _doc(self, app, status, who, year='2026'):
        name, nric = who
        return ApplicantDocument(application=app, doc_type='str', household_member='father',
                                 vision_fields=_fields(name, nric, status, year, 'semakan_status'))

    def test_every_state(self):
        """Reworked: round 3 expected tier 0 for every stranger row; now the stranger's tier is its
        state's (an approval 1, a rejection 1, an unread page 1)."""
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        app = _app()
        for status, year, state, own_tier in (('Lulus', '2026', 'current', 2), ('Lulus', '', 'unconfirmed', 2),
                                              ('Ditolak', '2026', 'rejected', 1), ('', '2026', 'unreadable', 1)):
            with self.subTest(state=state):
                stranger = self._doc(app, status, _OUT, year)
                self.assertEqual(_status(stranger), state)
                self.assertEqual(_dedup_str_rank(stranger), 1)
                own = self._doc(app, status, (FATHER, FATHER_NRIC), year)
                self.assertEqual(_dedup_str_rank(own), own_tier)

    def test_an_approval_nobody_could_match_is_tier_one(self):
        """Reworked: round 3 expected tier 2 ("keeps its tier"); without a match it is tier 1."""
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        app = _app(ics=())                                       # no IC on file: every field no_ref
        self.assertEqual(_dedup_str_rank(self._doc(app, 'Lulus', _OUT)), 1)
        self.assertEqual(_dedup_str_rank(self._doc(app, 'Lulus', (FATHER, FATHER_NRIC))), 1)
        app = _app()
        self.assertEqual(_dedup_str_rank(self._doc(app, 'Lulus', ('', ''))), 1)   # nothing read: no_ref

    def test_a_partial_check_or_no_application_never_raises(self):
        """Reworked: an approval with no 'match' on either field is tier 1 (round 3 said 2). Round 5: a
        mocked check that says 'match' is tier 1 too when the page itself (empty here) hits no card —
        that is the shape of a match borrowed through the IC-number chain."""
        from unittest import mock
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        mismatch = {'current_status': 'current', 'name_status': 'mismatch', 'nric_status': 'mismatch'}
        pending = {'current_status': 'current', 'name_status': 'no_ref', 'nric_status': 'no_ref',
                   'pending_our_read': True}
        matched = {'current_status': 'unconfirmed', 'name_status': 'no_ref', 'nric_status': 'match'}
        no_app = ApplicantDocument(doc_type='str', vision_fields={'fields': {}})       # nothing to judge against
        with_app = ApplicantDocument(application=_app(), doc_type='str', vision_fields={'fields': {}})
        for doc, ret, want in ((no_app, mismatch, 1), (no_app, {'current_status': 'current'}, 1),
                               (no_app, matched, 1), (no_app, {}, 0), (no_app, None, 0),
                               (with_app, {'current_status': 'current'}, 1),         # no name_status key
                               (with_app, pending, 1), (with_app, matched, 1),
                               (with_app, {}, 0), (with_app, None, 0)):
            with self.subTest(app=doc.application_id is not None, ret=ret), mock.patch(
                    'apps.scholarship.income_engine.str_route.student_str_check', return_value=ret):
                self.assertEqual(_dedup_str_rank(doc), want)

    # Round 5: the whole table and the parity test with ``promotion._str_matched`` moved to
    # ``Round5TheTierTable`` — tier 2 now also needs the page's OWN card hit, so it IMPLIES the same-slot
    # guard instead of equalling it (a chain-only match counts there, not here).

    def test_non_str_rank_is_unchanged(self):
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        app = _app()
        for dt in ('salary_slip', 'epf', 'water_bill', 'electricity_bill'):
            doc = ApplicantDocument(application=app, doc_type=dt, household_member='father',
                                    vision_fields=_fields(OUTSIDER, OUTSIDER_NRIC, '', '', ''))
            self.assertEqual(_dedup_str_rank(doc), 1)


_STATES = ('current', 'unconfirmed', 'rejected', 'unreadable', 'not_approved', 'wrong_type', 'stale',
           'future', 'unknown', '', None)
_MATCHES = ('match', 'mismatch', 'no_ref')


# ── Round 5: the tier-2 match must be the page's OWN ──────────────────────────────────────────
# The IC-number chain (#9) sets both statuses to 'match' when the birth certificate's parent number
# equals the NEWEST live STR's — another document. During the household de-dupe both copies are live,
# so an outsider's approval BORROWED the match from the family's newer page and buried it. Tier 2 now
# reads only the page's own name / NRIC against the household's IC cards.
def _add_bc(app):
    return ApplicantDocument.objects.create(
        application=app, doc_type='birth_certificate', storage_path='test/bc', household_member='',
        vision_run_at=timezone.now(),
        vision_fields={'fields': {'bc_child_name': STUDENT.upper(), 'bc_father_name': FATHER.upper(),
                                  'bc_father_nric': FATHER_NRIC, 'bc_mother_name': MOTHER.upper(),
                                  'bc_mother_nric': MOTHER_NRIC},
                       'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})


def _own_hit(doc):
    from apps.scholarship.income_engine.str_route import str_recipient_hits_a_household_card
    return str_recipient_hits_a_household_card(doc)


class Round5TheMatchIsThePagesOwn(TestCase):
    """Round 5 on the real upload path (``create_in_slot`` → ``upload_read.judge``)."""

    def _live_one(self, app, want):
        want.refresh_from_db()
        self.assertEqual(_live_strs(app), [want])

    def _outsider_then_father(self, app, alone):
        from apps.scholarship.income_engine.identity_checks import chain_verified_earner
        outsider = _live_str(app, 'mother', status='Lulus', year='2026', who=_OUT)
        sc = _check(outsider)
        self.assertEqual((sc['current_status'], sc['name_status'], sc['nric_status']), alone)
        father = _upload_str(app, 'father', status='', year='2026')
        self.assertEqual(_status(father), 'unreadable')
        self._live_one(app, father)
        self.assertIs(chain_verified_earner(app, 'father'), True, 'the chain truly fires')
        self.assertIs(_own_hit(outsider), False)
        return outsider, father

    def test_1_the_reproduction_an_outsiders_approval_never_borrows_the_chain(self):
        """The adversary's round-5 case. On tip 1cccf3f00 the outsider's copy read match / match (the
        chain, off the father's newer page) while both were live, took tier 2, buried the father's
        page and the case blocked on ``str_not_household``. On base f0631426a his page stayed live."""
        app = _app()
        _add_bc(app)
        self._outsider_then_father(app, ('current', 'mismatch', 'mismatch'))
        self.assertEqual(_blockers(app), [])

    def test_2_no_ic_on_file_the_base_order_decides(self):
        """No IC on file: the outsider's copy reads current / no_ref / no_ref alone. Both copies are
        tier 1 and of the same year, so the newer upload (the father's) wins — as on base f0631426a
        (verified by running this test against the base freshness.py)."""
        app = _app(ics=())
        _add_bc(app)
        self._outsider_then_father(app, ('current', 'no_ref', 'no_ref'))
        self.assertNotIn('str_not_household', _blockers(app))

    def test_3_control_without_a_birth_certificate(self):
        app = _app()
        outsider = _live_str(app, 'mother', status='Lulus', year='2026', who=_OUT)
        father = _upload_str(app, 'father', status='', year='2026')
        self._live_one(app, father)
        self.assertIs(_own_hit(outsider), False)
        self.assertNotIn('str_not_household', _blockers(app))

    def test_4_the_familys_own_approval_with_a_bc_still_holds_the_slot(self):
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        for ics in (('father', 'mother'), ('father',)):
            with self.subTest(ics=ics):
                app = _app(ics=ics)
                _add_bc(app)
                father = _live_str(app, 'father', status='Lulus', year='2026')
                self.assertIs(_own_hit(father), True)
                self.assertEqual(_dedup_str_rank(father), 2)
                mother = _upload_str(app, 'mother', status='', year='2026')
                self.assertEqual(_status(mother), 'unreadable')
                self._live_one(app, father)

    def test_5_a_chain_only_match_is_tier_one_and_still_beats_a_failing_page(self):
        """The #9 shape: the mother's card sits in the father's slot, so the father's own page matches
        no card; the BC's father number equals the page's, so the chain reads match / match. That
        borrowed match is tier 1 (the TD-409 same-slot guard still counts it), and tier 1 still beats a
        newer received page (0) under the mother — whoever that page names."""
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        from apps.scholarship.promotion import _str_matched
        for who in (None, (FATHER, FATHER_NRIC)):
            with self.subTest(mother_page_names=who or 'mother'):
                app = _app(ics=())
                ApplicantDocument.objects.create(
                    application=app, doc_type='parent_ic', storage_path='test/ic/father/wrong',
                    household_member='father', vision_name=MOTHER.upper(), vision_nric=MOTHER_NRIC,
                    vision_run_at=timezone.now())
                _add_bc(app)
                father = _live_str(app, 'father', status='Lulus', year='2026')
                sc = _check(father)
                self.assertEqual((sc['current_status'], sc['name_status'], sc['nric_status']),
                                 ('current', 'match', 'match'))
                self.assertIs(_own_hit(father), False)
                self.assertIs(_str_matched(father, counting=True), True)
                self.assertEqual(_dedup_str_rank(father), 1)
                mother = _upload_str(app, 'mother', status='Permohonan Diterima', year='2026', who=who)
                self.assertEqual(_status(mother), 'not_approved')
                self._live_one(app, father)


class Round5TheOwnCardHelper(TestCase):
    """``str_recipient_hits_a_household_card`` — pure, the page's own fields only."""

    def test_it_never_raises_and_reads_only_the_page(self):
        app = _app()
        for doc, want in (
                (ApplicantDocument(doc_type='str', vision_fields={'fields': {}}), False),       # no application
                (ApplicantDocument(doc_type='str', vision_fields=None), False),
                (ApplicantDocument(application=app, doc_type='str', vision_fields=None), False),
                (ApplicantDocument(application=app, doc_type='str', vision_fields={'fields': {}}), False),
                (ApplicantDocument(application=app, doc_type='salary_slip',
                                   vision_fields=_fields(FATHER, FATHER_NRIC, '', '', '')), False),
                (ApplicantDocument(application=app, doc_type='str', household_member='mother',
                                   vision_fields=_fields(FATHER, FATHER_NRIC, 'Lulus', '', '')), True),
                (ApplicantDocument(application=app, doc_type='str',
                                   vision_fields=_fields(OUTSIDER, FATHER_NRIC, 'Lulus', '', '')), True),
                (ApplicantDocument(application=app, doc_type='str',
                                   vision_fields=_fields(FATHER, OUTSIDER_NRIC, 'Lulus', '', '')), True),
                (ApplicantDocument(application=app, doc_type='str',
                                   vision_fields=_fields(OUTSIDER, OUTSIDER_NRIC, 'Lulus', '', '')), False)):
            with self.subTest(doc_type=doc.doc_type, fields=doc.vision_fields):
                self.assertIs(_own_hit(doc), want)

    def test_the_check_payload_has_no_new_key(self):
        app = _app()
        doc = _live_str(app, 'father', status='Lulus', year='2026')
        self.assertEqual(set(_check(doc)), {
            'name', 'nric', 'status', 'year', 'member', 'name_status', 'nric_status', 'current_status',
            'ic_present', 'pending_our_read', 'ic_read_members'})


class Round5TheTierTable(SimpleTestCase):
    """Tier 2 = an approval whose check matched AND whose own page hits a card. It is now STRICTER than
    ``promotion._str_matched(doc, counting=True)`` (the same idea, minus the chain)."""

    def _rank(self, doc, ret, own):
        from unittest import mock
        from apps.scholarship.income_engine.freshness import _dedup_str_rank
        with mock.patch('apps.scholarship.income_engine.str_route.student_str_check', return_value=ret), \
                mock.patch('apps.scholarship.income_engine.str_route.str_recipient_hits_a_household_card',
                           return_value=own):
            return _dedup_str_rank(doc)

    def _table(self):
        for state in _STATES:
            for name_status in _MATCHES:
                for nric_status in _MATCHES:
                    for own in (True, False):
                        yield {'current_status': state, 'name_status': name_status,
                               'nric_status': nric_status}, own

    def test_the_whole_table(self):
        doc = ApplicantDocument(doc_type='str', vision_fields={'fields': {}})
        for ret, own in self._table():
            if ret['current_status'] in ('current', 'unconfirmed'):
                matched = 'match' in (ret['name_status'], ret['nric_status'])
                want = 2 if (matched and own) else 1
            else:
                want = 1 if ret['current_status'] in ('rejected', 'unreadable') else 0
            with self.subTest(ret=ret, own=own):
                self.assertEqual(self._rank(doc, ret, own), want)

    def test_tier_two_implies_the_same_slot_guard(self):
        from unittest import mock
        from apps.scholarship.promotion import _str_matched
        doc = ApplicantDocument(doc_type='str', vision_fields={'fields': {}})
        for ret, own in self._table():
            with self.subTest(ret=ret, own=own):
                if self._rank(doc, ret, own) != 2:
                    continue
                with mock.patch('apps.scholarship.income_engine.student_str_check', return_value=ret):
                    self.assertIs(_str_matched(doc, counting=True), True)

    def test_a_chain_only_match_is_tier_one(self):
        doc = ApplicantDocument(doc_type='str', vision_fields={'fields': {}})
        for state in ('current', 'unconfirmed'):
            with self.subTest(state=state):
                ret = {'current_status': state, 'name_status': 'match', 'nric_status': 'match'}
                self.assertEqual(self._rank(doc, ret, False), 1)
                self.assertEqual(self._rank(doc, ret, True), 2)


# ── R7: two rejection wordings that read as approved ──────────────────────────────────────────
class TheRejectionWordings(SimpleTestCase):
    def test_the_ladder(self):
        from apps.scholarship.income_engine import _str_currency
        for status, want in (('Tidak Diluluskan', 'rejected'), ('tidak  diluluskan', 'rejected'),
                             ('Not Approved', 'rejected'), ('NOT APPROVED', 'rejected'),
                             ('Diluluskan', 'current'), ('Approved', 'current'), ('Lulus', 'current'),
                             ('Lulus Rayuan', 'current'), ('Kekal Kelulusan Asal', 'current')):
            with self.subTest(status=status):
                self.assertEqual(_str_currency(status, '2026', 2026, 'semakan_status'), want)

    def test_the_reader_stores_the_whole_rejection_phrase(self):
        from apps.scholarship.income_engine import _str_currency
        from apps.scholarship.tests.test_td718_str_not_approved import (
            _desktop_columns, _desktop_rows, _mobile)
        # _desktop_columns is the labels-then-values layout (#104): the body scan reads the status, and
        # the line just above it is Status Pedalaman's value "Tidak" — so "Lulus" there must NOT read
        # "Tidak Lulus" (the rejection phrase is matched on one line only). _desktop_rows is one row.
        for layout in (_desktop_columns, _desktop_rows, _mobile):
            for word, stored, want in (('Tidak Lulus', 'tidak lulus', 'rejected'),
                                       ('Tidak Diluluskan', 'tidak diluluskan', 'rejected'),
                                       ('Lulus', 'lulus', 'current'),
                                       ('Diluluskan', 'diluluskan', 'current'),
                                       ('Kekal Kelulusan Asal', 'kekal kelulusan asal', 'current'),
                                       ('Ditolak', 'ditolak', 'rejected'),
                                       ('Tidak Layak', 'tidak layak', 'rejected')):
                if layout is _desktop_columns and word in ('Tidak Lulus', 'Tidak Diluluskan'):
                    # Round 3 (B3): a body-scan "Tidak (Di)Lulus(kan)" on a page with a Status Pedalaman
                    # label cannot be told from Pedalaman's "Tidak" beside "Lulus" → no status, amber.
                    stored, want = '', 'unreadable'
                with self.subTest(layout=layout.__name__, word=word):
                    f = parse_by_labels('str', layout(word))
                    got = ' '.join((f.get('status') or '').lower().split())
                    self.assertEqual(got.replace('ⓘ', '').strip(), stored)
                    self.assertEqual(_str_currency(f['status'], '2026', 2026, f.get('source_type')), want)


# ── R2: a body "berjaya" ──────────────────────────────────────────────────────────────────────
_LABELLED_RECEIVED = '\n'.join([
    'Semakan Status', 'Maklumat Pemohon', 'Nama', MOTHER.upper(), 'No. MyKad', MOTHER_NRIC.replace('-', ''),
    'Status Permohonan Semasa', 'Permohonan Diterima', '- Permohonan akan diproses pada Disember 2026',
    'Permohonan anda telah berjaya dihantar.', 'Kembali']) + '\n'


class ABodyBerjayaNeverOverridesAPendingValue(SimpleTestCase):
    def _read(self, text):
        return parse_by_labels('str', text)

    def test_a_labelled_received_value_with_a_berjaya_sentence_reads_not_approved(self):
        from apps.scholarship.income_engine import _str_currency
        f = self._read(_LABELLED_RECEIVED)
        self.assertEqual(f.get('status'), 'Permohonan Diterima')
        self.assertEqual(_str_currency(f['status'], '2026', 2026, f.get('source_type')), 'not_approved')

    def test_a_decided_body_token_still_overrides_as_today(self):
        for token, want in (('Lulus', 'current'), ('Diluluskan', 'current'),
                            ('Kekal Kelulusan Asal', 'current'), ('Ditolak', 'rejected'),
                            ('Tidak Layak', 'rejected'), ('Gagal', 'rejected')):
            with self.subTest(token=token):
                from apps.scholarship.income_engine import _str_currency
                text = _LABELLED_RECEIVED.replace('Kembali', f'Keputusan: {token}\nKembali')
                f = self._read(text)
                self.assertNotEqual(f.get('status'), 'Permohonan Diterima')
                self.assertEqual(_str_currency(f['status'], '2026', 2026, f.get('source_type')), want)


_APPLICATION_PAGE = '\n'.join([
    'MySTR', 'Maklumat Pemohon', 'No. MyKad', MOTHER_NRIC.replace('-', ''), 'Nama', MOTHER.upper(),
    'Umur', '51', 'Jantina', 'Perempuan', 'Status Perkahwinan', 'Berkahwin', 'Alamat',
    '12 Jalan Contoh 3', 'Poskod', '43000', 'Bandar', 'Kajang', 'Negeri', 'Selangor',
    'Permohonan anda telah berjaya dihantar.']) + '\n'


class AnApplicationPageSaysSent(SimpleTestCase):
    def test_berjaya_dihantar_does_not_keep_the_page_out_of_the_signature(self):
        from apps.scholarship.str_application_page import is_application_details
        self.assertIs(is_application_details(_APPLICATION_PAGE), True)
        self.assertEqual(parse_by_labels('str', _APPLICATION_PAGE).get('source_type'), 'unknown')

    def test_a_decided_word_still_keeps_it_out(self):
        from apps.scholarship.str_application_page import is_application_details
        for word in ('Lulus', 'Diluluskan', 'Ditolak'):
            with self.subTest(word=word):
                self.assertIs(is_application_details(_APPLICATION_PAGE + word + '\n'), False)


# ── R3: the strict approved words ─────────────────────────────────────────────────────────────
class TheStrictApprovedWords(SimpleTestCase):
    def test_the_ladder(self):
        from apps.scholarship.income_engine import _str_currency
        for status, want in (
                ('Dalam Proses Kelulusan', 'not_approved'),
                ('Menunggu Kelulusan', 'unreadable'),       # "Menunggu" is not a pending word
                ('Tidak Lulus', 'rejected'),
                ('TIDAK   LULUS', 'rejected'),
                ('Lulus (Dalam Proses Bayaran)', 'current'),
                ('Lulus Rayuan', 'current'),
                ('Lulus', 'current'),
                ('Diluluskan', 'current'),
                ('Kekal  Kelulusan\nAsal', 'current'),         # any whitespace
                ('Approved', 'current'),
                ('Kelulusan', 'unreadable'),                  # no whole-word Lulus
                ('Ditolak', 'rejected')):
            with self.subTest(status=status):
                self.assertEqual(_str_currency(status, '2026', 2026, 'semakan_status'), want)


# ── R4: Unicode spaces around an application page label ───────────────────────────────────────
class TheLabelsAllowUnicodeSpaces(SimpleTestCase):
    def test_a_no_break_or_other_horizontal_space_still_reads_a_label(self):
        from apps.scholarship.str_application_page import is_application_details
        for sp in ('\xa0', '\u2007', '\u202f', '\u3000', '\t'):
            with self.subTest(space=repr(sp)):
                text = '\n'.join(['Maklumat Pemohon', f'Umur{sp}:{sp}51', f'{sp}Jantina{sp}: Perempuan',
                                  f'Status{sp}Perkahwinan{sp}', 'Berkahwin', f'Poskod{sp}:43000']) + '\n'
                self.assertIs(is_application_details(text), True)

    def test_a_line_break_is_never_a_label_space(self):
        from apps.scholarship.str_application_page import is_application_details
        # each "label" split over two lines is not a label line: fewer than three labels
        text = 'Maklumat Pemohon\nUmur\n:\n51\nJantina Perempuan Lelaki\nPoskod 43000 Kajang\n'
        self.assertIs(is_application_details(text), False)
