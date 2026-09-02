"""Tenant theme tokens — the ONE home for what a tenant's colours ARE (Layer 1 A1).

An organisation's theme is stored as a RESOLVED TOKEN SET, not as a hex colour that something
derives on the way out. That is the load-bearing decision of arc A and it is worth stating plainly,
because "store the hex, derive at serve time" is one column smaller and looks equivalent:

  * A tenant approved *those* colours. If the ten shades were derived per request, improving the
    derivation below would silently restyle every tenant's product without anyone asking — the same
    reasoning that freezes a student's requirements at submit and a terms version at publish.
  * A2's picker is then a UI that WRITES this shape, and A4's full palette is a SECOND EDITOR over
    the same storage: a new screen, no migration, no second reader taught two shapes.

── THE FENCE (owner ruling, 2026-07-29) ───────────────────────────────────────────────────────────
A tenant tints its own identity. The four TONE families and the CATEGORY family are the platform's:
they are how the product says "this went well" / "read this carefully" / "this is broken", and a
meaning that changes per tenant is not a meaning. `PLATFORM_FAMILIES` states that as a rule, and
`test_a_tone_is_never_a_tenants` pins it INDEPENDENTLY of the allow-list — so widening what a tenant
may write (A4) can never quietly widen it into a tone.

`TENANT_FAMILIES` is today's allow-list and it is deliberately just `brand`. The owner's eventual
boundary is brand + ground, but nothing writes a ground tint yet, and the standing constraint on
arc A forbids shipping a reserved key that nothing fills. Adding 'ground' is one word here on the
day a writer exists.

── THE IDENTITY STOP ──────────────────────────────────────────────────────────────────────────────
`brand-500` must be byte-identical in light and dark. That is the whole of the 2026-07-29 ruling —
a mode change may not alter WHOSE product you are looking at — and it is enforced here, at the
storage fence, so it holds for a token set typed by hand as well as one this module derived.

⚠ THIS MODULE MIRRORS `halatuju-web/src/lib/branding.ts` `brandRamp()`. Two copies of one sum is a
drift risk, so both sides assert the SAME golden fixture (`GOLDEN_HEX` below, and the matching case
in `branding.test.ts`). If one implementation drifts, its own suite fails.
"""
import math
import re

# The ten Tailwind steps, in order. Not configurable — the token vocabulary's own shape.
STEPS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900)

# The identity stop: the tenant's colour itself, unchanged by the mode.
IDENTITY_STEP = 500

# What a tenant may tint TODAY. See the module docstring before widening this.
TENANT_FAMILIES = ('brand',)

# Platform-owned families, by owner ruling. A tenant may NEVER write one, whatever else is allowed.
PLATFORM_FAMILIES = ('positive', 'info', 'caution', 'critical', 'category', 'ground')

MODES = ('light', 'dark')

# `--ground-50` in dark mode — the page a tinted brand panel actually sits on. Mirrors DARK_GROUND
# in `branding.ts`, which `theme.test.ts` already refuses to let drift from `globals.css`.
DARK_GROUND = (17, 24, 39)

# How far each step is pulled toward its end.
#
# TINTS are the same distances in both modes — only the END they aim at swaps (white in light, the
# page ground in dark), which is F3b's ruling.
_TINT_MIX = {50: 0.95, 100: 0.85, 200: 0.7, 300: 0.5, 400: 0.25}

# ⚠ SHADES ARE NOT. THE DARK DISTANCES ARE MUCH LONGER, AND THAT IS THE F7a FIX (2026-09-02).
#
# F3b aimed the dark shade end at WHITE, which was right, and kept light's distances, which was not.
# At 15% toward white, `brand-600` in dark is barely lighter than the tenant's colour — and the app
# spells its LINK ink `text-primary-600`, sitting on a `#1f2937` card. Measured across 18 realistic
# tenant colours, that pair failed AA for 14 of them; the panel-text pair failed for 4. Nothing was
# wrong with the direction; the steps were simply too short to reach a pale enough value.
#
# At these distances all 18 pass every text pair the product renders. Light is untouched, so the
# only mode that moves is the one no person can currently reach.
#
# ⚠ THE FILLED BUTTON IS A SEPARATE FIX AND THESE NUMBERS DO NOT ADDRESS IT — see `--brand-fill`
# in globals.css. A button's ink and a link's ink want opposite things in dark, and no single set
# of ramp distances can be both. Retuning further to "fix" a button would break every link again.
_SHADE_MIX = {
    'light': {600: 0.15, 700: 0.3, 800: 0.45, 900: 0.6},
    'dark': {600: 0.45, 700: 0.6, 800: 0.75, 900: 0.86},
}

_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
_KEY_RE = re.compile(r'^([a-z]+)-([0-9]+)$')
_TRIPLET_RE = re.compile(r'^([0-9]{1,3}) ([0-9]{1,3}) ([0-9]{1,3})$')

# A fixed input whose output both languages assert. Chosen to exercise rounding on every channel.
GOLDEN_HEX = '#a21caf'


class ThemeTokenError(ValueError):
    """A token set that a tenant is not allowed to store. Carries a plain reason."""


def _round_half_up(value):
    """JavaScript's `Math.round` (ties toward +infinity), NOT Python's banker's rounding.

    Every channel here is non-negative, so `floor(v + 0.5)` is exactly the JS rule. Using the
    built-in `round()` would disagree with `brandRamp()` on any exact .5 and the two ramps would
    differ by one in a channel — invisible on screen and permanently confusing in a diff.
    """
    return int(math.floor(value + 0.5))


def hex_to_rgb(value):
    """'#a21caf' -> (162, 28, 175). Raises ThemeTokenError on anything that is not a 6-digit hex."""
    if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        raise ThemeTokenError(f'not a 6-digit hex colour: {value!r}')
    h = value.strip().lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def brand_ramp(colour, mode):
    """The ten shades for one colour in one mode, as `'r g b'` triplets keyed by step.

    The two ends SWAP between modes. In light the tints mix toward white and the shades toward
    black, which is right for a white page. In dark that is exactly backwards — a 95%-white tint is
    a glaring patch on a dark page — so the tints mix toward the page ground and the shades toward
    white. `500` is the same value in both, by ruling.

    The DISTANCES also differ, on the shade end only: see `_SHADE_MIX`. Aiming at the right end was
    F3b's job and travelling far enough was F7a's.
    """
    if mode not in MODES:
        raise ThemeTokenError(f'unknown mode: {mode!r}')
    r, g, b = hex_to_rgb(colour)
    to_tint = DARK_GROUND if mode == 'dark' else (255, 255, 255)
    to_shade = (255, 255, 255) if mode == 'dark' else (0, 0, 0)

    def towards(end, t):
        return ' '.join(
            str(_round_half_up(channel + (target - channel) * t))
            for channel, target in zip((r, g, b), end)
        )

    shades = _SHADE_MIX[mode]
    out = {}
    for step in STEPS:
        if step == IDENTITY_STEP:
            out[step] = f'{r} {g} {b}'
        elif step in _TINT_MIX:
            out[step] = towards(to_tint, _TINT_MIX[step])
        else:
            out[step] = towards(to_shade, shades[step])
    return out


def tokens_from_colour(colour):
    """Derive the full stored token set from one brand colour.

    This is the SAVE-time derivation — its output is what gets stored and approved, never recomputed
    on the way out. A2's picker previews in the browser and posts a colour; this is what freezes.
    """
    return {
        mode: {f'brand-{step}': triplet for step, triplet in brand_ramp(colour, mode).items()}
        for mode in MODES
    }


def family_of(key):
    """'brand-500' -> 'brand'. None when the key is not a `family-step` token name at all."""
    m = _KEY_RE.match(key or '')
    return m.group(1) if m else None


def validate_tokens(tokens):
    """Refuse anything a tenant may not store. Raises ThemeTokenError with a plain reason.

    Called from `OrganisationTheme.save()`, so it is the seam EVERY writer passes — the management
    command, A2's endpoint, and a shell caller alike. A guard only on the endpoint would be a
    request rather than a rule.
    """
    if not isinstance(tokens, dict):
        raise ThemeTokenError('tokens must be an object')
    if set(tokens) != set(MODES):
        raise ThemeTokenError(f'tokens must carry exactly {sorted(MODES)}, got {sorted(tokens)}')

    for mode in MODES:
        block = tokens[mode]
        if not isinstance(block, dict) or not block:
            raise ThemeTokenError(f'{mode}: must be a non-empty object of tokens')
        for key, value in block.items():
            family = family_of(key)
            if family is None:
                raise ThemeTokenError(f'{mode}: {key!r} is not a `family-step` token name')
            if family in PLATFORM_FAMILIES:
                raise ThemeTokenError(
                    f'{mode}: {key!r} belongs to the platform — a tenant may not set a '
                    f'{family} colour'
                )
            if family not in TENANT_FAMILIES:
                raise ThemeTokenError(f'{mode}: {key!r} is not a family a tenant may set')
            if int(_KEY_RE.match(key).group(2)) not in STEPS:
                raise ThemeTokenError(f'{mode}: {key!r} is not one of the ten steps')
            _validate_triplet(mode, key, value)

    if set(tokens['light']) != set(tokens['dark']):
        raise ThemeTokenError('light and dark must define the same token names')

    # The identity stop. A mode change may never alter whose product you are looking at.
    for family in TENANT_FAMILIES:
        key = f'{family}-{IDENTITY_STEP}'
        if key in tokens['light'] and tokens['light'][key] != tokens['dark'][key]:
            raise ThemeTokenError(
                f'{key} must be identical in light and dark — it is the tenant identity, '
                'and a mode may not change it'
            )
    return tokens


def _validate_triplet(mode, key, value):
    m = _TRIPLET_RE.match(value) if isinstance(value, str) else None
    if not m:
        raise ThemeTokenError(f"{mode}: {key} must be an 'r g b' triplet, got {value!r}")
    for channel in m.groups():
        if not 0 <= int(channel) <= 255:
            raise ThemeTokenError(f'{mode}: {key} has a channel outside 0-255')


def applied_tokens(tokens):
    """The subset of a STORED set that is safe to paint, re-filtered on the way out.

    Defence in depth, and cheap: the fence runs at write time, but a row edited around the ORM (a
    console, a restore, a future migration) must not be able to repaint a tone. The web app filters
    the same way for the same reason.
    """
    if not isinstance(tokens, dict):
        return None
    out = {}
    for mode in MODES:
        block = tokens.get(mode)
        if not isinstance(block, dict):
            return None
        out[mode] = {
            k: v for k, v in block.items()
            if family_of(k) in TENANT_FAMILIES and isinstance(v, str) and _TRIPLET_RE.match(v)
        }
        if not out[mode]:
            return None
    return out
