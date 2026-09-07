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


def _default_sponsor_email_max_cards():
    # The one platform home has always been the env-tunable `SPONSOR_EMAIL_MAX_CARDS` (owner
    # 2026-07-18: keep it to 5). `sponsor_comms` used to carry its OWN literal 5 beside it;
    # Sprint B collapsed both render sites onto this single default so they can never disagree.
    return int(getattr(settings, 'SPONSOR_EMAIL_MAX_CARDS', 5) or 5)


def _default_query_email_delay_hours():
    # The platform value is a module constant, not a Django setting — imported lazily because
    # `services` lives in apps.scholarship and importing it at module load would be circular.
    from apps.scholarship.services import QUERY_EMAIL_DELAY_HOURS
    return QUERY_EMAIL_DELAY_HOURS


def _default_nudge_auto_delay_minutes():
    return int(getattr(settings, 'NUDGE_AUTO_DELAY_MINUTES', 30))


def _default_nudge_cooldown_hours():
    return int(getattr(settings, 'NUDGE_COOLDOWN_HOURS', 24))


def _default_max_clarify_open():
    # Module constant (design §4: a long list suppresses student responses) — lazy import, as above.
    from apps.scholarship.check2_queries import MAX_CLARIFY
    return MAX_CLARIFY


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
    # How many student cards a sponsor notification email shows before "and N more" (a teaser —
    # the button leads to the full pool). ONE value drives BOTH render sites: the pre-template
    # sender (`emails._send_sponsor_notify`) and the template block
    # (`sponsor_comms.student_cards_blocks`). Deferred out of Sprint A because neither carried
    # an organisation; Sprint B threads it through the batch's applications.
    'sponsor_email_max_cards': {
        'group': 'sponsor_page',
        'unit': 'cards',
        'min': 1,
        'max': 20,
        'default': _default_sponsor_email_max_cards,
    },
    # ── student comms (Sprint B) ──
    # How long after submission the "we have a few questions" email is held, so it reads as a
    # human review rather than an instant bot reply (`services.send_due_query_emails`).
    'query_email_delay_hours': {
        'group': 'student_comms',
        'unit': 'hours',
        'min': 1,
        'max': 168,
        'default': _default_query_email_delay_hours,
    },
    # The one-time automatic "you haven't submitted yet" nudge fires this long after consent
    # (`nudge._auto_delay` — the highest-chance moment is while the student is still at their
    # device, hence a minutes-scale value).
    'nudge_auto_delay_minutes': {
        'group': 'student_comms',
        'unit': 'minutes',
        'min': 5,
        'max': 1440,
        'default': _default_nudge_auto_delay_minutes,
    },
    # How long an org admin's MANUAL re-nudge is rate-limited after any nudge (`nudge._cooldown`).
    'nudge_cooldown_hours': {
        'group': 'student_comms',
        'unit': 'hours',
        'min': 1,
        'max': 168,
        'default': _default_nudge_cooldown_hours,
    },
    # How many Check-2 clarify questions may be OPEN at once (`check2_queries`). Doc requests and
    # the one-tap confirms sit OUTSIDE this cap by design — only typed-answer questions count.
    'max_clarify_open': {
        'group': 'student_comms',
        'unit': 'questions',
        'min': 1,
        'max': 10,
        'default': _default_max_clarify_open,
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
