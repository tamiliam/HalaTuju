"""Layer 1 A2 — the contrast gate: can a person READ this tenant's colour?

The three claims worth protecting, hardest first:

1. **The platform's own colour passes its own gate.** If it did not, the gate would be measuring a
   defect in OUR product and refusing tenants for it — which is exactly what the first draft did,
   and how the 46 mis-shaded buttons were found. That test is the calibration canary.
2. **The maths is WCAG's, not an approximation.** Pinned against the two ratios everybody knows
   (black on white is 21, a colour on itself is 1) plus a hand-checked middle value.
3. **A refusal is a real refusal.** The spread below is the measured behaviour over realistic brand
   colours, recorded so that a change in the pair table or a threshold shows up as a diff in a
   named list rather than as a vague feeling that the gate got stricter.
"""
from django.test import TestCase

from apps.courses import contrast as cx
from apps.courses import theme_tokens as tt

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Measured 2026-09-01, AFTER the 46 white-text buttons moved off `bg-primary-500`. Anything that
# changes this list is a change in what a tenant may choose, and should be argued for in a commit.
PASSES = ('#137fec', '#1e3a8a', '#0f766e', '#166534', '#7f1d1d', '#a21caf',
          '#4338ca', '#010066', '#dc2626', '#ea580c', '#db2777', '#475569', '#111827')
REFUSES = ('#d97706', '#0ea5e9', '#65a30d', '#6ee7b7', '#facc15')


class TestTheMaths(TestCase):
    def test_the_two_ratios_everybody_knows(self):
        self.assertAlmostEqual(cx.contrast_ratio(BLACK, WHITE), 21.0, places=4)
        self.assertAlmostEqual(cx.contrast_ratio(WHITE, WHITE), 1.0, places=4)

    def test_it_is_symmetric(self):
        a, b = (19, 127, 236), WHITE
        self.assertEqual(cx.contrast_ratio(a, b), cx.contrast_ratio(b, a))

    def test_a_hand_checked_middle_value(self):
        # White on the platform brand's 600 stop. Computed by hand from the WCAG formula before
        # this module existed, so it pins the implementation rather than merely agreeing with it.
        six_hundred = tuple(int(c) for c in tt.brand_ramp('#137fec', 'light')[600].split())
        self.assertAlmostEqual(cx.contrast_ratio(WHITE, six_hundred), 5.24, places=2)

    def test_the_linearisation_uses_the_low_branch(self):
        # The 0.03928 branch matters only for very dark channels; getting it wrong shifts every
        # near-black ratio slightly, which nothing else here would catch.
        self.assertAlmostEqual(cx._channel(0), 0.0, places=6)
        self.assertAlmostEqual(cx._channel(10), 10 / 255 / 12.92, places=6)


class TestTheGate(TestCase):
    def test_the_platform_colour_passes_its_own_gate(self):
        """⚠ THE CALIBRATION CANARY — read the failure message before changing anything else.

        A gate that refuses the colour the product itself ships is not protecting anyone; it is
        reporting that the product renders that colour badly somewhere. When this fails, the honest
        first question is "which pair, and is the PRODUCT wrong there?" — that is how A2 found the
        46 buttons carrying small white text on the lightest usable brand stop.
        """
        fails = cx.failures(tt.tokens_from_colour('#137fec'))
        self.assertEqual(fails, [], f'the platform colour now fails: {[f.key for f in fails]}')

    def test_the_measured_spread(self):
        for hexv in PASSES:
            self.assertTrue(cx.is_readable(tt.tokens_from_colour(hexv)), f'{hexv} should pass')
        for hexv in REFUSES:
            self.assertFalse(cx.is_readable(tt.tokens_from_colour(hexv)), f'{hexv} should be refused')

    def test_a_pale_colour_fails_the_text_pairs_not_merely_one(self):
        # Yellow is unreadable for white text AND for brand-as-text. A gate that caught only one
        # would still refuse it, and would be a worse explanation to the person who picked it.
        keys = {f.key for f in cx.failures(tt.tokens_from_colour('#facc15'))}
        self.assertIn('filled_button', keys)
        self.assertIn('link_on_card', keys)
        self.assertIn('panel_text', keys)

    def test_shapes_are_held_to_three_not_four_point_five(self):
        shape = [p for p in cx.PAIRS if p.key == 'ui_shape']
        self.assertEqual(len(shape), 1)
        self.assertEqual(shape[0].min_ratio, cx.AA_NON_TEXT)
        # And every OTHER pair carries words, so every other pair is held to the text bar.
        for pair in cx.PAIRS:
            if pair.key != 'ui_shape':
                self.assertEqual(pair.min_ratio, cx.AA_TEXT, pair.key)

    def test_white_and_ground_zero_are_separate_entries(self):
        # `text-white` is a literal in this codebase and deliberately never became `text-ground-0`.
        # In light they are the same colour, so only the DARK table shows the difference — which is
        # exactly why folding them together would be an invisible mistake today.
        self.assertNotEqual(cx.PLATFORM_SURFACES['dark']['white'],
                            cx.PLATFORM_SURFACES['dark']['ground-0'])
        self.assertEqual(cx.PLATFORM_SURFACES['light']['white'],
                         cx.PLATFORM_SURFACES['light']['ground-0'])

    def test_a_pair_the_set_cannot_supply_is_skipped_not_failed(self):
        # A partial set is a `theme_tokens` question, not a readability one. Reporting it here as
        # "unreadable" would tell a tenant the wrong thing about a colour they chose correctly.
        partial = {'light': {'brand-600': '16 108 201'}, 'dark': {'brand-600': '16 108 201'}}
        keys = {r.key for r in cx.check_tokens(partial)}
        # `brand-600` alone supplies THREE pairs, not one: the filled button (white on it) and both
        # link pairs (it on the two platform grounds, which are constants and always available).
        # The three needing `-700`, `-50` or `-500` drop out.
        self.assertEqual(keys, {'filled_button', 'link_on_card', 'link_on_page'})

    def test_an_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            cx.check_tokens(tt.tokens_from_colour('#137fec'), 'sepia')


class TestDarkIsDeliberatelyNotGatedYet(TestCase):
    def test_dark_is_deliberately_not_gated_yet(self):
        """The reason, recorded so the omission is never read as an oversight (TD-222).

        In dark mode `brand-600` and `-700` are mixes toward WHITE, so `text-white` on them measures
        about 3.2 and 2.6 **for the platform's own colour**. That is a defect in the ramp, not in
        anybody's choice, and no colour on earth would pass a dark gate until it is fixed — gating
        dark now would refuse every tenant for our mistake.

        `check_tokens` already takes the mode, so switching this on is passing a different argument.
        F7 must not ship before it does.
        """
        tokens = tt.tokens_from_colour('#137fec')
        self.assertTrue(cx.is_readable(tokens, 'light'))
        dark_fails = {f.key for f in cx.failures(tokens, 'dark')}
        # If this ever comes back EMPTY, the dark ramp has been fixed — switch the gate on and
        # delete this test rather than leaving a passing assertion that means nothing.
        self.assertIn('filled_button', dark_fails)
