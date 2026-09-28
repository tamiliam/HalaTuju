"""WHICH GIFT a record belongs to, as the admin console is told it (2026-09-28).

The console's breadcrumb names the gift you are in. On a LIST page that is a choice the person
made; on a DETAIL page — one payment run, one application — it is a FACT about the record, and
the page has to tell the crumb which gift it is showing or the crumb lies (owner, 2026-09-28:
*"since we access the payment run by first selecting the gift programme, that question
shouldn't even arise"*). This module is the one place that fact is spelled for the client.

⚠ THE GIFT IS `application.programme` — NEVER `chosen_programme`. `chosen_programme` is the
student's COURSE (a JSON blob about a diploma or a degree); `programme` is the GIFT that funds
them, a set-once FK denormalised at first save. The two words are one letter apart in English
and nothing in between, which is exactly why the field is named here and nowhere else.

⚠ DISPLAY ONLY. This is not a fence and adding it makes none. Every record that carries it has
already passed the organisation fence (`_org_allows` / the org-fenced run lookup); the client
uses the code to label the breadcrumb and nothing else.

⚠ IT LIVES IN ITS OWN MODULE BECAUSE `serializers_admin.py` IS AT ITS SIZE ALLOWANCE (TD-283).
The serializer gains one base class and not one line.
"""


def gift_ref(programme):
    """``{id, code, name}`` for a gift, or ``None`` when there is none.

    ``None`` is a real answer, not an error: a payment run made before P2b has no programme, and
    an application's `programme` is nullable. The client treats ``None`` as "this record does
    not say", which leaves the breadcrumb exactly where it was — never a guess.
    """
    if programme is None:
        return None
    return {'id': programme.id, 'code': programme.code, 'name': (programme.name_en or '').strip()}


class ServesTheGift:
    """Adds ``programme: {id, code, name} | None`` to a serializer's output, LAST.

    ⚠ APPENDED IN `to_representation`, NOT DECLARED AS A FIELD. A declared field would have to be
    added to the host serializer's `Meta.fields`, which is a line in a file that may not grow; and
    appending after `super()` guarantees every existing key keeps its value and its position — the
    payload is the old one plus one key, byte for byte.

    ⚠ IT COSTS A QUERY UNLESS THE CALLER JOINED THE GIFT. The first cut assumed the detail build
    already read `application.programme`; it does not (it reads `programme_id`), and
    `test_query_budgets.py` caught the lazy FK read at 38 -> 39. `_AdminBase._get_application`
    therefore `select_related`s it, which is the lookup every admin detail endpoint goes through.
    A caller that builds this serializer from some other queryset pays one query, and is correct.
    """

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['programme'] = gift_ref(getattr(instance, 'programme', None))
        return data
