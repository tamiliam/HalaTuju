"""The single-model Gemini call, shared by the three features that make one.

**There are three Gemini shapes in this app and they are not interchangeable.** Tenancy rule 6
names the sanctioned seams and this module adds no fourth:

  * `vision._call_gemini_json` — structured JSON out of a document, walking a MODEL CASCADE and
    returning `{'_error': …}` rather than raising, because a document read must degrade into an
    officer's screen and never into a 500;
  * `profile_engine._call_gemini_text` — prose, same cascade, same error-as-a-value contract;
  * this — ONE model, NO fallback, and it RAISES. Owner decision 4 on the contract module: if the
    configured model is unconfigured or unavailable, say so; do not quietly produce something
    from a weaker model and present it as the answer. The three callers here draft copy a HUMAN
    then reads and publishes, so a silent downgrade is exactly the failure to avoid.

Neither of the first two could absorb this without changing what its own callers get back, so the
third shape keeps a home — but ONE home instead of three near-identical copies in
`apply_copy_draft`, `sponsor_terms` and `contracts`.

**The mockable seam does NOT move.** Each of those modules keeps a `_gemini_generate` of its own
name, three lines long, and every `patch('apps.scholarship.<module>._gemini_generate')` in the
suite goes on working untouched. That is deliberate and is what tenancy rule 6 asks for: the
per-feature seam is where the metering wrapper and the test double attach, and a shared core that
swallowed the seams would move the boundary the rule names.

**Metering is inside.** `usage.record_usage` runs on every successful call, best-effort, exactly
as it did in all three copies. A caller that bypassed this would be a billable call outside the
meter — the thing rule 6 exists to prevent.

**The cascade's failure string is built here too** (`cascade_failure`), for both cascade seams.
2026-10-24: Gemini's prepaid credit ran out (402) for ~20 hours; the error kept only the LAST
model's message — a retired model's 404 — so nobody could see the cause. Whether a stored error is
OUR outage or the document's problem is `read_errors`, which reads the prefix this writes.
"""
from django.conf import settings

from .read_errors import CASCADE_FAILED, DOCUMENT_FAILED

#: The stored cascade error stays readable on a cockpit row and in a log line.
_CASCADE_ERROR_MAX = 600


def cascade_failure(errors) -> str:
    """The one error string for a cascade in which EVERY model failed, naming each model and its
    own message — `errors` is `[(model, message), …]` in the order tried. The last message alone
    hid a 402 behind a retired model's 404 for a day (2026-10-24). Each message is cut to an even
    share so the whole stays under `_CASCADE_ERROR_MAX`; the prefix never changes, because
    `read_errors.is_ai_service_error` and the outage alert read it."""
    return _joined(CASCADE_FAILED, errors)


def document_failure(errors) -> str:
    """The error string when EVERY model looked at the document and none could use it — the same
    shape as `cascade_failure`, under `read_errors.DOCUMENT_FAILED`, which is NOT a service error."""
    return _joined(DOCUMENT_FAILED, errors)


def _joined(prefix, errors):
    head = f'{prefix}: '
    if not errors:
        return head + 'no model was tried'
    share = max(40, (_CASCADE_ERROR_MAX - len(head)) // len(errors) - 2)
    parts = []
    for model, msg in errors:
        one = ' '.join(str(msg or '').split())        # a provider error spans several lines
        label = f'{model}: '
        room = max(20, share - len(label))
        parts.append(label + (one if len(one) <= room else one[:room - 1] + '…'))
    return (head + '; '.join(parts))[:_CASCADE_ERROR_MAX]


def generate_text(prompt, model, *, images=None, exc, unconfigured, unavailable):
    """Run `prompt` through ONE Gemini model and return the response text.

    `exc` is the caller's own exception class and `unconfigured` / `unavailable` its own machine
    codes — they stay with the caller because a view maps them to copy a person reads, and a
    shared module has no business knowing that `contracts` says `quiz_ai_unconfigured` where
    `apply_copy_draft` says `ai_unconfigured`.

    `images` is an optional list of `(bytes, mime_type)` sent alongside the prompt. ⚠ The parts
    order is IMAGES FIRST, then the prompt, matching `vision._call_gemini_json` — the model
    attends better to instructions that follow the evidence. A call with no images takes the
    plain `contents=prompt` path, byte-identically to before, which a test pins.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise exc(unconfigured)
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise exc(unavailable)
    client = genai.Client(api_key=api_key)
    if images:
        contents = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]
        contents.append(prompt)
    else:
        contents = prompt
    response = client.models.generate_content(model=model, contents=contents)
    from . import usage   # billable Gemini call — best-effort meter, same contract as every seam
    _it, _ot = usage.gemini_tokens(response)
    usage.record_usage(usage.GEMINI, model=model, input_tokens=_it, output_tokens=_ot)
    return response.text
