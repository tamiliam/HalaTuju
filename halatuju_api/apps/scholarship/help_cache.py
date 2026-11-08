"""A2.4 / SP-06 - the "Cikgu Gopal" coach answers a repeat GET from the cache, with no model call.

Both coach GETs (a document's help, an earner's income-cluster help) built the same prompt and
called Gemini on every open: p95 14 to 21 s for a message that had not changed. The prompt IS the
complete input of the call (persona, programme, document, verdict, first name, language, the
non-sensitive household specifics), so its hash is the key.

What is cached: ONLY a message the model actually wrote (`source == 'ai'`). A fallback, an error or
`none` is never stored, so a throttled or failed call is retried on the next open.

Personal data: the key carries the application id AND the prompt hash, so one student's message can
never be served to another. Nothing but the engine's own reply is stored, and it expires after
`TTL_SECONDS`. Uses the existing Django cache backend (the database cache in production).
"""
import hashlib

from django.core.cache import cache

TTL_SECONDS = 6 * 3600


def cache_key(application_id, prompt):
    digest = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    return f'help_coach_msg:{application_id}:{digest}'


def cached_help(application_id, doc_type, verdict, *, first_name='', target_language,
                context=None, branding=None):
    """`help_engine.generate_document_help` with a cache in front. Same arguments (plus the
    application id that scopes the key), same reply."""
    from . import help_engine
    verdict_clean = (verdict or '').strip()
    if verdict_clean not in help_engine.VERDICT_GUIDANCE:
        return help_engine.generate_document_help(doc_type, verdict, first_name=first_name,
                                                  target_language=target_language, context=context,
                                                  branding=branding)
    prompt = help_engine._build_help_prompt(doc_type, verdict_clean, first_name, target_language,
                                            context, branding)
    key = cache_key(application_id, prompt)
    hit = cache.get(key)
    if hit is not None:
        return dict(hit)
    result = help_engine.generate_document_help(doc_type, verdict, first_name=first_name,
                                                target_language=target_language, context=context,
                                                branding=branding)
    if result.get('source') == 'ai' and result.get('message'):
        cache.set(key, dict(result), TTL_SECONDS)
    return result
