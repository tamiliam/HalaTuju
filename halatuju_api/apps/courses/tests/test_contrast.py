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
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.courses import contrast as cx
from apps.courses import theme_tokens as tt

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Re-measured 2026-09-02 in BOTH MODES (Layer 1 F7a). Anything that changes these lists is a change
# in what a tenant may choose, and should be argued for in a commit — so here is the argument.
PASSES = ('#137fec', '#1e3a8a', '#0f766e', '#166534', '#7f1d1d', '#a21caf',
          '#4338ca', '#dc2626', '#ea580c', '#db2777', '#475569')

# ⚠ TWO COLOURS MOVED FROM PASSES TO REFUSES, and it is the gate telling the truth rather than
# getting stricter for its own sake. `#010066` and `#111827` are near-black. Gating dark asks a
# question light never did — can this colour be a READABLE LINK on a `#1f2937` card? — and even
# mixed 45% toward white a near-black brand cannot. Both fail `link_on_card` and `link_on_page` in
# dark and nothing else, which is exactly the honest reading: they were never unreadable before,
# because before, nobody could see the surface they are unreadable on.
DARK_ONLY_REFUSALS = ('#010066', '#111827')

REFUSES = ('#d97706', '#0ea5e9', '#65a30d', '#6ee7b7', '#facc15') + DARK_ONLY_REFUSALS


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
        # ⚠ `is_readable_everywhere`, not `is_readable`. The single-mode form still answers a real
        # question, and using it HERE would have let this list stay green while the save path — which
        # checks both — refused two of the colours it names as passing.
        for hexv in PASSES:
            fails = cx.failures_all_modes(tt.tokens_from_colour(hexv))
            self.assertEqual(fails, [], f'{hexv} should pass: {fails}')
        for hexv in REFUSES:
            self.assertFalse(cx.is_readable_everywhere(tt.tokens_from_colour(hexv)),
                             f'{hexv} should be refused')

    def test_the_two_new_refusals_fail_ONLY_in_dark_and_ONLY_on_links(self):
        """Pins WHY the two near-blacks moved, so a later reader cannot mistake it for the gate
        getting arbitrarily stricter — and so that if the reason ever stops being true, this fails
        rather than the list quietly meaning something else."""
        for hexv in DARK_ONLY_REFUSALS:
            with self.subTest(hexv):
                tokens = tt.tokens_from_colour(hexv)
                self.assertTrue(cx.is_readable(tokens, 'light'))
                self.assertEqual({r.key for r in cx.failures(tokens, 'dark')},
                                 {'link_on_card', 'link_on_page'})

    def test_a_pale_colour_fails_the_text_pairs_not_merely_one(self):
        # Yellow is unreadable for white text AND for brand-as-text. A gate that caught only one
        # would still refuse it, and would be a worse explanation to the person who picked it.
        keys = {f.key for f in cx.failures(tt.tokens_from_colour('#facc15'))}
        self.assertIn('filled_button', keys)
        self.assertIn('link_on_card', keys)
        self.assertIn('panel_text', keys)

    def test_shapes_are_held_to_three_not_four_point_five(self):
        # TWO pairs are about a shape's EDGE rather than about words: the dot/bar, and — since
        # F7a — whether the filled button can be found against its own card at all.
        shapes = {'ui_shape', 'filled_button_visible'}
        for pair in cx.PAIRS:
            expected = cx.AA_NON_TEXT if pair.key in shapes else cx.AA_TEXT
            self.assertEqual(pair.min_ratio, expected, pair.key)
        self.assertEqual({p.key for p in cx.PAIRS} & shapes, shapes)

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
        # `brand-600` alone supplies FOUR pairs in LIGHT, not one: both link pairs (it against the
        # two platform grounds, which are constants and always available) plus the filled button and
        # its visibility, because in LIGHT the fill role resolves to `brand-600` itself. The pairs
        # needing `-700`, `-50` or `-500` drop out.
        self.assertEqual(keys, {'filled_button', 'filled_button_visible',
                                'link_on_card', 'link_on_page'})
        # ⚠ `ui_shape` drops out in LIGHT, where the shape role resolves to `brand-500`, and comes
        # BACK in dark, where it resolves to `brand-600` — which this partial set happens to carry.
        # Two roles now move between modes, so a one-mode assertion would miss half the behaviour.
        # ⚠ AND THE SAME SET IS DIFFERENT IN DARK, which is the whole point of the role. There the
        # fill resolves to `brand-800`, which this partial set does not carry, so the button pairs
        # drop out and only the links remain. A test asserting one mode would have missed that the
        # resolution moved at all.
        self.assertEqual({r.key for r in cx.check_tokens(partial, 'dark')},
                         {'link_on_card', 'link_on_page', 'ui_shape'})

    def test_an_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            cx.check_tokens(tt.tokens_from_colour('#137fec'), 'sepia')


class TestDarkIsGatedNow(TestCase):
    """TD-222 is CLOSED (Layer 1 F7a). This class replaces `TestDarkIsDeliberatelyNotGatedYet`.

    What it was recording: in dark, `brand-600` and `-700` were short mixes toward white, so
    `text-white` on them measured 3.22 and 2.59 for the platform's own colour. Two separate things
    were wrong and only one of them was the ramp:

      1. The shade end aimed at white (right) but travelled light's short distances (wrong), so
         `brand-600` — which the app spells as its LINK ink — was barely lighter than the tenant's
         colour on a `#1f2937` card. Fixed by `_SHADE_MIX`.
      2. A filled button and a link were being spelled with the SAME stop while wanting opposite
         things. No set of distances fixes that; it needed a role. Fixed by `FILL_ROLE`.
    """

    def test_the_platform_colour_passes_in_BOTH_modes(self):
        tokens = tt.tokens_from_colour('#137fec')
        self.assertTrue(cx.is_readable_everywhere(tokens), cx.failures_all_modes(tokens))

    def test_a_realistic_spread_of_tenant_colours_passes_in_dark(self):
        """⚠ THE CALIBRATION CANARY, pointed at dark. A2's light-mode twin exists for the same
        reason: a gate that refuses almost everybody is reporting OUR defect as the tenant's.
        Before F7a these nine passed light and failed dark; the fix is not credible unless they
        pass both, so they are named individually rather than counted."""
        for hex_colour in ('#137fec', '#a21caf', '#0f766e', '#1e3a8a', '#c2410c',
                           '#be123c', '#166534', '#db2777', '#4338ca'):
            with self.subTest(hex_colour):
                tokens = tt.tokens_from_colour(hex_colour)
                self.assertEqual(cx.failures_all_modes(tokens), [])

    def test_EVERY_pair_is_checked_in_EVERY_mode_now(self):
        """⚠ F7b CLOSED THE LAST EXEMPTION, and this replaces the test that named it.

        `ui_shape` was light-only because it measured `brand-500` — the IDENTITY stop, which cannot
        move between modes by owner ruling — so a dark tenant colour drew an invisible dot on a dark
        card. It is a ROLE now, like the fill, and `DARK_EXEMPT` is gone with it.
        """
        self.assertFalse(hasattr(cx, 'DARK_EXEMPT'))
        tokens = tt.tokens_from_colour('#137fec')
        for mode in tt.MODES:
            self.assertEqual({r.key for r in cx.check_tokens(tokens, mode)},
                             {p.key for p in cx.PAIRS}, mode)

    def test_the_shape_role_is_what_made_that_possible(self):
        """The defect the exemption stood for was REAL, so pin that the ROLE is what fixed it and
        not a loosened bar. A dark navy dot drawn at the identity stop is still under 3.0; drawn
        through the role it is not."""
        navy = tt.tokens_from_colour('#1e3a8a')
        card = cx.PLATFORM_SURFACES['dark']['ground-0']
        at_identity = cx.contrast_ratio(cx._rgb('brand-500', navy, 'dark'), card)
        through_role = cx.contrast_ratio(cx._rgb('shape', navy, 'dark'), card)
        self.assertLess(at_identity, cx.AA_NON_TEXT)
        self.assertGreaterEqual(through_role, cx.AA_NON_TEXT)
        # ⚠ AND THE IDENTITY STOP DID NOT MOVE. The ruling is about `--brand-500`, not about which
        # stop a role lands on — this is the assertion that says the two are different things.
        self.assertEqual(navy['light']['brand-500'], navy['dark']['brand-500'])

    def test_gating_shapes_in_dark_added_NO_new_refusals(self):
        """⚠ THE RESULT THAT MAKES F7b CREDIBLE. A2's lesson is that a gate refusing lots of colours
        is usually reporting OUR defect. F7a exempted this pair because 10 of 18 failed; if the role
        were the wrong fix, closing the exemption would show up here as colours moving into REFUSES.
        None did — the same 11 pass and the same 7 refuse, for the same reasons as before."""
        for hexv in PASSES:
            with self.subTest(hexv):
                self.assertEqual(cx.failures_all_modes(tt.tokens_from_colour(hexv)), [])
        for hexv in DARK_ONLY_REFUSALS:
            with self.subTest(hexv):
                self.assertEqual({r.key for r in cx.failures(tt.tokens_from_colour(hexv), 'dark')},
                                 {'link_on_card', 'link_on_page'})


class TestTheBrandRolesAgreeWithTheBrowser(SimpleTestCase):
    """⚠ THREE FILES DESCRIBE THE FILL ROLE AND ALL THREE MUST AGREE (Layer 1 F7a).

    `--brand-fill*` and `--brand-shape` are declared in `globals.css` (what the browser PAINTS),
    `BRAND_ROLE` in
    `branding.ts` (what the picker MEASURES as somebody types) and `BRAND_ROLE` here (what the SAVE
    PATH measures, and therefore what is actually enforced).

    A disagreement is silent in both directions: the gate would approve a colour on a button nobody
    will ever see, or refuse one that renders perfectly. That is the F4 role-palette shape, and the
    lesson from it is that a comment asking two files to stay in step is a request — only a test is
    a rule. The web suite pins the CSS against `branding.ts`; this pins the CSS against Python, so
    whichever side drifts, its own suite goes red.
    """

    CSS = (Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src' / 'app' / 'globals.css')

    def _stop(self, block, role):
        m = re.search(r'--brand-%s:\s*var\(--([a-z0-9-]+)\)' % role, block)
        return m.group(1) if m else None

    def test_the_css_resolves_the_same_stops_this_module_measures(self):
        css = self.CSS.read_text(encoding='utf-8')
        dark_at = css.index("[data-theme='dark']")
        light, dark = css[:dark_at], css[dark_at:]

        self.assertEqual(self._stop(light, 'fill'), cx.BRAND_ROLE['light']['fill'])
        self.assertEqual(self._stop(light, 'fill-hover'), cx.BRAND_ROLE['light']['hover'])
        self.assertEqual(self._stop(dark, 'fill'), cx.BRAND_ROLE['dark']['fill'])
        self.assertEqual(self._stop(dark, 'fill-hover'), cx.BRAND_ROLE['dark']['hover'])

        # Light's ink is the white LITERAL; dark's is the page it punches through.
        self.assertEqual(cx.BRAND_ROLE['light']['ink'], 'white')
        self.assertRegex(light, r'--brand-fill-ink:\s*255 255 255;')
        self.assertEqual(self._stop(dark, 'fill-ink'), cx.BRAND_ROLE['dark']['ink'])

        # …and the SHAPE role, added in F7b. It is in the same table for the same reason.
        self.assertEqual(self._stop(light, 'shape'), cx.BRAND_ROLE['light']['shape'])
        self.assertEqual(self._stop(dark, 'shape'), cx.BRAND_ROLE['dark']['shape'])

    def test_the_fill_never_shares_a_stop_with_the_link(self):
        # The property behind the whole sprint, so a later tuning pass cannot undo it by accident:
        # on a dark card a link has to be pale enough to READ and a button dark enough to carry ink,
        # so they may not be the same number.
        link = [p for p in cx.PAIRS if p.key == 'link_on_card'][0].ink
        self.assertNotEqual(cx.BRAND_ROLE['dark']['fill'], link)
