"""The Layer 0 seam agrees with the code it will eventually replace.

This sprint is deliberately inert: nothing calls `requirements.py` to make a decision, and the
literals it mirrors are still live in `services.py`. That is what makes these tests possible —
both sides exist at once and can be compared. Sprint 3 deletes one side, and by then this file is
the record of what the two agreed on.

⚠ The strongest evidence in this sprint is NOT in this file. It is the rest of the suite passing
UNMODIFIED. A new test proves the new thing works; only the old tests prove nothing else moved.
"""
from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import PartnerOrganisation
from .. import requirements
from ..models import (
    ApplicantDocument, ApplicationItem, Programme, ProgrammeApplicationItem,
)


def seed():
    call_command('seed_application_catalogue', verbosity=0)


class TestCatalogueIntegrity(TestCase):
    """Rules that make 'catalogue, not form builder' true rather than merely stated."""

    def setUp(self):
        seed()

    def test_every_document_code_is_a_real_doc_type_or_a_declared_aggregate(self):
        # THE rule of Layer 0. A document the engine cannot recognise is a blob a human must
        # read, so the catalogue may only NAME types that already exist. The one exception is
        # declared explicitly and cannot grow silently, because this test would fail.
        known = {c for c, _ in ApplicantDocument.DOC_TYPES} | requirements.DOCUMENT_AGGREGATES
        codes = set(ApplicationItem.objects.filter(kind='document')
                    .values_list('code', flat=True))
        self.assertEqual(codes - known, set())

    def test_the_only_aggregate_is_the_income_route(self):
        # Pinning the exception itself: if someone adds a second aggregate, they have to come
        # here and argue for it rather than quietly widen a frozenset.
        self.assertEqual(requirements.DOCUMENT_AGGREGATES, frozenset({'income_proof'}))

    def test_every_item_label_key_RESOLVES_in_the_message_catalogue(self):
        """Every catalogue label names a string that actually exists, in the file the app reads.

        ⚠ THIS TEST USED TO CHECK THE SHAPE OF THE KEY, AND THAT IS WHY IT MISSED THE REAL BUG.
        It asserted `label_key.startswith('apply.')` and no spaces — a stand-in for "looks like an
        i18n key" — and passed for two sprints while all nineteen keys pointed at an `apply.*`
        namespace **that did not exist in any message file**. `scripts/check-i18n.js` could not see
        it either: it compares the three catalogues against each other and against the source tree,
        and a key held in a DATABASE ROW is in neither. So the one guard that could have caught it
        was the one checking the wrong property. (TD-197.)

        Reading `en.json` from Python is the same cross-runtime trick `test_subject_drift.py` uses
        to pin `academic_engine._SUBJECT_BM` against `subjects.ts` — same repo, so the backend can
        simply open the front end's file and stop guessing.

        Only `en.json` is read: `check-i18n.js` already enforces that ms and ta carry every key en
        does, so existence in en plus that parity check covers all three without a second reader.
        """
        import json
        from pathlib import Path
        messages = Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src' / 'messages' / 'en.json'
        self.assertTrue(messages.exists(), f'cannot find the message catalogue at {messages}')
        catalogue = json.loads(messages.read_text(encoding='utf-8'))

        def resolve(dotted):
            node = catalogue
            for part in dotted.split('.'):
                if not isinstance(node, dict) or part not in node:
                    return None
                node = node[part]
            return node if isinstance(node, str) else None

        missing = [f'{i.kind}:{i.code} -> {i.label_key}'
                   for i in ApplicationItem.objects.all() if resolve(i.label_key) is None]
        self.assertEqual(missing, [], 'catalogue labels with no message behind them')

    def test_the_core_floor_is_exactly_what_the_owner_named(self):
        # Owner, 2026-07-28: identity card, results slip, consent, the family/income block —
        # "those listed and offer letter". Written down so a later sprint cannot quietly widen
        # or narrow a POLICY decision that was not its to make.
        core = {f'{i.kind}:{i.code}' for i in ApplicationItem.objects.filter(is_core=True)}
        self.assertEqual(core, {
            'document:ic', 'document:results_slip', 'document:offer_letter',
            'document:income_proof', 'question:family_roster', 'question:consent',
        })

    def test_seeding_twice_changes_nothing(self):
        before = list(ApplicationItem.objects.values_list('kind', 'code', 'is_core',
                                                          'default_state').order_by('kind', 'code'))
        seed()
        after = list(ApplicationItem.objects.values_list('kind', 'code', 'is_core',
                                                         'default_state').order_by('kind', 'code'))
        self.assertEqual(before, after)


class TestSeamMatchesTodaysBehaviour(TestCase):
    """The seam must resolve to what `services.py` hard-codes, or Sprint 3 ships a behaviour change
    wearing a "no change" label."""

    def setUp(self):
        seed()
        self.org = PartnerOrganisation.objects.create(code='seam-org', name='Seam Org')
        self.programme = Programme.objects.create(
            organisation=self.org, code='seam-programme', name_en='Seam Programme')

    def test_required_documents_match_the_submission_gate(self):
        # `services.application_completeness`, not-yet-submitted branch:
        #     {'ic', 'results_slip', 'offer_letter'}.issubset(present)
        #     and not income_doc_blockers(application)
        # The income route is one catalogue item, so the seam's set is those three plus it.
        app = _stub(self.programme)
        self.assertEqual(
            requirements.required_documents(app),
            {'ic', 'results_slip', 'offer_letter', 'income_proof'},
        )

    def test_optional_documents_match_the_student_UI(self):
        """What the student Documents tab actually offers.

        ⚠ CHANGED IN SPRINT 3b, and not because a policy moved. The original version of this test
        was written against `OTHER_OPTIONAL_DOC_TYPES` in halatuju-web/src/lib/scholarship.ts, and
        that constant was itself incomplete: the tab renders a `school_leaving_cert` card which
        appears in neither list. Reading one description of the UI and calling it the UI is how
        the omission survived — the card is in the JSX, and only the JSX was ever authoritative.

        `offer_letter` is absent because the 2026-06-05 gate promoted it to compulsory for every
        route; it is required, not optional.
        """
        app = _stub(self.programme)
        self.assertEqual(
            requirements.optional_documents(app),
            {'water_bill', 'electricity_bill', 'statement_of_intent', 'photo',
             'school_leaving_cert'},
        )

    def test_required_questions_match_the_completeness_parts(self):
        app = _stub(self.programme)
        self.assertEqual(
            requirements.required_questions(app),
            {'aspirations', 'plans', 'daily_life', 'fears',
             'family_roster', 'funding', 'address', 'consent'},
        )

    def test_the_no_programme_fallback_says_the_same_as_the_catalogue(self):
        """The two descriptions of "what BrightPath asks for" must agree.

        `PLATFORM_REQUIRED_*` and the seed lists are written in different files and are the same
        claim twice. The first draft proved why that needs a test rather than a comment: the
        fallback omitted `consent`, which the catalogue had as core, so an application with no
        programme would have skipped a LEGAL requirement while one with a programme enforced it.
        A comment saying "keep these in step" would not have caught it; this does.
        """
        app_with = _stub(self.programme)
        self.assertEqual(
            requirements.required_documents(app_with),
            set(requirements.PLATFORM_REQUIRED_DOCUMENTS),
        )
        self.assertEqual(
            requirements.optional_documents(app_with),
            set(requirements.PLATFORM_OPTIONAL_DOCUMENTS),
        )
        self.assertEqual(
            requirements.required_questions(app_with),
            set(requirements.PLATFORM_REQUIRED_QUESTIONS),
        )
        self.assertEqual(
            requirements.optional_questions(app_with),
            set(requirements.PLATFORM_OPTIONAL_QUESTIONS),
        )

    def test_an_application_with_no_programme_falls_back_to_todays_behaviour(self):
        # The most dangerous branch in the module. Legacy rows and bare test fixtures have no
        # programme; returning "asks for nothing" would silently open every gate for exactly
        # those applications, and it would look like everything passing.
        self.assertEqual(
            requirements.required_documents(_stub(None)),
            {'ic', 'results_slip', 'offer_letter', 'income_proof'},
        )
        self.assertIn('consent', requirements.required_questions(_stub(None)))


class TestEmptyCatalogueCannotOpenTheGates(TestCase):
    """The near-miss this sprint produced, pinned so it cannot recur.

    **What was almost shipped.** Production carries 143 applications, every one of them with a
    programme, and the catalogue tables were empty because seeding had been deferred on the
    grounds that nothing read them yet. The first cut of `resolve()` took "programme present" as
    licence to trust the catalogue, so it returned `{}` — and `documents_done` became
    `set().issubset(present)`, which is vacuously true. All 60 applications inside the submission
    gate could have submitted with no documents whatsoever.

    **Why the suite did not catch it.** No fixture seeds the catalogue, so ~5000 tests exercised
    the fallback branch and none exercised the branch that mattered. They passed for the wrong
    reason, which is indistinguishable from passing for the right one.

    These tests are written from the shape of PRODUCTION — programme set, catalogue empty — rather
    than from what the code was meant to do.
    """

    def setUp(self):
        # Deliberately NOT seeded. This is production's exact state at the moment of writing.
        self.org = PartnerOrganisation.objects.create(code='empty-org', name='Empty Org')
        self.programme = Programme.objects.create(
            organisation=self.org, code='empty-programme', name_en='Empty Programme')

    def test_an_empty_catalogue_still_requires_everything(self):
        self.assertEqual(ApplicationItem.objects.count(), 0)
        app = _stub(self.programme)
        self.assertEqual(
            requirements.required_documents(app),
            {'ic', 'results_slip', 'offer_letter', 'income_proof'},
        )

    def test_an_empty_catalogue_still_asks_for_each_gate(self):
        # The four `asks_for` calls the gates in services.py depend on. If any returns False the
        # corresponding gate silently stops running.
        app = _stub(self.programme)
        for code in ('ic', 'results_slip', 'offer_letter', 'income_proof'):
            self.assertTrue(requirements.asks_for(app, 'document', code), code)

    def test_a_catalogue_with_only_QUESTIONS_still_requires_documents(self):
        # Half-seeded is a real state — a partial seed, or a kind added in a later sprint. The
        # fallback is per KIND for exactly this reason.
        ApplicationItem.objects.create(kind='question', code='aspirations',
                                       label_key='apply.questions.aspirations.title',
                                       default_state='required')
        app = _stub(self.programme)
        self.assertEqual(
            requirements.required_documents(app),
            {'ic', 'results_slip', 'offer_letter', 'income_proof'},
        )

    def test_the_fallback_stops_the_moment_the_catalogue_has_documents(self):
        # And the converse: once documents ARE seeded, the catalogue governs — otherwise the
        # fallback would quietly override every configuration an organisation ever makes.
        seed()
        ApplicationItem.objects.filter(kind='document', code='photo').update(is_active=False)
        self.assertNotIn('photo', requirements.resolve(_stub(self.programme), 'document'))


class TestProgrammeSelection(TestCase):
    def setUp(self):
        seed()
        self.org = PartnerOrganisation.objects.create(code='sel-org', name='Sel Org')
        self.programme = Programme.objects.create(
            organisation=self.org, code='sel-programme', name_en='Sel Programme')

    def _set(self, kind, code, state):
        item = ApplicationItem.objects.get(kind=kind, code=code)
        ProgrammeApplicationItem.objects.update_or_create(
            programme=self.programme, item=item, defaults={'state': state})

    def test_a_programme_can_switch_a_non_core_document_off(self):
        self._set('document', 'water_bill', 'off')
        app = _stub(self.programme)
        self.assertFalse(requirements.asks_for(app, 'document', 'water_bill'))
        self.assertNotIn('water_bill', requirements.optional_documents(app))

    def test_a_programme_can_promote_an_optional_document_to_required(self):
        self._set('document', 'water_bill', 'required')
        self.assertIn('water_bill', requirements.required_documents(_stub(self.programme)))

    def test_a_core_item_cannot_be_switched_off_even_by_an_explicit_row(self):
        # The floor lives in the seam, not only in the UI and the API. A row can arrive from a
        # migration, a fixture or a future bulk edit, none of which pass through either of those.
        self._set('document', 'ic', 'off')
        app = _stub(self.programme)
        self.assertIn('ic', requirements.required_documents(app))
        self.assertTrue(requirements.asks_for(app, 'document', 'ic'))

    def test_one_programme_s_choice_does_not_leak_to_another(self):
        other = Programme.objects.create(
            organisation=self.org, code='other-programme', name_en='Other')
        self._set('document', 'water_bill', 'off')
        self.assertFalse(requirements.asks_for(_stub(self.programme), 'document', 'water_bill'))
        self.assertTrue(requirements.asks_for(_stub(other), 'document', 'water_bill'))

    def test_an_inactive_catalogue_item_disappears_entirely(self):
        ApplicationItem.objects.filter(kind='document', code='photo').update(is_active=False)
        self.assertNotIn('photo', requirements.resolve(_stub(self.programme), 'document'))


class _Stub:
    """A minimal stand-in for an application.

    The gates in `services.py` are full of partially-built objects, so the seam must read its
    programme defensively rather than assume a full model instance.
    """
    def __init__(self, programme):
        self.programme = programme


def _stub(programme):
    return _Stub(programme)
