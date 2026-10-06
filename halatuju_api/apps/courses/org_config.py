"""Organisation-wide configuration — the registry and the read seam (Org Config Sprint A).

An organisation may TUNE a small set of platform values from Organisation → Settings →
Configuration. This module is the ONE door to three things:

  * the REGISTRY (`SETTINGS`) — which keys exist, their bounds, their unit, and where the
    platform default comes from. Since org-timing Sprint 1 (2026-10-07) its body lives in
    `org_config_registry.py` and the cross-field rules in `org_config_rules.py`; both are
    re-exported here, so callers read `org_config.SETTINGS` exactly as before;
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
from .org_config_registry import OrgConfigError, SETTINGS, default  # re-exported: the seam
from .org_config_rules import RULES, check_rules


def is_rule_code(code):
    """True when `code` is a cross-field rule's refusal (`org_config_rules.RULES`), not a
    single key's (`out_of_range`, `bad_value`, …). Served on the endpoint's refusal."""
    return any(rule.code == code for rule in RULES)


def validate_values(values, *, pairs=True):
    """The storage fence. Raises `OrgConfigError` on anything the registry refuses.

    Run inside `OrganisationConfiguration.save()` — the model is where the fence lives
    (the `OrganisationTheme.save()` precedent), so every writer passes it.

    `pairs=False` checks each key ALONE, for a caller holding only the changed keys (the
    endpoint's first pass, which wants a per-key refusal code before it merges). With
    `pairs=True` the cross-field rules (`org_config_rules.RULES`) run on the whole dict too.
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
        allowed = spec.get('allowed')
        if allowed is not None and value not in allowed:
            raise OrgConfigError('not_allowed', key)
    if pairs:
        check_rules(values)


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


def max_doc_size_bytes(organisation):
    """The per-file upload cap in BYTES for one organisation.

    ⚠ THE ONE PLACE MB BECOMES BYTES. Every door that weighs an upload calls this; none of them
    carries its own `* 1024 * 1024`, because a second conversion is how one door starts refusing
    a file another door accepted. The value on the tab is MB (the owner's unit) and the wire
    talks bytes — this function is the join, and `views.py` reports the MB back on a refusal by
    dividing here-and-nowhere-else.
    """
    return value(organisation, 'max_doc_size_mb') * 1024 * 1024


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
