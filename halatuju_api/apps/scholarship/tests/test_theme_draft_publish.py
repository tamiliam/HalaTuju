"""Layer 1 A3 — changing a colour stops being a live experiment on applicants.

Before this, saving a colour changed it for everyone instantly and there was no undo: the previous
hex was simply gone. Now there is a draft nobody but the editor sees, a publish that is the moment
applicants see something new, and a revert that puts back what was live before.

The first test in this file is the one that matters. Everything else is the lifecycle around it.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses import theme_tokens, theme_versions
from apps.courses.models import OrganisationTheme, PartnerAdmin, PartnerOrganisation

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/scholarship/organisation/theme/'
PUBLISH = URL + 'publish/'
REVERT = URL + 'revert/'

GOOD = '#a21caf'        # purple — passes every contrast pair
TEAL = '#0f766e'
UNREADABLE = '#facc15'  # yellow — fails the text pairs


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDraftPublishRevert(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='alpha', name='Alpha Foundation')
        PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OrgAdmin A', email='oaa@x.com')
        PartnerAdmin.objects.create(
            supabase_user_id='rev-a', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Reviewer A', email='reva@x.com')

    def setUp(self):
        self.client = APIClient()
        self._auth('oa-a')

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _draft(self, colour):
        return self.client.put(URL, {'colour': colour}, format='json')

    def _served_theme(self):
        """What the PUBLIC branding endpoint hands a VISITOR's browser.

        ⚠ A FRESH, ANONYMOUS CLIENT — not `self.client`, which is carrying the org_admin's token.
        Reusing it asked "what does a signed-in administrator get", which is a different question
        and is also refused by the NRIC gate. The claim being tested is about a student's browser,
        so the request has to look like one.
        """
        anon = APIClient()
        r = anon.get(f'/api/v1/branding/{self.org.code}/')
        self.assertEqual(r.status_code, 200)
        return r.json()['theme']

    # ── the one that matters most ────────────────────────────────────────────────────────────
    def test_a_draft_never_reaches_a_visitor(self):
        """If this fails, an unpublished experiment is being served to applicants.

        It drives the PUBLIC branding endpoint — the thing the web app actually calls — rather than
        the admin payload, because the admin screen is supposed to see the draft. The question here
        is what a student's browser gets, and the answer must be nothing until somebody publishes.
        """
        self._draft(GOOD)
        self.assertIsNone(self._served_theme())

        self.client.post(PUBLISH, {}, format='json')
        self.assertEqual(self._served_theme()['light']['brand-500'], '162 28 175')

    def test_a_second_draft_does_not_disturb_what_is_live(self):
        self._draft(GOOD)
        self.client.post(PUBLISH, {}, format='json')
        self._draft(TEAL)
        # Still the PUBLISHED purple, not the drafted teal.
        self.assertEqual(self._served_theme()['light']['brand-500'], '162 28 175')

    # ── publish ──────────────────────────────────────────────────────────────────────────────
    def test_publishing_makes_the_draft_live_and_clears_the_draft(self):
        self._draft(GOOD)
        body = self.client.post(PUBLISH, {}, format='json').json()
        self.assertEqual(body['live']['colour'], GOOD)
        self.assertIsNone(body['draft'])
        self.assertTrue(body['published_at'])
        self.assertEqual(body['published_by'], 'oaa@x.com')

    def test_publishing_with_no_draft_is_refused(self):
        r = self.client.post(PUBLISH, {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'no_draft')

    def test_publishing_archives_the_previous_version_rather_than_overwriting_it(self):
        # Keeping it is the whole reason Revert can work at all.
        self._draft(GOOD)
        self.client.post(PUBLISH, {}, format='json')
        self._draft(TEAL)
        body = self.client.post(PUBLISH, {}, format='json').json()
        self.assertEqual(body['live']['colour'], TEAL)
        self.assertEqual(body['previous_colour'], GOOD)
        self.assertEqual(OrganisationTheme.objects.filter(organisation=self.org).count(), 2)

    def test_only_ONE_version_is_ever_live(self):
        for colour in (GOOD, TEAL, '#1e3a8a'):
            self._draft(colour)
            self.client.post(PUBLISH, {}, format='json')
        self.assertEqual(
            OrganisationTheme.objects.filter(organisation=self.org, status='active').count(), 1)

    # ── revert ───────────────────────────────────────────────────────────────────────────────
    def test_revert_puts_back_the_colour_that_was_live_before(self):
        self._draft(GOOD)
        self.client.post(PUBLISH, {}, format='json')
        self._draft(TEAL)
        self.client.post(PUBLISH, {}, format='json')

        body = self.client.post(REVERT, {}, format='json').json()
        self.assertEqual(body['live']['colour'], GOOD)
        self.assertEqual(self._served_theme()['light']['brand-500'], '162 28 175')

    def test_reverting_the_FIRST_colour_lands_on_the_platform_default(self):
        # A real outcome, not an error: it is genuinely what they had before, and it is how a
        # tenant gets all the way back to the stylesheet.
        self._draft(GOOD)
        self.client.post(PUBLISH, {}, format='json')
        body = self.client.post(REVERT, {}, format='json').json()
        self.assertIsNone(body['live'])
        self.assertIsNone(body['tokens'])
        self.assertIsNone(self._served_theme())

    def test_revert_with_nothing_live_is_refused(self):
        r = self.client.post(REVERT, {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'nothing_live')

    def test_revert_twice_walks_back_and_forth_correctly(self):
        # A version can be published, archived and republished, so the undo has to point at what
        # was live MOST RECENTLY — which is why `previous_for` orders by archived_at, not created.
        self._draft(GOOD)
        self.client.post(PUBLISH, {}, format='json')
        self._draft(TEAL)
        self.client.post(PUBLISH, {}, format='json')
        self.client.post(REVERT, {}, format='json')                 # back to purple
        body = self.client.post(REVERT, {}, format='json').json()   # and back again, to teal
        self.assertEqual(body['live']['colour'], TEAL)

    # ── who may, and what is refused ─────────────────────────────────────────────────────────
    def test_a_reviewer_may_not_publish_or_revert(self):
        self._draft(GOOD)
        self._auth('rev-a')
        self.assertEqual(self.client.post(PUBLISH, {}, format='json').status_code, 403)
        self.assertEqual(self.client.post(REVERT, {}, format='json').status_code, 403)

    def test_an_unreadable_colour_cannot_even_become_a_draft(self):
        # Refused where it is typed, not saved and refused later — a draft that can never be
        # published is a trap somebody walks into twice.
        r = self._draft(UNREADABLE)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'unreadable')
        self.assertFalse(OrganisationTheme.objects.filter(organisation=self.org).exists())


class TestTheServiceFailsClosed(TestCase):
    """publish and revert default allowed=False, copied from sponsor_terms.publish for the same
    reason: a shell caller or a future endpoint that forgets the role gate must fail closed."""

    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='alpha', name='Alpha')

    def test_a_shell_caller_that_forgets_the_gate_publishes_nothing(self):
        theme_versions.save_draft(self.org, GOOD, theme_tokens.tokens_from_colour(GOOD))
        with self.assertRaises(theme_versions.ThemeVersionError) as ctx:
            theme_versions.publish(self.org)          # note: no allowed=True
        self.assertEqual(ctx.exception.code, 'not_allowed')
        self.assertIsNone(OrganisationTheme.active_for(self.org))

    def test_the_same_for_revert(self):
        theme_versions.save_draft(self.org, GOOD, theme_tokens.tokens_from_colour(GOOD))
        theme_versions.publish(self.org, allowed=True)
        with self.assertRaises(theme_versions.ThemeVersionError) as ctx:
            theme_versions.revert(self.org)
        self.assertEqual(ctx.exception.code, 'not_allowed')
        self.assertIsNotNone(OrganisationTheme.active_for(self.org))

    def test_a_draft_and_an_active_can_coexist_but_never_two_of_either(self):
        theme_versions.save_draft(self.org, GOOD, theme_tokens.tokens_from_colour(GOOD))
        theme_versions.publish(self.org, allowed=True)
        theme_versions.save_draft(self.org, TEAL, theme_tokens.tokens_from_colour(TEAL))
        self.assertEqual(OrganisationTheme.objects.filter(organisation=self.org).count(), 2)
        self.assertEqual(theme_versions.active_for(self.org).source_colour, GOOD)
        self.assertEqual(theme_versions.draft_for(self.org).source_colour, TEAL)

    def test_saving_a_draft_twice_updates_the_same_row(self):
        theme_versions.save_draft(self.org, GOOD, theme_tokens.tokens_from_colour(GOOD))
        theme_versions.save_draft(self.org, TEAL, theme_tokens.tokens_from_colour(TEAL))
        self.assertEqual(OrganisationTheme.objects.filter(organisation=self.org).count(), 1)
        self.assertEqual(theme_versions.draft_for(self.org).source_colour, TEAL)
