# -*- coding: utf-8 -*-
"""Sponsor terms — authoring, validation, publishing, and the reads a sponsor screen needs.

Mirrors `contracts.py` in SHAPE (a `SponsorTermsError` carrying a machine code; module-level
service functions over the models) and deliberately not in SIZE. The contract module is ~1,140
lines because a bursary agreement has a payment schedule, two signatories, a witness, a lawyer
attestation, a .docx importer and a PDF renderer. A sponsor-terms document has none of those.

What is kept from there, because it earns its keep:
  * draft immutability — every write funnels through `_require_draft`
  * publish as archive-then-activate inside ONE transaction, with `select_for_update`
  * a validation checklist of machine codes the frontend renders without knowing any rule
  * the single mockable Gemini seam, metered, with no downgrade fallback
  * per-item locale→en fallback, so a half-translated version can never be served half-rendered

What is deliberately dropped: hierarchy (sections are FLAT), tokens/merge variables (the
counterparty is named in prose, so a new entity is a new version rather than a templating
system), and any notion of a counter-signature.
"""
import json
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SponsorTermsAcceptance, SponsorTermsSection, SponsorTermsVersion

LANGUAGES = ('en', 'ms', 'ta')

# PATCHable intro fields. Anything outside this set is refused rather than silently ignored —
# two layers (this and the view's own filter) for one line of code each.
_CONFIG_FIELDS = (
    'title_en', 'title_ms', 'title_ta',
    'intro_en', 'intro_ms', 'intro_ta',
)

# Sponsor-facing labels for each validation code. The FE renders what the server says, so a rule
# can be added or reworded without touching the client.
RULE_LABELS = {
    'T1': 'Version, English title and English introduction are all required.',
    'C1': 'At least one section, numbered from 1 with no gaps.',
    'C2': 'Every section needs an English heading and body.',
    'Q1': 'At least one section must carry a quiz checkpoint.',
    'Q2': 'Every quiz checkpoint needs three options and one correct answer.',
    'Q3': 'A quiz answer is attached to a section that is no longer a checkpoint.',
    'Q4': 'A translated checkpoint must mark the SAME answer as the English one.',
    'W1': 'Malay or Tamil is incomplete — those sponsors will read English.',
}


class SponsorTermsError(Exception):
    """Carries a machine code the view maps to a 400 and the FE maps to copy."""

    def __init__(self, code, detail=''):
        super().__init__(code)
        self.code = code
        self.detail = detail


class ValidationResult:
    def __init__(self, errors, warnings):
        self.errors = sorted(set(errors))
        self.warnings = sorted(set(warnings))

    @property
    def ok(self):
        return not self.errors


def _require_draft(terms):
    """A published or archived version is IMMUTABLE — that is what lets a past acceptance point
    at an exact version forever and still mean something."""
    if terms.status != SponsorTermsVersion.STATUS_DRAFT:
        raise SponsorTermsError('not_draft')


# ── authoring (draft only) ───────────────────────────────────────────────────

@transaction.atomic
def create_version(*, version, copy_from=None, by_email=''):
    """A new draft, optionally deep-cloned from an existing version.

    The clone copies CONTENT (intro + every section, quiz payloads included) and never the
    lifecycle stamps — a copy of a published version is a fresh draft, not a published one.
    """
    version = (version or '').strip()
    if not version:
        raise SponsorTermsError('version_required')
    if SponsorTermsVersion.objects.filter(version=version).exists():
        raise SponsorTermsError('version_exists')

    terms = SponsorTermsVersion(version=version, created_by_email=by_email or '')
    if copy_from is not None:
        for f in _CONFIG_FIELDS:
            setattr(terms, f, getattr(copy_from, f))
    terms.save()

    if copy_from is not None:
        SponsorTermsSection.objects.bulk_create([
            SponsorTermsSection(
                terms=terms, order=sec.order,
                heading_en=sec.heading_en, heading_ms=sec.heading_ms, heading_ta=sec.heading_ta,
                body_en=sec.body_en, body_ms=sec.body_ms, body_ta=sec.body_ta,
                is_quiz_candidate=sec.is_quiz_candidate,
                quiz_en=sec.quiz_en, quiz_ms=sec.quiz_ms, quiz_ta=sec.quiz_ta,
                quiz_generated_model=sec.quiz_generated_model,
            )
            for sec in copy_from.sections.all()
        ])
    return terms


def update_intro(terms, fields, *, by_email=''):
    _require_draft(terms)
    unknown = set(fields) - set(_CONFIG_FIELDS)
    if unknown:
        raise SponsorTermsError('unknown_config_field', ', '.join(sorted(unknown)))
    for k, v in fields.items():
        setattr(terms, k, v or '')
    terms.save(update_fields=list(fields) + ['updated_at'])
    return terms


@transaction.atomic
def replace_sections(terms, rows):
    """Replace every section in one shot. `rows` is an ordered list of dicts.

    Orders are ASSIGNED here (1..N by position), never taken from the payload — the client cannot
    produce a gap or a duplicate even by accident.

    ⚠ A section whose quiz flag is cleared LOSES its payloads. A question cannot outlive the
    checkpoint it belonged to; leaving it behind is how the contract module's Q3 rule came to
    exist, and dropping it here means Q3 can only ever fire on hand-edited data.
    """
    _require_draft(terms)
    if not isinstance(rows, list):
        raise SponsorTermsError('sections_invalid')

    fresh = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SponsorTermsError('sections_invalid')
        flagged = bool(row.get('is_quiz_candidate'))
        sec = SponsorTermsSection(
            terms=terms, order=idx,
            is_quiz_candidate=flagged,
            quiz_generated_model=(row.get('quiz_generated_model') or '') if flagged else '',
        )
        for loc in LANGUAGES:
            setattr(sec, f'heading_{loc}', (row.get(f'heading_{loc}') or '').strip())
            setattr(sec, f'body_{loc}', (row.get(f'body_{loc}') or '').strip())
            payload = row.get(f'quiz_{loc}') or {}
            setattr(sec, f'quiz_{loc}', payload if (flagged and isinstance(payload, dict)) else {})
        fresh.append(sec)

    terms.sections.all().delete()
    SponsorTermsSection.objects.bulk_create(fresh)
    terms.save(update_fields=['updated_at'])
    return list(terms.sections.all())


# ── quiz generation ──────────────────────────────────────────────────────────

def _gemini_generate(prompt, model):
    """The single mockable seam — patched in every test, so no CI run can make a live call.

    NO downgrade fallback, matching the contract module's owner decision: an unconfigured or
    unavailable model raises rather than quietly producing something from a weaker one.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise SponsorTermsError('quiz_ai_unconfigured')
    try:
        from google import genai
    except ImportError:
        raise SponsorTermsError('quiz_ai_unavailable')
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    from . import usage   # billable — best-effort meter
    _it, _ot = usage.gemini_tokens(response)
    usage.record_usage(usage.GEMINI, model=model, input_tokens=_it, output_tokens=_ot)
    return response.text


def _build_quiz_prompt(section):
    """Strict-JSON prompt for one checkpoint in all three languages.

    The tone instruction is not decoration: this quiz is read by someone who has just offered to
    give money away, and a checkpoint that reads like an exam question is a reason to close the
    tab. Falls back to the English text where a translation is missing, so a partly-translated
    section still produces a usable ms/ta draft for the owner to correct.
    """
    def text(loc):
        h = getattr(section, f'heading_{loc}') or section.heading_en
        b = getattr(section, f'body_{loc}') or section.body_en
        return f'{h}\n{b}'.strip()

    return (
        'You are writing ONE comprehension checkpoint for a charity sponsor who is reading the '
        'terms they are about to accept. They are a volunteer donor, not a student and not a '
        'lawyer.\n\n'
        'Rules:\n'
        '- Warm, plain, concrete. Prefer a short realistic scenario over an abstract question.\n'
        '- Exactly THREE options, exactly one correct. The wrong ones must be plausible, never silly.\n'
        '- "why" explains the right answer in one or two sentences, in the second person.\n'
        '- "plain" restates the section in one sentence a person would actually say.\n'
        '- "tag" is two or three words naming the idea.\n'
        '- Never mention tax relief or a tax-deductible receipt.\n'
        '- Never imply the sponsor owns, chooses unilaterally, or may contact a student.\n\n'
        'Return STRICT JSON only, no prose, no code fence:\n'
        '{"en": {"tag": "", "plain": "", "question": "", "options": ["", "", ""], '
        '"correct": 0, "why": ""}, "ms": {...}, "ta": {...}}\n'
        'The "correct" index MUST be identical in all three languages.\n\n'
        f'ENGLISH SECTION:\n{text("en")}\n\n'
        f'MALAY SECTION:\n{text("ms")}\n\n'
        f'TAMIL SECTION:\n{text("ta")}\n'
    )


def _parse_quiz_json(raw):
    text = (raw or '').strip()
    if text.startswith('```'):                      # tolerate a ```json fence
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text).strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise SponsorTermsError('quiz_bad_json')
    if not isinstance(data, dict):
        raise SponsorTermsError('quiz_bad_json')
    return data


def quiz_payload_valid(payload):
    """The structural contract: exactly three non-blank options and a correct index in 0..2.

    `tag` / `plain` / `question` / `why` are deliberately NOT validated — they are prose, and a
    human reviews them in the editor. What is checked is the shape a wrong value would break.
    """
    if not isinstance(payload, dict):
        return False
    options = payload.get('options')
    if not isinstance(options, list) or len(options) != 3:
        return False
    if not all(isinstance(o, str) and o.strip() for o in options):
        return False
    return payload.get('correct') in (0, 1, 2)


def generate_quiz(section, *, model=None):
    """Draft a checkpoint for one section with Gemini. Draft-only, billable, metered."""
    _require_draft(section.terms)
    if not section.is_quiz_candidate:
        raise SponsorTermsError('quiz_not_candidate')

    model = model or getattr(settings, 'CONTRACT_QUIZ_MODEL', 'gemini-2.5-pro')
    from . import usage
    with usage.usage_context(source='sponsor_terms_quiz'):
        raw = _gemini_generate(_build_quiz_prompt(section), model)

    data = _parse_quiz_json(raw)
    if not quiz_payload_valid(data.get('en')):
        raise SponsorTermsError('quiz_invalid', 'en missing or malformed')

    section.quiz_en = data['en']
    for loc in ('ms', 'ta'):
        payload = data.get(loc)
        # A translation is kept only if it is BOTH structurally valid and marks the same answer.
        # A Tamil-reading sponsor being marked wrong for the right answer is the one failure this
        # whole feature cannot afford.
        keep = (quiz_payload_valid(payload)
                and payload.get('correct') == data['en'].get('correct'))
        setattr(section, f'quiz_{loc}', payload if keep else {})
    section.quiz_generated_model = model
    section.save(update_fields=['quiz_en', 'quiz_ms', 'quiz_ta', 'quiz_generated_model'])
    return section


# ── validation ───────────────────────────────────────────────────────────────

def validate_for_publish(terms):
    errors, warnings = [], []
    sections = list(terms.sections.all())

    if not (terms.version.strip() and terms.title_en.strip() and terms.intro_en.strip()):
        errors.append('T1')

    orders = [s.order for s in sections]
    if not sections or orders != list(range(1, len(sections) + 1)):
        errors.append('C1')

    if any(not s.heading_en.strip() or not s.body_en.strip() for s in sections):
        errors.append('C2')

    candidates = [s for s in sections if s.is_quiz_candidate]
    if not candidates:
        errors.append('Q1')
    if any(not quiz_payload_valid(s.quiz_en) for s in candidates):
        errors.append('Q2')

    # A payload on a section that is NOT a checkpoint — only reachable by a hand edit, since
    # `replace_sections` wipes them. Refusing it at publish is the backstop.
    if any((s.quiz_en or s.quiz_ms or s.quiz_ta)
           for s in sections if not s.is_quiz_candidate):
        errors.append('Q3')

    for s in candidates:
        for loc in ('ms', 'ta'):
            payload = getattr(s, f'quiz_{loc}')
            if not payload:
                continue
            if not quiz_payload_valid(payload) or payload.get('correct') != s.quiz_en.get('correct'):
                errors.append('Q4')

    if set(terms.languages_available) != set(LANGUAGES):
        warnings.append('W1')

    return ValidationResult(errors, warnings)


# ── lifecycle ────────────────────────────────────────────────────────────────

@transaction.atomic
def publish(terms, *, by_email='', is_super=False):
    """Make this version the active one, archiving whatever was active before.

    Super-only, and validated again HERE rather than trusting an earlier check — a publish must
    not be able to ride on a validation that passed before the last edit.
    """
    if not is_super:
        raise SponsorTermsError('publish_forbidden')
    _require_draft(terms)

    result = validate_for_publish(terms)
    if not result.ok:
        err = SponsorTermsError('not_publishable')
        err.errors = result.errors
        raise err

    now = timezone.now()
    previous = (SponsorTermsVersion.objects
                .select_for_update()
                .filter(status=SponsorTermsVersion.STATUS_ACTIVE)
                .exclude(pk=terms.pk))
    for old in previous:
        old.status = SponsorTermsVersion.STATUS_ARCHIVED
        old.archived_at = now
        old.save(update_fields=['status', 'archived_at', 'updated_at'])

    terms.status = SponsorTermsVersion.STATUS_ACTIVE
    terms.published_by_email = by_email or ''
    terms.published_at = now
    terms.save(update_fields=['status', 'published_by_email', 'published_at', 'updated_at'])
    return terms


# ── reads ────────────────────────────────────────────────────────────────────

def active_version():
    return (SponsorTermsVersion.objects
            .filter(status=SponsorTermsVersion.STATUS_ACTIVE)
            .prefetch_related('sections')
            .first())


def resolve_locale(terms, requested):
    """The locale we can serve WHOLE, falling back to English."""
    want = (requested or 'en').split('-')[0].lower()
    return want if want in terms.languages_available else 'en'


def _localised(obj, field, locale):
    return getattr(obj, f'{field}_{locale}') or getattr(obj, f'{field}_en')


def document(terms, locale='en'):
    """The whole document as plain data — one shape, used by the admin preview AND the
    sponsor-facing page, so the two can never drift apart."""
    loc = resolve_locale(terms, locale)
    return {
        'version': terms.version,
        'locale_used': loc,
        'title': _localised(terms, 'title', loc),
        'intro': _localised(terms, 'intro', loc),
        'sections': [
            {
                'order': s.order,
                'heading': _localised(s, 'heading', loc),
                'body': _localised(s, 'body', loc),
                'has_quiz': s.is_quiz_candidate,
            }
            for s in terms.sections.all()
        ],
    }


def quiz_checkpoints(terms, locale='en'):
    """The checkpoints in section order, each falling back to English INDIVIDUALLY — a section
    translated into Tamil is served in Tamil even if its neighbour is not."""
    loc = resolve_locale(terms, locale)
    out = []
    for s in terms.sections.all():
        if not s.is_quiz_candidate:
            continue
        payload = getattr(s, f'quiz_{loc}') or s.quiz_en
        if not quiz_payload_valid(payload):
            continue
        out.append({
            'order': s.order,
            'tag': payload.get('tag', ''),
            'plain': payload.get('plain', ''),
            'question': payload.get('question', ''),
            'options': payload.get('options', []),
            'correct': payload.get('correct'),
            'why': payload.get('why', ''),
        })
    return out


def acceptance_for(sponsor, terms):
    if sponsor is None or terms is None:
        return None
    return SponsorTermsAcceptance.objects.filter(sponsor=sponsor, terms=terms).first()


def acceptance_state(sponsor):
    """What the sponsor's own account payload reports, so the SCREEN never computes the rule.

    `needs_terms` is the whole gate: an active version exists and this sponsor has no row for it.
    Grandfathering is therefore data — a pre-written row — and not a branch in this function.
    """
    terms = active_version()
    if terms is None:
        return {'terms_version': '', 'terms_accepted': False, 'needs_terms': False,
                'terms_basis': ''}
    row = acceptance_for(sponsor, terms)
    return {
        'terms_version': terms.version,
        'terms_accepted': row is not None,
        'needs_terms': row is None,
        'terms_basis': row.basis if row else '',
    }


@transaction.atomic
def record_acceptance(sponsor, terms, *, signed_name, locale='en', ip_address=None):
    """A sponsor accepts by TYPING THEIR NAME — that is the signature, matching
    `BursaryAgreement.student_signed_name` and the credit chain's `*_signed_name` fields.

    ⚠ A name that differs from the account name is RECORDED, never refused. There is no IC to
    check against, "Ve. Elanjelian" and "Elanjelian Venugopal" are the same person, and refusing
    someone their own name on an acceptance screen is a worse failure than storing a difference an
    admin can see. `registered_name_at_acceptance` freezes the account name so the divergence is
    permanently visible.
    """
    typed = (signed_name or '').strip()
    if len(typed) < 3:
        raise SponsorTermsError('signature_required')

    now = timezone.now()
    row, created = SponsorTermsAcceptance.objects.get_or_create(
        sponsor=sponsor, terms=terms,
        defaults={
            'basis': SponsorTermsAcceptance.BASIS_ACCEPTED,
            'signed_name': typed,
            'registered_name_at_acceptance': sponsor.name or '',
            'accepted_at': now,
            'quiz_passed_at': now,
            'locale': locale or 'en',
            'ip_address': ip_address,
        },
    )
    return row, created


def grandfather(sponsor, terms, *, by_email='', reason=''):
    """Record that a sponsor was deliberately NOT asked. Never reports as an acceptance."""
    row, created = SponsorTermsAcceptance.objects.get_or_create(
        sponsor=sponsor, terms=terms,
        defaults={
            'basis': SponsorTermsAcceptance.BASIS_GRANDFATHERED,
            'granted_by_email': by_email or '',
            'reason': reason or '',
        },
    )
    return row, created
