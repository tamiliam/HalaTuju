"""R5 — Trust & Transparency hub content.

Assembles the four-layer trust story for an approved sponsor's hub:
  1. Who we are       — org / legal entity / contact   (placeholder until formalised)
  2. Governance       — trustee board                  (placeholder until appointed)
  3. Sources & uses   — programme-wide money, IR-style  (illustrative figures now)
  4. Independent assurance — annual, layered            (illustrative figures now)

The EDITABLE, language-neutral data comes from the single active ``TrustContent``
row (so the org fills it in over time WITHOUT a deploy). The live community counts
are computed truthfully from the DB. The trilingual UI chrome lives in the frontend
i18n — this module returns DATA only, never display copy. No PII ever crosses here:
programme-level content + counts only, so it is allowlist-safe by construction.
"""
from . import sponsor_feed
from .models import TrustContent


def _default_content():
    """The honest empty state if no row exists yet (defensive — the migration
    seeds one). Mirrors the seeded placeholders so the hub always renders."""
    return {
        'legal_entity': '',
        'contact_email': 'help@halatuju.xyz',
        'trustees': [],
        'sources': [],
        'uses': [],
        'assurance': {},
        'figures_are_illustrative': True,
    }


def get_trust_content():
    """Return the trust-hub payload: the editable content row + live community
    counts. Figures are flagged ``figures_are_illustrative`` so the FE can show an
    'illustrative' pill until real audited figures are published."""
    row = TrustContent.objects.filter(is_active=True).order_by('-updated_at').first()
    if row is None:
        content = _default_content()
    else:
        content = {
            'legal_entity': row.legal_entity or '',
            'contact_email': row.contact_email or 'help@halatuju.xyz',
            'trustees': row.trustees if isinstance(row.trustees, list) else [],
            'sources': row.sources if isinstance(row.sources, list) else [],
            'uses': row.uses if isinstance(row.uses, list) else [],
            'assurance': row.assurance if isinstance(row.assurance, dict) else {},
            'figures_are_illustrative': bool(row.figures_are_illustrative),
        }
    # Live, truthful programme counts (no identity): the one part we can state as fact.
    content['community'] = sponsor_feed.community_stats()
    return content
