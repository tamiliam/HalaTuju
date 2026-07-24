"""Sprint 6 — the FE-visual accessors added to the branding seam: ``brand_colour`` /
``logo_url`` / ``org_short_name``. (The programme/persona/sender/domain accessors are covered by
``test_email_branding.py``; this file exists because there was no ``test_branding.py`` — the brief's
"extend tests/test_branding.py" is satisfied by creating it for the new accessors.)"""
from types import SimpleNamespace

from apps.scholarship import branding


def _tenant(**overrides):
    base = dict(
        code='inspire', name='Inspire Foundation',
        brand_colour='', logo_url='',
        programme_name_en='', programme_name_ms='', programme_name_ta='',
        persona_name_en='', persona_name_ms='', persona_name_ta='',
        email_from='', email_reply_to='', email_support='', frontend_url='',
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_platform_visual_identity():
    b = branding.platform()
    assert b.brand_colour == '#137fec'
    assert b.logo_url == ''
    assert b.org_short_name == 'BrightPath'


def test_platform_org_code_resolves_to_platform_visuals():
    # An org whose code IS the platform code renders the platform block, not its own columns.
    org = _tenant(code=branding.PLATFORM_ORG_CODE, brand_colour='#ff0000', name='Whatever')
    b = branding.for_organisation(org)
    assert b.brand_colour == '#137fec'
    assert b.org_short_name == 'BrightPath'


def test_tenant_uses_own_visual_columns():
    b = branding.for_organisation(_tenant(
        brand_colour='#a21caf', logo_url='https://cdn.inspire.example/logo.png',
        name='Inspire Foundation'))
    assert b.brand_colour == '#a21caf'
    assert b.logo_url == 'https://cdn.inspire.example/logo.png'
    assert b.org_short_name == 'Inspire Foundation'


def test_tenant_blank_columns_fall_through_to_platform():
    b = branding.for_organisation(_tenant(brand_colour='   ', logo_url=''))
    assert b.brand_colour == '#137fec'
    assert b.logo_url == ''  # platform default is '' anyway
    # org_short_name derives from name; a blank name falls through to the platform short name.
    b2 = branding.for_organisation(_tenant(name='   '))
    assert b2.org_short_name == 'BrightPath'


def test_accessors_never_raise_on_missing_org():
    b = branding.for_organisation(None)
    assert b.brand_colour == '#137fec'
    assert b.logo_url == ''
    assert b.org_short_name == 'BrightPath'
