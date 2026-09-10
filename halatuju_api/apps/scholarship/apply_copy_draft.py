"""Draft a gift's apply-page copy in Malay or Tamil, FROM ITS OWN ENGLISH.

⚠⚠ THIS DRAFTS. IT NEVER SAVES. The endpoint returns the drafted block and the browser puts it
in the boxes; the person reads it and presses Save themselves. That is the same rule the document
engines follow — *"Gemini extracts, deterministic matchers decide the verdict"* (`decisions.md`,
2026-05-31) — applied to copy: **the model proposes wording, a human publishes it.** Nothing here
may write to `Programme.apply_copy`. A gift's advertised criteria are read by applicants deciding
whether to apply; a machine must not be the last hand on them.

⚠ THE SOURCE IS THE GIFT'S OWN ENGLISH, NEVER THE PLATFORM DEFAULT. `apply_copy.for_wire` already
folds ms/ta onto the gift's English for a READER; drafting from the platform's B40 wording would
translate ANOTHER gift's criteria into this one's Malay — the exact "right-language falsehood"
`applyCopy.ts` was written to prevent. If the gift has no English, there is nothing to draft from
and this refuses.

⚠ THE BULLET COUNT MUST SURVIVE. Each bullet is a separate condition an applicant is judged
against; a translation that merges two or drops one changes the advertised bar in one language
only, and `normalise` would happily store it (the all-or-nothing rule is per LANGUAGE, not per
bullet). So the count is asserted, not hoped for.

⚠ TAMIL FOLLOWS THE PROJECT'S OWN STYLE GUIDE, and the rules below are a DELIBERATE SUBSET. The
full guide is 320 lines of grammar (three categories, ~85 rules); the ones repeated here are the
joining/sandhi rules a machine translation actually gets wrong on administrative prose. It is a
draft either way — the owner is the Tamil authority and reads every line before saving.
"""

import json
import logging
import re

from django.conf import settings

from . import apply_copy as ac

logger = logging.getLogger(__name__)

#: The languages this can draft INTO. English is the source and can never be a target.
TARGET_LOCALES = ('ms', 'ta')

_LANG_NAME = {'ms': 'Malay (Bahasa Melayu)', 'ta': 'Tamil'}


class DraftError(Exception):
    """A refusal the tab renders where the reader is looking. Mirrors `ApplyCopyError`."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _model():
    """Flash by owner decision (2026-09-10): a few hundred words per press, reviewed by a human
    before it reaches anybody, so the pro model's extra cost buys nothing here."""
    return getattr(settings, 'APPLY_COPY_DRAFT_MODEL', '') or 'gemini-2.5-flash'


def _gemini_generate(prompt, model):
    """The single mockable seam — patched in every test, so no CI run can make a live call.

    NO downgrade fallback, matching `sponsor_terms._gemini_generate` and the contract module's
    owner decision: an unconfigured or unavailable model raises rather than quietly producing
    something from a weaker one.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise DraftError('ai_unconfigured')
    try:
        from google import genai
    except ImportError:
        raise DraftError('ai_unavailable')
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    from . import usage   # billable — best-effort meter, same contract as every other seam
    _it, _ot = usage.gemini_tokens(response)
    usage.record_usage(usage.GEMINI, model=model, input_tokens=_it, output_tokens=_ot)
    return response.text


# ── The prompt ───────────────────────────────────────────────────────────────────────────────

#: ⚠ KEEP AS-IS, IN EVERY LANGUAGE. These are Malaysian qualification and programme names that a
#: reader recognises in Latin script; "translating" SPM into Tamil words helps nobody and makes the
#: criterion unrecognisable against the certificate the student is holding.
_KEEP_VERBATIM = (
    'SPM', 'STPM', 'PNGK', 'CGPA', 'IPTA', 'IPTS', 'ILKA', 'IPG', 'B40', 'M40', 'T20',
    'STR', 'MyKad', 'UPU', 'SijilPelajaranMalaysia', 'RM',
)

_TAMIL_RULES = """
Tamil style rules (from this project's own style guide — follow them):
- Join a noun with no case marker to its postposition (பற்றி, மீது, மூலம், கீழ், போல): இதுபற்றி.
  Keep them SEPARATE when the noun carries a case marker: ஆட்சியின் கீழ், இவற்றைப் பற்றி.
- Join a main verb to its auxiliary: பார்த்துக்கொண்டிருந்தான், not பார்த்து கொண்டிருந்தான்.
- Join an infinitive to இல்லை with வி: வர + இல்லை -> வரவில்லை.
- Join a verbal noun to இல்லை: பார்ப்பது + இல்லை -> பார்ப்பதில்லை.
- Keep a noun SEPARATE from இல்லாமல்: மழை இல்லாமல்.
- Write plain administrative Tamil. Do not reach for rare or heavily Sanskritised words where an
  ordinary one exists; this is read by a seventeen-year-old and their parents.
"""

_MALAY_RULES = """
Malay style rules:
- Write standard Bahasa Melayu as used in official Malaysian education notices.
- Use "anda" for the applicant, not "kamu" or "awak".
- Do not translate the qualification names listed above; keep them exactly as written.
"""


def build_prompt(block, locale):
    """The gift's English block -> a strict-JSON translation prompt. Pure; unit-tested directly."""
    rules = _TAMIL_RULES if locale == 'ta' else _MALAY_RULES
    bullets = block.get('criteria') or []
    payload = json.dumps(
        {'title': block.get('title', ''), 'intro': block.get('intro', ''), 'criteria': list(bullets)},
        ensure_ascii=False, indent=2)
    return f"""You are translating the public application page of a Malaysian education grant into
{_LANG_NAME[locale]}. A student reads this to decide whether they qualify and whether to apply.

Translate the JSON below. Return ONLY a JSON object with exactly these keys:
  "title"    - a string
  "intro"    - a string
  "criteria" - an array of EXACTLY {len(bullets)} strings, in the same order as the input

Hard requirements:
- Each criterion must stay a SEPARATE condition. Never merge two, never split one, never drop one,
  never add one. The array must have exactly {len(bullets)} entries.
- Do not soften or strengthen any requirement. A number, a grade or a threshold must carry over
  exactly. If the English says five A's, the translation says five A's.
- Keep these terms exactly as written, in Latin script: {', '.join(_KEEP_VERBATIM)}.
- Keep it about the same length as the English. "title" must be under {ac.MAX_TITLE} characters,
  "intro" under {ac.MAX_INTRO}, and each criterion under {ac.MAX_BULLET}.
- Plain, warm, factual. No marketing language, no exclamation marks.
- Never use the characters < or >.
{rules}
Input:
{payload}
"""


# ── Parsing the reply ────────────────────────────────────────────────────────────────────────

_FENCE = re.compile(r'^\s*```(?:json)?\s*|\s*```\s*$', re.IGNORECASE)


def parse_reply(text, expected_bullets):
    """A model reply -> a clean block. Raises `DraftError`. Pure; unit-tested directly.

    ⚠ THE COUNT CHECK IS LOAD-BEARING, not defensive tidiness — see the module docstring.
    """
    raw = _FENCE.sub('', (text or '').strip())
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise DraftError('bad_reply')
    if not isinstance(data, dict):
        raise DraftError('bad_reply')

    title = (data.get('title') or '').strip() if isinstance(data.get('title'), str) else ''
    intro = (data.get('intro') or '').strip() if isinstance(data.get('intro'), str) else ''
    rows = data.get('criteria')
    if not isinstance(rows, list):
        raise DraftError('bad_reply')
    bullets = [r.strip() for r in rows if isinstance(r, str) and r.strip()]

    if not title or not intro or not bullets:
        raise DraftError('bad_reply')
    if len(bullets) != expected_bullets:
        raise DraftError('bullet_count')
    # A drafted line the SAVE would refuse is worse than no draft: the reader would have to guess
    # which box is over. Refuse here with a code the tab can explain.
    if (len(title) > ac.MAX_TITLE or len(intro) > ac.MAX_INTRO
            or any(len(b) > ac.MAX_BULLET for b in bullets)):
        raise DraftError('draft_too_long')
    if any('<' in v or '>' in v for v in [title, intro] + bullets):
        raise DraftError('bad_reply')

    return {'title': title, 'intro': intro, 'criteria': bullets}


# ── The one public entry point ───────────────────────────────────────────────────────────────

def draft(programme, locale):
    """Draft this gift's `locale` block from its own English. Returns a block; never saves."""
    if locale not in TARGET_LOCALES:
        raise DraftError('bad_locale')
    stored = getattr(programme, 'apply_copy', None) or {}
    english = stored.get('en') or {}
    bullets = [b for b in (english.get('criteria') or []) if (b or '').strip()]
    if not english.get('title') or not english.get('intro') or not bullets:
        raise DraftError('english_required')

    prompt = build_prompt(english, locale)
    try:
        reply = _gemini_generate(prompt, _model())
    except DraftError:
        raise
    except Exception:                                   # noqa: BLE001 — one refusal for the reader
        logger.exception('apply-copy draft failed programme=%s locale=%s', programme.pk, locale)
        raise DraftError('ai_failed')
    return parse_reply(reply, len(bullets))
