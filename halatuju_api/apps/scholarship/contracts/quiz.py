"""Contract module: the comprehension-quiz prompt and its checks. The Gemini seam
(``_gemini_generate``) and ``generate_quiz`` stay in the package ``__init__``.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
import json
import re

from .errors import ContractsError
from .numbering import LANGUAGES


def _clause_and_descendants(clause):
    """A clause plus its descendant sub-clauses: the following clauses whose level is DEEPER,
    up to (but not including) the next clause at the same-or-shallower level. Lets a top-level
    clause's comprehension quiz cover its entire subtree (sub- and sub-sub-clauses included)."""
    ordered = list(clause.template.clauses.order_by('order'))
    result = []
    collecting = False
    for c in ordered:
        if c.pk == clause.pk:
            collecting = True
            result.append(c)
        elif collecting:
            if c.level > clause.level:
                result.append(c)
            else:
                break
    return result or [clause]


def _build_quiz_prompt(clause):
    """Strict-JSON prompt asking for a comprehension checkpoint in en/ms/ta, built from the whole
    clause SUBTREE (the clause + its sub-clauses) so the checkpoint covers the clause's key points,
    using each language's translations when present, else English."""
    subtree = _clause_and_descendants(clause)

    def block(lang):
        parts = []
        for c in subtree:
            heading = getattr(c, f'heading_{lang}') or c.heading_en
            body = getattr(c, f'body_{lang}') or c.body_en
            seg = f'{heading}\n{body}'.strip()
            if seg:
                parts.append(seg)
        return f'[{lang}]\n' + '\n\n'.join(parts)

    clause_text = '\n\n'.join(block(lang) for lang in LANGUAGES)
    return (
        'You write a plain-language comprehension checkpoint for one clause of a '
        'student bursary agreement. Return STRICT JSON only, no prose, shaped as '
        '{"en": CHECKPOINT, "ms": CHECKPOINT, "ta": CHECKPOINT} where each '
        'CHECKPOINT is {"tag": str, "plain": str, "question": str, '
        '"options": [str, str, str], "correct": 0|1|2, "why": str}. Exactly one '
        'option is correct (its index is "correct"); the same index must be '
        'correct in all three languages. Keep it warm and simple; never invent '
        'terms the clause does not contain.\n\nCLAUSE:\n' + clause_text
    )


def _parse_quiz_json(raw):
    text = (raw or '').strip()
    # Tolerate a ```json fence around the payload.
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text).strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise ContractsError('quiz_bad_json')
    if not isinstance(data, dict):
        raise ContractsError('quiz_bad_json')
    return data


def _quiz_payload_valid(payload):
    """Structural check (the Q2 shape): 3 options, a correct index in 0..2."""
    if not isinstance(payload, dict):
        return False
    options = payload.get('options')
    if not isinstance(options, list) or len(options) != 3:
        return False
    if not all(isinstance(o, str) and o.strip() for o in options):
        return False
    return payload.get('correct') in (0, 1, 2)
