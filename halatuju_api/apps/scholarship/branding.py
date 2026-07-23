"""Per-organisation branding — the ONE read seam for tenant branding columns (platform
Sprint 5, decision D1).

Every org-branding value used to RENDER an email or a coach persona is read here and only
here. No other module reads `PartnerOrganisation.programme_name_* / team_signoff_* /
persona_name_* / email_* / frontend_url` for rendering.

Design (byte-identity contract, D2):

* ``PLATFORM`` is the single sanctioned home for today's brand literals ("BrightPath …",
  "Cikgu Gopal", "halatuju.xyz"). The AST brand-guard (test_branding_guard.py) allows these
  literals ONLY in this block. Values that vary by deployment (sender identity, frontend URL)
  read live from settings, exactly as the pre-extraction code did — so the output is identical
  in every environment, not just prod.

* The PLATFORM tenant (BrightPath, org #1) renders from ``PLATFORM`` verbatim — it does NOT read
  its own seeded columns. This is deliberate: several of BrightPath's seeded columns intentionally
  differ from the byte-exact runtime values the emails actually produce (``email_from`` is
  settings-driven, not the ``info@halatuju.xyz`` column; ``persona_name_ta`` renders in Tamil
  script ``சிக்கு கோபால்`` in email bodies while the column is Latin ``Cikgu Gopal``; the award
  email prints the bare display domain ``halatuju.xyz`` regardless of ``FRONTEND_URL``). Reading
  ``PLATFORM`` keeps BrightPath byte-identical to the pre-extraction output.

* A TENANT org (any other org) renders from its own columns, falling through per D3:
  requested-language column -> that org's `_en` column -> the PLATFORM per-language default ->
  PLATFORM English. An empty column ('') always falls through; a missing/None org falls through
  entirely to PLATFORM, so best-effort emails never raise.

Topical aliases (``interview@`` / ``sponsor@``) are platform-domain features (D4): they apply
only while the sender identity is on the platform domain (the platform tenant). A tenant with its
OWN ``email_from`` domain gets that address for all mail — no per-topic aliases until a tenant asks.
"""
from django.conf import settings

# The org code of the platform tenant (BrightPath is seeded as org #1). Its branding IS the
# platform default, so it renders from PLATFORM rather than its own seeded columns (see above).
PLATFORM_ORG_CODE = 'brightpath'

# ── PLATFORM defaults — today's brand constants, byte-exact (guard allowlist) ─────────────────
# Sender identity + frontend URL read live from settings (env-dependent, exactly as before);
# everything else is the literal brand copy the emails render today.
_PLATFORM_FROM_FALLBACK = 'info@halatuju.xyz'
_FRONTEND_FALLBACK = 'https://halatuju.xyz'

PLATFORM = {
    # Trilingual programme name (the {programme} used by the hard-coded brand emails).
    'programme_name': {
        'en': 'BrightPath Bursary',
        'ms': 'Bursari BrightPath',
        'ta': 'BrightPath Bursary',
    },
    # Trilingual team sign-off line (the line after the "Warm regards," prefix).
    'team_signoff': {
        'en': 'The BrightPath Bursary Team',
        'ms': 'Pasukan Program Bursari BrightPath',
        'ta': 'BrightPath Bursary குழு',
    },
    # Coach persona as rendered IN EMAIL BODIES (Tamil in Tamil script). help_engine renders the
    # coach's proper-noun name via persona_name('en') — see help_engine for why.
    'persona_name': {
        'en': 'Cikgu Gopal',
        'ms': 'Cikgu Gopal',
        'ta': 'சிக்கு கோபால்',
    },
    # Support / reply-to address (the SUPPORT_EMAIL constant + the seeded email_support/reply_to).
    'email_support': 'help@halatuju.xyz',
    'email_reply_to': 'help@halatuju.xyz',
    # Topical platform-domain aliases (D4).
    'interview_from': 'interview@halatuju.xyz',
    'interview_reply_to': 'interview@halatuju.xyz',
    'sponsor_reply_to': 'sponsor@halatuju.xyz',
    # Display domain shown in prose ("sign in at halatuju.xyz") and the .ics calendar UID. This is
    # a brand token, NOT the functional FRONTEND_URL (which is http://localhost:3000 in dev); the
    # .ics UID additionally stays on the fixed platform domain so calendar identities are stable.
    'frontend_domain': 'halatuju.xyz',
    'ics_uid_domain': 'halatuju.xyz',
}


def _platform_from_email():
    """Platform sender identity = the deployment's DEFAULT_FROM_EMAIL (settings-driven, exactly as
    the pre-extraction ``getattr(settings, 'DEFAULT_FROM_EMAIL', …)`` sites did)."""
    return getattr(settings, 'DEFAULT_FROM_EMAIL', _PLATFORM_FROM_FALLBACK)


def _platform_frontend_url():
    """Functional frontend base URL (settings-driven), trailing slash stripped — the value the
    ~15 ``getattr(settings, 'FRONTEND_URL', …).rstrip('/')`` sites produced."""
    return getattr(settings, 'FRONTEND_URL', _FRONTEND_FALLBACK).rstrip('/')


def _strip_scheme(url):
    return url.split('://', 1)[-1].rstrip('/')


class Branding:
    """Resolved branding for one organisation (or the platform). All accessors are total — they
    never raise, so a best-effort email with a missing org link still renders."""

    __slots__ = ('_org', '_is_platform')

    def __init__(self, org, is_platform):
        self._org = org
        self._is_platform = is_platform

    # ── per-language brand copy ──────────────────────────────────────────────────────────────
    def _lang_value(self, field):
        """Resolve a `{field}_{lang}` group with the D3 fallback chain."""
        plat = PLATFORM[field]

        def resolve(lang):
            if not self._is_platform and self._org is not None:
                own = (getattr(self._org, f'{field}_{lang}', '') or '').strip()
                if own:
                    return own
                own_en = (getattr(self._org, f'{field}_en', '') or '').strip()
                if own_en:
                    return own_en
            return plat.get(lang) or plat['en']

        return resolve

    def programme_name(self, lang):
        return self._lang_value('programme_name')(lang)

    def team_signoff(self, lang):
        return self._lang_value('team_signoff')(lang)

    def persona_name(self, lang):
        return self._lang_value('persona_name')(lang)

    # ── sender identity ──────────────────────────────────────────────────────────────────────
    @property
    def email_from(self):
        # The platform tenant's from-identity is the deployment default (settings). A tenant with
        # its own configured sender uses it; otherwise it falls through to the platform default.
        if not self._is_platform and self._org is not None and (self._org.email_from or '').strip():
            return self._org.email_from.strip()
        return _platform_from_email()

    @property
    def email_reply_to(self):
        if not self._is_platform and self._org is not None:
            own = (self._org.email_reply_to or '').strip() or (self._org.email_from or '').strip()
            if own:
                return own
        return PLATFORM['email_reply_to']

    @property
    def email_support(self):
        if not self._is_platform and self._org is not None:
            own = (self._org.email_support or '').strip()
            if own:
                return own
        return PLATFORM['email_support']

    # Topical aliases (D4): platform-domain features. On the platform tenant they are the
    # dedicated aliases; a tenant with its own sender domain gets its own from/reply-to for all
    # mail — no per-topic aliases until a tenant asks for them.
    @property
    def interview_from(self):
        return PLATFORM['interview_from'] if self._is_platform else self.email_from

    @property
    def interview_reply_to(self):
        return PLATFORM['interview_reply_to'] if self._is_platform else self.email_reply_to

    @property
    def sponsor_reply_to(self):
        return PLATFORM['sponsor_reply_to'] if self._is_platform else self.email_reply_to

    # ── URLs / display domain ────────────────────────────────────────────────────────────────
    @property
    def frontend_url(self):
        if not self._is_platform and self._org is not None and (self._org.frontend_url or '').strip():
            return self._org.frontend_url.strip().rstrip('/')
        return _platform_frontend_url()

    @property
    def frontend_domain(self):
        """Bare display domain for prose ("sign in at <domain>"). Platform = the brand constant
        'halatuju.xyz'; a tenant = the host of its own frontend_url."""
        if not self._is_platform and self._org is not None and (self._org.frontend_url or '').strip():
            return _strip_scheme(self._org.frontend_url.strip())
        return PLATFORM['frontend_domain']

    @property
    def ics_uid_domain(self):
        # Calendar UIDs stay on the fixed platform domain for identity stability across tenants.
        return PLATFORM['ics_uid_domain']


# The single platform Branding instance (BrightPath / no org).
_PLATFORM_BRANDING = Branding(org=None, is_platform=True)


def platform():
    """The platform branding — today's constants. The default for every send_* that isn't handed
    a tenant branding, so an un-wired caller renders byte-identically to before."""
    return _PLATFORM_BRANDING


def for_organisation(org):
    """Branding for an organisation. None or the platform org -> platform defaults; any other org
    -> that tenant's columns (falling through to platform)."""
    if org is None or getattr(org, 'code', None) == PLATFORM_ORG_CODE:
        return _PLATFORM_BRANDING
    return Branding(org=org, is_platform=False)


def for_application(app):
    """Branding for the organisation that OWNS the application's cohort. Tolerant of every missing
    link (no cohort, no owning_organisation) -> platform defaults, so it never raises."""
    org = None
    try:
        cohort = getattr(app, 'cohort', None)
        if cohort is not None:
            org = getattr(cohort, 'owning_organisation', None)
    except Exception:
        org = None
    return for_organisation(org)
