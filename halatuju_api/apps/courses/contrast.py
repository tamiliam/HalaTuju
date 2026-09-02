"""The contrast gate — can a person READ this tenant's colour? (Layer 1 A2)

`theme_tokens` decides whether a token set is one a tenant is ALLOWED to store. This module decides
whether it is one anybody can read. They are separate questions and they stay in separate files.

── IT CHECKS PAIRS, NOT A HEX ─────────────────────────────────────────────────────────────────────
"Is #a21caf safe?" has no answer. Contrast is a property of two colours and the question is always
"is THIS ink readable on THAT surface". So the gate holds a table of the pairs the product actually
renders, derived by counting them in the web app rather than imagined:

    the fill role's ink  on the fill role   the main filled button
    the fill role's ink  on its hover stop  that button under the cursor
    the fill role        on a card          whether the button can be FOUND at all
    text-primary-700 on bg-primary-50   the tinted panel with brand text
    text-primary-600 on a card          a link
    text-primary-600 on the page ground a link outside a card
    bg-primary-500   on a card          dots, bars and icon circles — NOT text

A checker written against a hex has to be rewritten the day per-token colours arrive; one written
against the pairs actually rendered simply gets more rows.

The first three rows name a ROLE rather than a stop, and `FILL_ROLE` resolves it per mode — see
that table for why a button and a link cannot share a number in dark.

⚠ THE LAST ROW HAS A DIFFERENT BAR, AND THE REASON IS THE SPRINT'S OWN FINDING. `bg-primary-500`
used to carry `text-white` in 46 places, which put small white text on the lightest usable brand
stop — and the platform's own colour measured **3.98** there, below AA. So the gate as first written
refused BrightPath's own live blue, and orange besides. That is not a mis-calibrated gate; it is a
correctly-calibrated gate finding a real defect, because F4 had already ruled that a filled control
carries `bg-primary-600` and those 46 were the ones that never moved. A2 moved them. What is left on
`-500` is dots, progress bars and icon circles — SHAPES, not text — so its bar is WCAG's **3:1 for
non-text** rather than 4.5. Measured after the move: 13 of 18 realistic brand colours passed in
light, and every refusal was a colour a person genuinely could not read.

**Re-measured in BOTH modes after F7a: 11 of 18.** The two that moved (`#010066`, `#111827`) are
near-black and fail only the dark link pairs — a question light never asked.

── IT REFUSES; IT DOES NOT WARN ───────────────────────────────────────────────────────────────────
A tenant will pick a colour that renders at 4:1 against white. A warning is dismissed and a student
cannot read the page, and the person who dismissed it is not the person who suffers. So this is
called from the save path and a failure is a `400`, not a note on the screen.

── BOTH MODES, SINCE LAYER 1 F7a. TD-222 IS CLOSED ────────────────────────────────────────────────
A2 gated light alone and said why: dark was unreachable, and it was also ungateable, because
`text-white` on the dark `brand-600` measured 3.22 **for the platform's own colour** — no colour on
earth would have passed, so the gate would have been refusing every tenant for our defect.

F7a fixed the two things behind that number. The dark shade end was aimed correctly (F3b) but
travelled light's short distances, so `brand-600` was barely lighter than the tenant's colour on a
`#1f2937` card; and a filled button and a link were being spelled with the SAME stop while wanting
opposite things there. The first is `_SHADE_MIX`, the second is `FILL_ROLE`. **The save path now
calls `failures_all_modes`** — a colour is stored once and rendered in both, and a tenant refused
only after somebody flips the switch has been let down by the gate rather than protected by it.

**F7b closed the last exemption.** `ui_shape` was light-only because it measured `brand-500` — the
identity stop, which cannot move between modes — so a dark tenant colour drew an invisible dot on a
dark card. It is a ROLE now, like the fill, and every pair is checked in every mode.
"""
from collections import namedtuple

from .theme_tokens import MODES

# WCAG 2.1 AA for normal-size text. The product sets these pairs in `text-xs`/`text-sm`, so the
# large-text allowance (3:1) does not apply — checked in the markup, not assumed.
AA_TEXT = 4.5

# WCAG 2.1 AA for non-text: a shape whose BOUNDARY must be discernible, not read. Dots, progress
# bars and the circles behind icons. Never use this for anything carrying words.
AA_NON_TEXT = 3.0

# A pair the product renders. `ink` and `surface` are token references; `min_ratio` is its bar.
Pair = namedtuple('Pair', 'key ink surface min_ratio')

# ⚠ `white` IS NOT `ground-0`, and they are separate entries on purpose. `text-white` is a LITERAL
# in this codebase (214 uses) and deliberately never became `text-ground-0` — see globals.css. In
# light mode they happen to be the same colour; in dark they are nothing like each other, so folding
# them together here would quietly make the dark pairs wrong the day dark is gated.
PLATFORM_SURFACES = {
    'light': {'white': (255, 255, 255), 'ground-0': (255, 255, 255), 'ground-50': (249, 250, 251)},
    'dark': {'white': (255, 255, 255), 'ground-0': (31, 41, 55), 'ground-50': (17, 24, 39)},
}

# ⚠ THE BRAND'S ROLES, AND WHICH STOP EACH LANDS ON PER MODE.
#
# A role rather than a stop wherever one number cannot serve two jobs across modes:
#   fill / hover / ink   the filled control (F7a). A button's fill and a link's ink want opposite
#                        things on a dark card, and no set of ramp distances gives both.
#   shape                the mark a dot, bar, spinner or focus ring makes (F7b). It was the
#                        IDENTITY stop, which cannot move between modes by owner ruling, so a dark
#                        tenant colour drew an invisible shape on a dark card — 10 of 18 under 3.0.
#
# ⚠ ONE TABLE ON PURPOSE. Two tables of brand roles is the F4 role-palette shape waiting to happen.
# It must stay byte-identical to `BRAND_ROLE` in `src/lib/branding.ts` and to the `--brand-fill*` /
# `--brand-shape` block in `globals.css`; a test on each side pins all three together.
BRAND_ROLE = {
    'light': {'fill': 'brand-600', 'hover': 'brand-700', 'ink': 'white', 'shape': 'brand-500'},
    'dark': {'fill': 'brand-800', 'hover': 'brand-900', 'ink': 'ground-50', 'shape': 'brand-600'},
}

PAIRS = (
    Pair('filled_button', 'fill-ink', 'fill', AA_TEXT),
    Pair('filled_button_hover', 'fill-ink', 'fill-hover', AA_TEXT),
    # ⚠ THE PAIR THAT STOPS THE OBVIOUS "FIX". When dark first failed, the reflex was to move the
    # button DOWN the ramp so white text would read. It does — `brand-400` measures 5.82 — and the
    # button then sits at **2.52** against its own card and stops looking like a button. A control
    # has to be findable as well as readable, so both bars are held at once and neither can be
    # traded for the other. Non-text, because what is being seen here is a SHAPE's edge.
    Pair('filled_button_visible', 'fill', 'ground-0', AA_NON_TEXT),
    Pair('panel_text', 'brand-700', 'brand-50', AA_TEXT),
    Pair('link_on_card', 'brand-600', 'ground-0', AA_TEXT),
    Pair('link_on_page', 'brand-600', 'ground-50', AA_TEXT),
    # Shapes, not words — see the docstring. Moving this to AA_TEXT would refuse the platform's
    # own colour, and `test_the_platform_colour_passes_its_own_gate` says so out loud.
    # ⚠ `ground-0` rather than `white`: in light they are the same colour, and in dark `ground-0` is
    # the CARD, which is what a dot actually sits on. `white` here would have measured the dot
    # against a surface that does not exist in dark.
    # ⚠ A ROLE since F7b, and it is gated in BOTH modes now. `DARK_EXEMPT` is gone with it.
    Pair('ui_shape', 'shape', 'ground-0', AA_NON_TEXT),
)

Result = namedtuple('Result', 'key ratio min_ratio passes')


def _channel(value):
    """One sRGB channel, linearised. The 0.03928 branch and the 2.4 exponent are WCAG's, verbatim."""
    s = value / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(a, b):
    """WCAG contrast between two RGB triples. Symmetric — order never matters."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _rgb(ref, tokens, mode):
    """Resolve a pair reference to an RGB triple, or None when the set does not carry it.

    A ROLE name is resolved through `BRAND_ROLE` FIRST, so it lands on a different stop in each
    mode. Everything else is a literal token name.
    """
    if ref.startswith('fill'):
        ref = BRAND_ROLE[mode][ref[5:] or 'fill']
    elif ref == 'shape':
        ref = BRAND_ROLE[mode]['shape']
    if ref in PLATFORM_SURFACES[mode]:
        return PLATFORM_SURFACES[mode][ref]
    raw = (tokens.get(mode) or {}).get(ref)
    if not isinstance(raw, str):
        return None
    parts = raw.split()
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def check_tokens(tokens, mode='light'):
    """Every pair this token set can be measured on, in the order of `PAIRS`.

    A pair the set does not carry is SKIPPED, not failed. That matters: a partial set is a
    `theme_tokens` question ("may you store this?"), and answering it here as "unreadable" would
    report the wrong problem to a tenant who has done nothing wrong.
    """
    if mode not in MODES:
        raise ValueError(f'unknown mode: {mode!r}')
    out = []
    for pair in PAIRS:
        ink = _rgb(pair.ink, tokens, mode)
        surface = _rgb(pair.surface, tokens, mode)
        if ink is None or surface is None:
            continue
        ratio = contrast_ratio(ink, surface)
        out.append(Result(pair.key, round(ratio, 2), pair.min_ratio, ratio >= pair.min_ratio))
    return out


def failures(tokens, mode='light'):
    """Just the pairs that a person could not read. Empty means the colour may be saved."""
    return [r for r in check_tokens(tokens, mode) if not r.passes]


def is_readable(tokens, mode='light'):
    return not failures(tokens, mode)


def failures_all_modes(tokens):
    """Every unreadable pair across EVERY mode, as `(mode, Result)`.

    ⚠ THIS IS WHAT THE SAVE PATH CALLS, and the difference matters. `failures(tokens)` answers
    "is this readable in light", which is the question A2 could honestly ask while dark was
    unreachable. A colour is now stored once and rendered in both, and a tenant who is refused only
    after somebody switches mode has been let down by the gate rather than protected by it.
    """
    return [(mode, r) for mode in MODES for r in failures(tokens, mode)]


def is_readable_everywhere(tokens):
    return not failures_all_modes(tokens)
