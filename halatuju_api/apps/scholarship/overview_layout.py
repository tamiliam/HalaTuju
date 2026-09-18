"""The organisation's Overview layout — which widgets show, and in what order.

Owner ruling, 2026-09-18 ("Programme Overview phase 2"): the layout is PER ORGANISATION, set by
the org admin, read by everyone in that organisation. It lives in its own table
(`OrganisationOverviewLayout`) rather than in `courses.org_config`, because that module is a
catalogue of integer settings by doctrine — "a catalogue, not a form builder" — and an ordered
list of switches is exactly the form-builder case it refuses.

⚠⚠ **THE LAYOUT NARROWS AND ORDERS. IT NEVER WIDENS.** `apply()` takes the sections a ROLE is
entitled to (`programme_overview.SECTIONS_BY_ROLE`) and returns the subset the organisation has
switched on, in the organisation's order. A key in the layout that the role may not see is
dropped; nothing is ever added. Role shaping stays the second gate it always was.

⚠ **`mine` AND `qc` ARE PAGES, NOT WIDGETS.** A reviewer's Overview is their queue; a QC's is
theirs. They are outside `CUSTOMISABLE`, so an org admin cannot switch a colleague's whole page
off, and `apply()` passes them through untouched at the end.

⚠ **THE STORED LIST IS ORDERED FROM DAY ONE**, so the second sprint (drag-and-drop order) needs
no migration — it only lets people change an order that is already stored.

⚠ A layout that hides every widget a role may see leaves that role with `sections: []` and a
200: the page says "your organisation has switched every panel off". The 403 in the view stays
on `sections_for(admin)` being empty — entitlement is a different question from preference.
"""
from __future__ import annotations

#: The five widgets an organisation may switch off or reorder, in the default order. Must equal
#: `programme_overview.FULL` — `test_overview_layout` pins the two together, and it is a literal
#: here (not an import) so this module has no dependency on the page module that reads it.
CUSTOMISABLE = ('funnel', 'money', 'attention', 'applications_series', 'money_series')


class OverviewLayoutError(ValueError):
    """A layout the fence refuses. `.code` names the reason, `.key` the offending section."""

    def __init__(self, code, key=None):
        super().__init__(code)
        self.code = code
        self.key = key


def default():
    """Every widget on, in the default order — what an organisation with no row sees."""
    return [{'key': key, 'on': True} for key in CUSTOMISABLE]


def validate_sections(value):
    """Refuse anything that is not an ordered permutation of `CUSTOMISABLE` with boolean flags.

    ⚠ ALL-OR-NOTHING AND EXACT: no unknown key (a typo would be silently ignored for ever), no
    duplicate (which of the two orders wins?), no missing key (a widget that vanished from the
    list would vanish from the page with nothing to switch it back on). `bool` is checked with
    `isinstance`, so `1`/`0` and `"true"` are refused — JSON from a browser is `true`/`false`.
    """
    if not isinstance(value, list):
        raise OverviewLayoutError('bad_layout')
    seen = []
    for item in value:
        if not isinstance(item, dict):
            raise OverviewLayoutError('bad_layout')
        key = item.get('key')
        if key not in CUSTOMISABLE:
            raise OverviewLayoutError('bad_section', key)
        if key in seen:
            raise OverviewLayoutError('duplicate_section', key)
        if not isinstance(item.get('on'), bool):
            raise OverviewLayoutError('bad_flag', key)
        seen.append(key)
    for key in CUSTOMISABLE:
        if key not in seen:
            raise OverviewLayoutError('missing_section', key)


def normalised(value):
    """The list as stored: only `key` and `on`, in the given order. Validates first."""
    validate_sections(value)
    return [{'key': item['key'], 'on': bool(item['on'])} for item in value]


def for_org(org):
    """The organisation's stored layout, or the default when it has never saved one."""
    from .models import OrganisationOverviewLayout

    if org is None:
        return default()
    # org-fence: reached by `organisation=org`, and `org` is the caller's own tenant (or the
    # named gift's owner under the platform scope) — resolved by `programme_overview.build`.
    stored = (OrganisationOverviewLayout.objects
              .filter(organisation=org)
              .values_list('sections', flat=True).first())
    if not stored:
        return default()
    try:
        return normalised(stored)
    except OverviewLayoutError:
        # A row the model's own fence would have refused — only reachable by a hand edit of the
        # table. The page is worth more than the preference, so fall back rather than 500.
        return default()


def apply(layout, role_sections):
    """The sections to build for this role under this layout, in layout order.

    ⚠ NARROWS, ORDERS, NEVER WIDENS. A layout key the role is not entitled to is dropped; a role
    section outside `CUSTOMISABLE` (`mine`, `qc`) is appended untouched — it is a page, not a
    widget, and no organisation may switch a colleague's page off.
    """
    allowed = tuple(role_sections)
    chosen = [item['key'] for item in layout if item['on'] and item['key'] in allowed]
    fixed = [s for s in allowed if s not in CUSTOMISABLE]
    return chosen + fixed
