"""Layer 1 A1 — a tenant's colours are stored, and the fence around them holds.

Three things are being pinned here, in order of how badly it would matter if they broke:

1. **A tone is never a tenant's.** The four tone families and the category family carry the
   product's own meanings. `test_a_tone_is_never_a_tenants` asserts that INDEPENDENTLY of the
   allow-list, so widening what a tenant may tint (A4) cannot quietly widen it into a tone.
2. **`brand-500` is the same in both modes.** The 2026-07-29 ruling — a mode may not change whose
   product you are looking at — enforced at the storage fence, so it holds for a hand-written set
   as well as a derived one.
3. **The ramp maths agrees with the browser's.** `theme_tokens.brand_ramp` mirrors `brandRamp()` in
   `branding.ts`; `GOLDEN` below is asserted here AND in `branding.test.ts`, so if either language
   drifts, that language's own suite fails.
"""
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.courses import theme_tokens as tt
from apps.courses.models import OrganisationTheme, PartnerOrganisation

# ⚠ SHARED GOLDEN — the same fixture is asserted in halatuju-web/src/lib/__tests__/branding.test.ts.
# Hand-verified at the corners: light-50 mixes 95% toward white, light-900 60% toward black, and in
# dark those two ends SWAP (50 toward the page ground 17/24/39, 900 toward white).
GOLDEN = {
    'light': {
        'brand-50': '250 244 251', 'brand-100': '241 221 243', 'brand-200': '227 187 231',
        'brand-300': '209 142 215', 'brand-400': '185 85 195', 'brand-500': '162 28 175',
        'brand-600': '138 24 149', 'brand-700': '113 20 123', 'brand-800': '89 15 96',
        'brand-900': '65 11 70',
    },
    # ⚠ THE DARK SHADES MOVED IN F7a and were re-derived BY HAND, not copied out of the code — a
    # golden taken from the implementation pins whatever that implementation does, including its
    # bugs, which is the one thing this fixture exists to prevent. #a21caf is (162, 28, 175) and the
    # dark shade end mixes toward white at 0.45 / 0.60 / 0.75 / 0.86, ties rounding UP:
    #   600  r 162+93(.45)=203.85→204   g 28+227(.45)=130.15→130   b 175+80(.45)=211
    #   700  r 162+93(.60)=217.8 →218   g 28+227(.60)=164.2 →164   b 175+80(.60)=223
    #   800  r 162+93(.75)=231.75→232   g 28+227(.75)=198.25→198   b 175+80(.75)=235
    #   900  r 162+93(.86)=241.98→242   g 28+227(.86)=223.22→223   b 175+80(.86)=243.8→244
    # The tints are UNCHANGED — F7a moved the shade end only.
    'dark': {
        'brand-50': '24 24 46', 'brand-100': '39 25 59', 'brand-200': '61 25 80',
        'brand-300': '90 26 107', 'brand-400': '126 27 141', 'brand-500': '162 28 175',
        'brand-600': '204 130 211', 'brand-700': '218 164 223', 'brand-800': '232 198 235',
        'brand-900': '242 223 244',
    },
}


def valid_tokens(colour='#a21caf'):
    return tt.tokens_from_colour(colour)


class TestBrandRamp(TestCase):
    def test_the_golden_set_matches_the_browsers(self):
        self.assertEqual(tt.tokens_from_colour(tt.GOLDEN_HEX), GOLDEN)

    def test_the_identity_stop_is_the_colour_itself_in_both_modes(self):
        tokens = valid_tokens('#137fec')
        self.assertEqual(tokens['light']['brand-500'], '19 127 236')
        self.assertEqual(tokens['dark']['brand-500'], tokens['light']['brand-500'])

    def test_the_ends_swap_between_modes(self):
        # A tint is lighter than its own base in light, and DARKER in dark — because in dark it is
        # mixed toward the page rather than toward white. This is the property F3b shipped.
        tokens = valid_tokens('#a21caf')
        light_50 = sum(int(c) for c in tokens['light']['brand-50'].split())
        dark_50 = sum(int(c) for c in tokens['dark']['brand-50'].split())
        base = sum(int(c) for c in tokens['light']['brand-500'].split())
        self.assertGreater(light_50, base)
        self.assertLess(dark_50, base)

    def test_rounding_is_javascripts_not_pythons(self):
        # Python's built-in round() is banker's: round(100.5) == 100. JavaScript's Math.round ties
        # toward +infinity: 101. A single channel disagreeing would be invisible on screen and
        # permanently confusing in a diff, so the helper is pinned directly.
        self.assertEqual(tt._round_half_up(100.5), 101)
        self.assertEqual(round(100.5), 100)  # the trap this avoids

    def test_a_bad_hex_is_refused(self):
        for bad in ('a21caf', '#a21ca', '#ggggff', '', None, '#a21caff'):
            with self.assertRaises(tt.ThemeTokenError):
                tt.tokens_from_colour(bad)


class TestTheFence(TestCase):
    def test_a_tone_is_never_a_tenants(self):
        # THE DURABLE RULE. Asserted per family and independently of TENANT_FAMILIES, so widening
        # the allow-list (A4) cannot let a tone through by accident.
        for family in tt.PLATFORM_FAMILIES:
            tokens = valid_tokens()
            tokens['light'][f'{family}-500'] = '1 2 3'
            tokens['dark'][f'{family}-500'] = '1 2 3'
            with self.assertRaises(tt.ThemeTokenError, msg=family) as ctx:
                tt.validate_tokens(tokens)
            self.assertIn('platform', str(ctx.exception))

    def test_an_unknown_family_is_refused(self):
        tokens = valid_tokens()
        tokens['light']['sparkle-500'] = '1 2 3'
        tokens['dark']['sparkle-500'] = '1 2 3'
        with self.assertRaises(tt.ThemeTokenError):
            tt.validate_tokens(tokens)

    def test_the_identity_stop_may_not_differ_between_modes(self):
        tokens = valid_tokens()
        tokens['dark']['brand-500'] = '1 2 3'
        with self.assertRaises(tt.ThemeTokenError) as ctx:
            tt.validate_tokens(tokens)
        self.assertIn('identity', str(ctx.exception))

    def test_both_modes_are_required(self):
        tokens = valid_tokens()
        del tokens['dark']
        with self.assertRaises(tt.ThemeTokenError):
            tt.validate_tokens(tokens)

    def test_the_modes_must_define_the_same_tokens(self):
        tokens = valid_tokens()
        del tokens['dark']['brand-50']
        with self.assertRaises(tt.ThemeTokenError):
            tt.validate_tokens(tokens)

    def test_a_malformed_triplet_is_refused(self):
        for bad in ('#a21caf', '162,28,175', '162 28', '162 28 300', 175, None):
            tokens = valid_tokens()
            tokens['light']['brand-50'] = bad
            with self.assertRaises(tt.ThemeTokenError, msg=repr(bad)):
                tt.validate_tokens(tokens)

    def test_a_step_outside_the_ten_is_refused(self):
        tokens = valid_tokens()
        tokens['light']['brand-550'] = '1 2 3'
        tokens['dark']['brand-550'] = '1 2 3'
        with self.assertRaises(tt.ThemeTokenError):
            tt.validate_tokens(tokens)

    def test_a_valid_set_passes(self):
        self.assertEqual(tt.validate_tokens(valid_tokens()), valid_tokens())


class TestAppliedTokens(TestCase):
    def test_a_tone_smuggled_around_the_orm_is_dropped_on_the_way_out(self):
        # The write fence covers writers. A row edited in a console, restored from a backup, or
        # touched by a future migration has no writer — so the read filters too.
        smuggled = valid_tokens()
        smuggled['light']['critical-500'] = '255 0 0'
        smuggled['dark']['critical-500'] = '255 0 0'
        out = tt.applied_tokens(smuggled)
        self.assertNotIn('critical-500', out['light'])
        self.assertIn('brand-500', out['light'])

    def test_junk_resolves_to_none_rather_than_half_a_theme(self):
        for junk in (None, {}, 'blue', {'light': {}}, {'light': {'brand-50': 'x'}, 'dark': {}}):
            self.assertIsNone(tt.applied_tokens(junk))


class TestTheModelIsTheSeam(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='inspire', name='Inspire Foundation')

    def test_saving_stores_the_set(self):
        theme = OrganisationTheme.objects.create(
            organisation=self.org, source_colour='#a21caf', tokens=valid_tokens())
        theme.refresh_from_db()
        self.assertEqual(theme.tokens['light']['brand-500'], '162 28 175')
        self.assertEqual(self.org.themes.get(), theme)

    def test_a_new_row_is_a_draft_and_a_draft_is_never_served(self):
        """⚠ THE ONE THAT MATTERS MOST IN A3. A row starts as a draft, and `active_for` — the seam
        the serve path reads — must not return it. If this ever passes with a draft, an unpublished
        experiment is reaching applicants."""
        draft = OrganisationTheme.objects.create(
            organisation=self.org, source_colour='#a21caf', tokens=valid_tokens())
        self.assertEqual(draft.status, OrganisationTheme.STATUS_DRAFT)
        self.assertIsNone(OrganisationTheme.active_for(self.org))

    def test_a_shell_caller_cannot_go_around_the_fence(self):
        # The guard is on save(), not on an endpoint — otherwise it is a request, not a rule.
        tokens = valid_tokens()
        tokens['light']['positive-500'] = '0 255 0'
        tokens['dark']['positive-500'] = '0 255 0'
        with self.assertRaises(tt.ThemeTokenError):
            OrganisationTheme.objects.create(organisation=self.org, tokens=tokens)
        self.assertFalse(OrganisationTheme.objects.filter(organisation=self.org).exists())

    def test_an_empty_theme_is_refused(self):
        with self.assertRaises(tt.ThemeTokenError):
            OrganisationTheme.objects.create(organisation=self.org, tokens={})


class TestTheCommand(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='inspire', name='Inspire Foundation')

    def test_report_only_by_default(self):
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#a21caf')
        self.assertFalse(OrganisationTheme.objects.exists())

    def test_apply_publishes_the_derived_set(self):
        # ⚠ THE COMMAND PUBLISHES; THE SCREEN DRAFTS (Layer 1 A3). This is the operator's path, run
        # deliberately from a shell by somebody who has just read the shades it printed.
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#a21caf', '--apply')
        theme = OrganisationTheme.active_for(self.org)
        self.assertIsNotNone(theme)
        self.assertEqual(theme.source_colour, '#a21caf')
        self.assertEqual(theme.tokens, GOLDEN)
        self.assertIsNotNone(theme.published_at)

    def test_applying_twice_keeps_ONE_live_and_archives_the_other(self):
        # The old version is archived, never overwritten — that history is what makes --clear a
        # real revert rather than a guess at the previous hex.
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#a21caf', '--apply')
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#137fec', '--apply')
        self.assertEqual(OrganisationTheme.objects.count(), 2)
        self.assertEqual(OrganisationTheme.active_for(self.org).source_colour, '#137fec')
        self.assertEqual(
            OrganisationTheme.objects.filter(status='archived').get().source_colour, '#a21caf')

    def test_clear_reverts_to_the_previous_colour(self):
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#a21caf', '--apply')
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#137fec', '--apply')
        call_command('set_organisation_theme', '--org', 'inspire', '--clear', '--apply')
        self.assertEqual(OrganisationTheme.active_for(self.org).source_colour, '#a21caf')

    def test_clearing_the_FIRST_colour_lands_on_the_platform_default(self):
        # A real outcome, not a failure: it is genuinely what they had before, and it is how a
        # tenant gets all the way back.
        call_command('set_organisation_theme', '--org', 'inspire', '--colour', '#a21caf', '--apply')
        call_command('set_organisation_theme', '--org', 'inspire', '--clear', '--apply')
        self.assertIsNone(OrganisationTheme.active_for(self.org))
        # The row is KEPT, archived — nothing is thrown away.
        self.assertEqual(OrganisationTheme.objects.filter(status='archived').count(), 1)

    def test_the_platform_organisation_is_refused(self):
        # BrightPath is seeded as org #1 by a data migration, so it is already there — and the
        # refusal fires on the CODE, before any lookup, so it would hold even if it were not.
        with self.assertRaises(CommandError) as ctx:
            call_command('set_organisation_theme', '--org', 'brightpath',
                         '--colour', '#a21caf', '--apply')
        self.assertIn('globals.css', str(ctx.exception))

    def test_an_unknown_organisation_is_refused(self):
        with self.assertRaises(CommandError):
            call_command('set_organisation_theme', '--org', 'nope', '--colour', '#a21caf')
