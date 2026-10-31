"""The optional fourth language on a staff profile (common profile S2, owner 2026-10-31).

One slot beside English / BM / Tamil — Mandarin, Kadazandusun, Bajau… for students from Sabah — stored
by NAME (`ReviewerProfile.other_language`, at most 60) with its fluency (`other_language_fluency`).
Both or neither: a name with no fluency, or a fluency with no name, is refused. It never counts for the
onboarding hold (`reviewer_onboarding.LANG_FIELDS` stays English / BM / Tamil), and it is served by
name BESIDE the en/ms/ta codes, never inside them (`ReviewerProfile.spoken_other_language`).
"""
from rest_framework import serializers


def checked_other_language(attrs, instance=None):
    """`attrs` with the name trimmed, or a 400 `other_language_incomplete`. Judged over the row as it
    would be saved, so a PATCH that sends one half against a stored other half is judged whole."""
    if 'other_language' in attrs:
        attrs['other_language'] = (attrs['other_language'] or '').strip()

    def value(key):
        return attrs.get(key, getattr(instance, key, '') if instance is not None else '')
    if bool(value('other_language')) != bool(value('other_language_fluency')):
        raise serializers.ValidationError({'other_language': 'other_language_incomplete'})
    return attrs
