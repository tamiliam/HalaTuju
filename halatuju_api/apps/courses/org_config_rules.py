"""Cross-field rules for organisation configuration — timings checked TOGETHER.

Split out of `org_config.py` (org-timing Sprint 1, 2026-10-07) with no behaviour change.
`org_config.validate_values` calls in here; nothing else should.
"""
from .org_config_registry import OrgConfigError, default


# Cross-field rules: (earlier key, later key, code). A single key's bounds cannot express
# "the window must open before it closes", and a window stored inverted would offer the
# reviewer an empty picker with nothing on screen saying why.
_ORDERED_PAIRS = (
    ('interview_window_start_min', 'interview_window_end_min', 'window_inverted'),
)


def _check_pairs(values):
    """Cross-field rules, resolved against the platform default for any key not stored.

    ⚠ Runs on a WHOLE settings dict, never on a diff: an organisation that stores only the
    closing time is still describing a window whose other end is the platform default, so
    checking the pair needs both sides resolved — and a diff has only one.
    """
    for earlier, later, code in _ORDERED_PAIRS:
        a = values.get(earlier)
        b = values.get(later)
        if a is None and b is None:
            continue
        a = default(earlier) if a is None else a
        b = default(later) if b is None else b
        if a >= b:
            # Name the LATER key: it is the box the person was most likely typing in.
            raise OrgConfigError(code, later)
