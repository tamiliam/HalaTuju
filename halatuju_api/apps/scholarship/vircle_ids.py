"""The Vircle eWallet ID rules (D9) — moved VERBATIM out of ``payments.py`` (student maintenance
Sprint 1, 2026-10-29, a moves-only split: ``payments.py`` sat at its ``oversize_files`` allowance and
the sprint's on-hold money doors had to be added to it). Every name is re-exported from ``payments``,
so ``payments.valid_vircle_id`` / ``payments.vircle_id_error`` / ``payments.vircle_id_prefix`` /
``payments.vircle_id_band`` resolve exactly as before and no caller changed.
"""
import logging

from django.conf import settings

#: ⚠ THE OLD LOGGER NAME, WRITTEN OUT: the band warning below was logged as
#: ``apps.scholarship.payments`` before the move, and a log filter keyed on it must not go quiet.
logger = logging.getLogger('apps.scholarship.payments')


def vircle_id_prefix():
    return getattr(settings, 'VIRCLE_ID_PREFIX', '80004001')


def vircle_id_band():
    """(low, high) — the inclusive range the FIRST digit the student types may take.

    Env-tunable (``VIRCLE_ID_BAND_MIN``/``_MAX``, see settings/base.py for the full reasoning):
    the band is what separates a real eWallet ID from a **truncated DuitNow Transfer number**,
    which shares the prefix and the length and is therefore invisible to a length+prefix check.
    """
    lo = str(getattr(settings, 'VIRCLE_ID_BAND_MIN', '7'))[:1] or '7'
    hi = str(getattr(settings, 'VIRCLE_ID_BAND_MAX', '9'))[:1] or '9'
    return lo, hi


def valid_vircle_id(value):
    """D9: a full 13-digit ID starting with the standard prefix, whose first TYPED digit sits in
    the issued band. Shared by the Action-Centre resolve endpoint and the admin PATCH path — one
    home, so both write paths cannot drift.

    The band check is the half that catches a DuitNow Transfer number truncated to its last few
    digits (three live cases, 2026-07-29). Do NOT relax it to make a fixture pass: build fixtures
    with in-band suffixes instead.

    The prefix is 8 digits since 2026-08-27 (was 9): Vircle's sequence rolled past 800040017xxxx
    and a 4-digit box could not take the new numbers at all. See settings/base.py for the history.
    """
    v = (value or '').strip()
    prefix = vircle_id_prefix()
    if not (v.isdigit() and len(v) == 13 and v.startswith(prefix)):
        return False
    if len(prefix) >= 13:            # a prefix that leaves nothing typed: length+prefix is all there is
        return True
    lo, hi = vircle_id_band()
    band = v[len(prefix)]
    if not (lo <= band <= hi):
        return False
    if band == hi:
        # Approaching the end of the issued block. When Vircle rolls past it every NEW student is
        # refused (or cannot even type the number) until the prefix shortens, so this wants to be
        # seen before that happens, not after. It fired four times in Aug 2026 and nobody read
        # the log — the relay sheet's "no id yet" rows are the signal a human actually sees.
        logger.warning(
            'vircle_id accepted at the TOP of the issued band (digit %s of %s-%s) — '
            'the next block needs a SHORTER VIRCLE_ID_PREFIX (settings + ActionCentre.tsx)',
            band, lo, hi)
    return True


def vircle_id_error(value):
    """WHICH thing is wrong with a supplied eWallet ID — ``''`` when it is valid.

    ``'duitnow'`` means the value looks like a DuitNow Transfer number (the whole 18-digit thing,
    or the last five digits of one). That distinction earns its keep in the COPY: the student typed
    exactly what was on their screen, so "check the number and try again" is both useless and
    faintly accusing — they need telling WHICH field to read instead. ``'format'`` is everything
    else (wrong length, non-digits, a different prefix).
    """
    v = (value or '').strip()
    if valid_vircle_id(v):
        return ''
    prefix = vircle_id_prefix()
    if not (v.isdigit() and v.startswith(prefix)):
        return 'format'
    # A DuitNow number's first 13 digits ARE the eWallet ID, so it shares the prefix; either the
    # whole 18 digits, or a 13-digit value whose typed part falls outside the issued band.
    if len(v) == 18 or len(v) == 13:
        return 'duitnow'
    return 'format'
