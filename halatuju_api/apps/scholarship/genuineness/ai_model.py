"""Which Gemini model the four genuineness checks ask, and the checked 3.8 call (OCR-16).

The four checks (IC fingerprint `ic.ic_genuineness`, the results slip's QR + crest read
`results_doc.results_visual_markers`, the holistic supporting-document read
`supporting_doc.doc_genuineness`, the SAMPLE-stamp read `sample_stamp._ask_model`) all ask
Gemini through `ask` here, behind ONE setting:

  * `GENUINENESS_MODEL` — a Django setting when one is set, else the env var of that name (read on
    every call, kept out of `settings/base.py`, which is in the frozen oversize-file ledger — the
    `offer_reader.retry_model` precedent). EMPTY (the default) keeps today's call exactly: the 2.5
    Flash cascade (`profile_engine.FLASH_25_CASCADE`), one call, no retry.
  * set to a 3.8 Flash name (the slip read's allow-list, `slip_read.is_slip_model`) → that ONE
    model, every answer CHECKED against the schema (each required key present with its JSON type,
    a verdict one of the known words), one retry on a malformed answer or a document refusal
    (DOCUMENT_FAILED), no retry on a service error (our side). Still malformed after the retry → a
    DOCUMENT_FAILED error, which every caller already turns into "no signal" (never a penalty).
  * any other value (a 2.5 name, a typo, a Lite variant) is refused with a warning and the checks
    stay on the 2.5 cascade — never an unvetted model on a document verdict.

The paid eval (`manage.py eval_genuineness_38`) forces the 3.8 path per call with `model=`.
"""
import logging
import os

from ..gemini import cascade_failure, document_failure
from ..read_errors import DOCUMENT_FAILED

logger = logging.getLogger(__name__)

SETTING = 'GENUINENESS_MODEL'
#: How many times a 3.8 genuineness question is asked in all: the first ask and at most one retry.
MAX_CALLS = 2
#: The reason stored with a 3.8 answer that failed the check (the retry's too).
MALFORMED = 'MALFORMED_GENUINENESS_ANSWER'

_JSON_TYPES = {'boolean': bool, 'string': str}


def chosen_model() -> str:
    """The 3.8 Flash model the checks ask, or '' for today's 2.5 cascade (the default)."""
    from django.conf import settings
    from ..vision.slip_read import is_slip_model
    model = (str(getattr(settings, SETTING, '') or '').strip()
             or os.environ.get(SETTING, '').strip())
    if not model:
        return ''
    if is_slip_model(model):
        return model
    logger.warning('%s=%s refused (only a 3.8 Flash name may read genuineness); using 2.5 Flash',
                   SETTING, model)
    return ''


def genuineness_models() -> list:
    """The models the four checks use right now — read live, so the AI registry shows the truth."""
    from ..profile_engine import FLASH_25_CASCADE
    model = chosen_model()
    return [model] if model else list(FLASH_25_CASCADE)


def answer_problems(answer, schema, verdicts=None) -> list:
    """What is wrong with one parsed answer (empty for a good one): not an object, a required key
    missing or of the wrong JSON type, or a `verdict` that is not one of `verdicts`."""
    if not isinstance(answer, dict):
        return ['not_an_object']
    problems = []
    props = schema.get('properties', {})
    for key in schema.get('required', []):
        want = _JSON_TYPES.get(props.get(key, {}).get('type'))
        if key not in answer:
            problems.append('missing:' + key)
        elif want is not None and not isinstance(answer[key], want):
            problems.append('type:' + key)
    if verdicts is not None and isinstance(answer.get('verdict'), str):
        if answer['verdict'].strip().lower() not in verdicts:
            problems.append('verdict')
    return problems


def _with_enum(schema, verdicts):
    """The 3.8 schema: the same keys, every one still required, the verdict a closed enum."""
    if not verdicts:
        return schema
    props = dict(schema['properties'])
    props['verdict'] = {'type': 'string', 'enum': sorted(verdicts)}
    return {**schema, 'properties': props}


def ask(prompt, schema, *, image, mime_type, model=None, verdicts=None) -> dict:
    """Ask one genuineness question → the parsed answer, or ``{'_error': ...}``. `model=None` reads
    `GENUINENESS_MODEL`; the eval passes a 3.8 name to force that path. `verdicts` is the set of
    verdict words the caller maps (lowercase); None when the answer has no verdict."""
    from apps.scholarship import vision   # lazy: the callers' patch seam stays vision._call_gemini_json
    from ..profile_engine import FLASH_25_CASCADE
    from ..vision.slip_read import is_slip_model
    model = chosen_model() if model is None else model
    if not model:                                           # today's call, byte for byte
        return vision._call_gemini_json(prompt, schema, image=image, mime_type=mime_type,
                                        models=FLASH_25_CASCADE)
    if not is_slip_model(model):                            # a forced model must be 3.8 Flash too
        return {'_error': cascade_failure([(str(model), 'refused: not a 3.8 Flash model')])}
    schema38 = _with_enum(schema, verdicts)
    problems = []
    for _ in range(MAX_CALLS):
        answer = vision._call_gemini_json(prompt, schema38, image=image, mime_type=mime_type,
                                          models=[model])
        err = answer.get('_error') if isinstance(answer, dict) else None
        if err:
            if not str(err).startswith(DOCUMENT_FAILED):    # our side: not retried here
                return answer
            problems = ['document_failed']
            continue
        problems = answer_problems(answer, schema, verdicts)
        if not problems:
            return answer
    return {'_error': document_failure([(model, f"{MALFORMED}: {', '.join(problems)}")])}
