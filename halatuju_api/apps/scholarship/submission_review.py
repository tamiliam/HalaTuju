"""
Check 2 — STEP 1: the deterministic submission-review FACTS LEDGER.

When a student submits (``profile_completed_at`` set), this turns the raw application
into an auditable picture the rest of Check 2 builds on, in three parts (design
``docs/scholarship/check2-design.md`` §3):

1. **Facts ledger** — every claim a sponsor profile might make, each tagged with HOW
   WELL it is backed by the deterministic layer (the four-fact verification verdict +
   structured fields + read documents). The profile generator (§6) gates its
   assertions on this ledger so it never states an unverified claim as fact (the bug
   behind the live output asserting "first-generation" while it was only a flag).
2. **Completeness gaps** — fundable-profile fields we don't yet have (device, transport
   cost, chosen course, sibling level, motivation). These become STEP-2 clarify-queries.
3. **Consistency flags** — contradictions/ambiguities, reused from the deterministic
   anomaly engine (narrative vs structured data vs documents).

**No LLM here.** "Verified/accurate is NOT the LLM's call" (design §3) — verification is
the deterministic layer's, so this whole module is pure rules: safe to call inside a
serializer GET, fully testable, no cost. An LLM consistency *enrichment* (reading the
letter of intent for subtler contradictions) is a later, guarded addition.

Verification taxonomy for a ledger row:
  - ``verified``       — backed by a verified verification-verdict fact (assert as fact).
  - ``reported``       — a self-reported structured field or a fact still under review
                         (assert as "the student reports …", not as confirmed truth).
  - ``student_words``  — narrative the student wrote (aspirations, motivation): assert
                         in their voice, never as an independent fact.
  - ``unverified``     — no backing, contradicted, or a verdict gap: omit or hedge, never
                         state as fact.
"""
from __future__ import annotations

from .anomaly_engine import sibling_tertiary_count, detect_anomalies
from .verdict_engine import build_verdict

# A verification-verdict status → the ledger verification it implies.
_VERDICT_TO_VERIFICATION = {
    'verified': 'verified',
    'review': 'reported',
    'recommend': 'reported',
    'gap': 'unverified',
}

_VALUE_MAX = 280  # narrative values are truncated in the ledger (the full text lives on the app)


def _verdict_map(application) -> dict:
    """``{fact_name: status}`` for the four verification facts."""
    return {f['fact']: f['status'] for f in build_verdict(application)}


def _ver_from_verdict(status: str) -> str:
    return _VERDICT_TO_VERIFICATION.get(status, 'unverified')


def _clip(value) -> str:
    s = '' if value is None else str(value).strip()
    return (s[:_VALUE_MAX] + '…') if len(s) > _VALUE_MAX else s


def _row(claim, value, source, verification):
    return {'claim': claim, 'value': _clip(value),
            'source': source, 'verification': verification}


def _letter_of_intent_text(application) -> str:
    """The OCR'd plain text of the letter of intent (P1), or '' if not uploaded/read."""
    doc = (application.documents.filter(doc_type='statement_of_intent', superseded_at__isnull=True)
           .order_by('-uploaded_at').first())
    if doc is None or not isinstance(getattr(doc, 'vision_fields', None), dict):
        return ''
    return (doc.vision_fields.get('text') or '').strip()


def build_facts_ledger(application) -> list[dict]:
    """Every assertable claim + its verification status. A row is emitted ONLY when the
    claim has a value (so the generator sees exactly the set it may draw on)."""
    profile = getattr(application, 'profile', None)
    verdicts = _verdict_map(application)
    rows = []

    def add(claim, value, source, verification):
        # Emit a row when the claim has a value. 0 / False are valid values (e.g.
        # household_income 0, siblings_in_school 0); only None and blank strings skip.
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        rows.append(_row(claim, value, source, verification))

    # Identity / academic / pathway / income — anchored on the verification verdict.
    add('name', getattr(profile, 'name', ''), 'identity_verdict',
        _ver_from_verdict(verdicts.get('identity', 'gap')))
    add('qualification', getattr(profile, 'exam_type', ''), 'academic_verdict',
        _ver_from_verdict(verdicts.get('academic', 'gap')))
    add('pathway', _pathway_value(application), 'pathway_verdict',
        _ver_from_verdict(verdicts.get('pathway', 'gap')))
    add('household_income', getattr(profile, 'household_income', None), 'income_verdict',
        _ver_from_verdict(verdicts.get('income', 'gap')))

    # Self-reported structured fields — true to attribute, not independently verified.
    add('school', getattr(profile, 'school', ''), 'reported', 'reported')
    add('household_size', getattr(profile, 'household_size', None), 'reported', 'reported')
    add('parents_occupation', application.parents_occupation, 'reported', 'reported')
    if application.siblings_in_school is not None:
        add('siblings_in_school', application.siblings_in_school, 'reported', 'reported')
    if application.siblings_in_tertiary is not None:
        add('siblings_in_tertiary', application.siblings_in_tertiary, 'reported', 'reported')

    # first-to-university — only an assertable claim when the student made it; its
    # verification comes from the P2 sibling split, not a self-tick.
    if application.first_in_family:
        tertiary = sibling_tertiary_count(application)
        ver = 'verified' if tertiary == 0 else 'unverified'  # None or >0 → can't assert
        add('first_in_family', True, 'sibling_split', ver)

    # The student's own words — assert in their voice, never as fact.
    add('motivation', application.aspirations or _letter_of_intent_text(application),
        'student_words', 'student_words')
    add('plans', application.plans, 'student_words', 'student_words')
    add('family_context', application.family_context, 'student_words', 'student_words')
    add('daily_life', application.daily_life, 'student_words', 'student_words')

    return rows


def _pathway_value(application) -> str:
    bits = []
    if application.field_of_study:
        bits.append(str(application.field_of_study))
    pc = application.pathways_considered
    if isinstance(pc, list) and pc:
        bits.append(', '.join(str(x) for x in pc))
    return '; '.join(bits)


def completeness_gaps(application) -> list[dict]:
    """Fundable-profile fields we don't yet have → STEP-2 clarify-query candidates.
    Each: ``{code}`` (the frontend resolves copy). Grounded in real fields only —
    device & transport have no structured field, so they're standing gaps."""
    gaps = []
    profile = getattr(application, 'profile', None)
    verdicts = _verdict_map(application)

    # Chosen course — needed for the Pathway plan section.
    if not _pathway_value(application) and verdicts.get('pathway') == 'gap':
        gaps.append({'code': 'course_unspecified'})

    # Motivation — the heart of the case; the form's aspirations OR the letter of intent.
    if not (application.aspirations or '').strip() and not _letter_of_intent_text(application):
        gaps.append({'code': 'motivation_missing'})

    # Sibling level — unknown when the split can't be derived (legacy count, no breakdown).
    if sibling_tertiary_count(application) is None and application.siblings_in_tertiary is None:
        gaps.append({'code': 'sibling_level_unknown'})

    # Device — no structured field. If they didn't tick 'device' under funding we don't
    # know whether they have one to study on.
    fn = getattr(application, 'funding_need', None)
    cats = fn.categories if (fn and isinstance(fn.categories, list)) else []
    if 'device' not in cats:
        gaps.append({'code': 'device_status_unknown'})

    # Transport cost — only STPM students travel daily at a real, distance-dependent
    # cost worth asking. Residential pathways (matrik/asasi/poly/PISMP) have transport
    # estimated as small, so we don't ask them; an unknown pathway also doesn't ask.
    from .funding_estimate import classify_pathway
    if classify_pathway(application) == 'stpm':
        gaps.append({'code': 'transport_cost_unknown'})

    return gaps


def consistency_flags(application) -> list[dict]:
    """Contradictions / ambiguities for the reviewer — the deterministic anomaly engine
    IS the narrative-vs-data consistency layer (design §3, check 3). Each: ``{code, params}``."""
    return detect_anomalies(application)


def submission_review(application) -> dict:
    """STEP 1 aggregate: the facts ledger + completeness gaps + consistency flags.
    Pure + deterministic — safe inside a serializer GET."""
    return {
        'ledger': build_facts_ledger(application),
        'completeness': completeness_gaps(application),
        'consistency': consistency_flags(application),
    }
