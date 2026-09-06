"""Organisation-wide configuration — the registry and the read seam (Org Config Sprint A).

An organisation may TUNE a small set of platform values from Organisation → Settings →
Configuration. This module is the ONE home for three things:

  * the REGISTRY (`SETTINGS`) — which keys exist, their bounds, their unit, and where the
    platform default comes from;
  * the STORAGE FENCE (`validate_values`) — run in `OrganisationConfiguration.save()`, so a
    shell caller cannot store junk any more than an endpoint can;
  * the READ SEAM (`value` / `stored` / `custom_values`) — what product code calls.

⚠ CATALOGUE, NOT A FORM BUILDER (the Layer 0 rule). An organisation sets a VALUE for a key we
defined, bounded by limits we defined; it never invents a key. Adding a setting means adding a
registry entry AND wiring the read site — a setting that appears on the tab with nothing reading
it is the "UI asserts what nothing checks" defect by construction, so do neither without the other.

⚠ BLANK MEANS PLATFORM DEFAULT, AND THE DEFAULT DELEGATES TO DJANGO SETTINGS. An organisation
with no row (or no key) behaves byte-identically to the platform before this module existed —
deploying a new registry entry changes nothing visible by itself. The stored dict holds ONLY what
the organisation changed, so tightening a platform default later reaches every org that never
chose (the same reasoning that keeps `None` meaning "not applied" on intake-year requirements).
"""
from django.conf import settings


class OrgConfigError(ValueError):
    """A value the registry refuses. `code` is machine-readable; `key` names the setting."""

    def __init__(self, code, key=''):
        self.code = code
        self.key = key
        super().__init__(f'{code}: {key}' if key else code)


def _default_pool_funded_grace_days():
    # The platform value has always lived in HOURS (`POOL_FUNDED_GRACE_HOURS`, default 48 —
    # owner 2026-07-21). The owner's unit for the tab is DAYS (owner 2026-09-06: "extend to
    # 30 days"), so the registry speaks days and converts here: 48h → 2.0. Kept as a float so a
    # fractional env override is honoured, never silently rounded.
    hours = float(getattr(settings, 'POOL_FUNDED_GRACE_HOURS', 48) or 48)
    return hours / 24.0


# key → {group, unit, min, max, default}. `default` is a CALLABLE, evaluated per read, because
# several platform defaults are env vars that can change without a deploy.
SETTINGS = {
    # How long a just-funded student lingers as a read-only "Funded" card on the sponsor browse
    # page before dropping off (`pool.display_pool_queryset`). Owner 2026-09-06: BrightPath wants
    # 30 days; the platform default stays 2.
    'pool_funded_grace_days': {
        'group': 'sponsor_page',
        'unit': 'days',
        'min': 1,
        'max': 90,
        'default': _default_pool_funded_grace_days,
    },
}


def default(key):
    """The platform default for `key`, read live from Django settings."""
    return SETTINGS[key]['default']()


def validate_values(values):
    """The storage fence. Raises `OrgConfigError` on anything the registry refuses.

    Run inside `OrganisationConfiguration.save()` — the model is where the fence lives
    (the `OrganisationTheme.save()` precedent), so every writer passes it.
    """
    if not isinstance(values, dict):
        raise OrgConfigError('bad_values')
    for key, value in values.items():
        spec = SETTINGS.get(key)
        if spec is None:
            raise OrgConfigError('unknown_setting', key)
        # `bool` IS an `int` in Python — refuse it explicitly or `True` stores as 1.
        if isinstance(value, bool) or not isinstance(value, int):
            raise OrgConfigError('bad_value', key)
        if value < spec['min'] or value > spec['max']:
            raise OrgConfigError('out_of_range', key)


def stored(organisation, key):
    """The value the organisation CHANGED, or None. None means "use the platform default"."""
    if organisation is None:
        return None
    # The reverse OneToOne raises RelatedObjectDoesNotExist, an AttributeError subclass —
    # which is exactly why getattr-with-default is the sanctioned spelling.
    row = getattr(organisation, 'configuration', None)
    if row is None:
        return None
    return (row.values or {}).get(key)


def value(organisation, key):
    """What the product should USE: the organisation's stored value, else the platform default."""
    v = stored(organisation, key)
    return default(key) if v is None else v


def custom_values(key):
    """{organisation_id: stored value} for every organisation that changed `key`.

    For query-time consumers with no single organisation in hand — the sponsor pool filters
    applications of MANY organisations in one queryset, so it needs the whole map, not one value.
    Organisations absent from the map follow the platform default.
    """
    from .models import OrganisationConfiguration
    out = {}
    for org_id, values in OrganisationConfiguration.objects.values_list(
            'organisation_id', 'values'):
        v = (values or {}).get(key)
        if v is not None:
            out[org_id] = v
    return out
