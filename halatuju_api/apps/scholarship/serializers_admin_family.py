"""The student's "About your family" answers and the parent-contact name check, as the cockpit
is told them (request #45, 2026-10-25).

Two things the officer's Family & finances card needs and the detail payload did not carry:

* ``income_declared`` / ``income_nonearning`` — the student's own answers: the average monthly
  wage declared for a working member with no payslip, and, for a member who is not working, why
  and since when. The roster (father/mother/other members + occupations) and who earns
  (``income_route`` / ``income_earner`` / ``income_working_members``) were already served.
* ``guardian_ic_name_match`` — the ids of the LIVE parent/guardian ICs whose read name MATCHES
  the parent contact's name (``guardians[0].name``). The cockpit's tick beside that name used to
  mean only "some parent IC was read"; on application 171 the IC on file was the father's while
  the contact name was the mother's, and the tick still showed. The match is computed HERE, with
  ``vision.name_match`` — the same matcher the ``parent_ic_name_mismatch`` anomaly uses for the
  same comparison (case, spacing and the A/L, A/P, bin, binti markers tolerated) — so the
  browser never grows its own copy of the name rules.

⚠ APPENDED IN ``to_representation``, NOT DECLARED AS FIELDS, for the reason
``serializers_admin_gift`` gives: ``serializers_admin.py`` is at its size allowance, and every
existing key keeps its value and position. The match reads the ALREADY-SERIALISED ``guardians``
and ``documents`` (the same rows the cockpit is sent), so it costs no query.

⚠ NO NEW AUDIENCE. This payload is role-invariant by owner decision (``test_admin_detail_payload``):
anyone the page gate lets open the cockpit already sees the household income, the roster and the
documents these values come from. Nothing here reaches a sponsor or finance serializer.
"""
from .vision import name_match


def _plain_dict(value):
    """A JSON object, or ``{}`` for anything else (a legacy row may hold a non-dict)."""
    return value if isinstance(value, dict) else {}


def guardian_ic_name_match(guardians, documents):
    """The ids of the live, legibly-read ``parent_ic`` documents whose read name is a full
    ``name_match`` for the first guardian's (the parent contact's) name. ``[]`` when there is no
    contact name, no such document, or no match — a partial or a mismatch never qualifies."""
    first = (guardians or [None])[0] if isinstance(guardians, list) else None
    contact = ((first or {}).get('name') or '').strip() if isinstance(first, dict) else ''
    if not contact:
        return []
    out = []
    for doc in documents or []:
        if not isinstance(doc, dict) or doc.get('doc_type') != 'parent_ic' or doc.get('superseded_at'):
            continue
        read = (doc.get('vision_name') or '').strip()
        if not read or not doc.get('vision_run_at') or doc.get('vision_error'):
            continue
        if name_match(read, contact) == 'match':
            out.append(doc.get('id'))
    return out


class ServesTheFamilyAnswers:
    """Adds ``income_declared``, ``income_nonearning`` and ``guardian_ic_name_match`` to the
    officer's detail payload, after every named field and just before the gift's ``programme``
    (``ServesTheGift`` sits outside this mixin, so ``programme`` stays the last key —
    ``test_gift_context`` pins both the extra keys and that order)."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['income_declared'] = _plain_dict(getattr(instance, 'income_declared', None))
        data['income_nonearning'] = _plain_dict(getattr(instance, 'income_nonearning', None))
        data['guardian_ic_name_match'] = guardian_ic_name_match(
            data.get('guardians'), data.get('documents'))
        return data
