"""TD-157 — the officer sees what a Singapore payslip converts to in ringgit, and the rate.

A Malaysian working in Singapore submits an S$ payslip, and the means-test converts it to ringgit
(`income_engine.amounts._to_myr`, at `sgd_to_myr_rate()`, owner 2026-07-05) — so the household can
read OVER the line while the document still shows the S$ figure. Until now the cockpit never said
so: the officer had to connect a higher income to the "Singapore payslip" genuineness note alone.

``sgd_conversion(doc)`` takes the slip's monthly figure the way the engine does
(`_salary_monthly_amount`) and hands it to the engine's OWN conversion, `amounts._to_myr` — one
home for the Singapore test and the in-review gate (review F3). When the engine declines to convert
(a ringgit slip, or a decided case, which keeps its as-recorded basis — owner: "leave out #75") it
returns the amount unchanged, and there is no note.

⚠ WHAT THE NOTE MEANS: "this slip converts to RM Y at this rate" — NOT "this slip was the figure the
means-test counted". The engine counts only the FIRST slip with an amount per earner
(`earner_monthly_income`); a second Singapore slip for the same earner carries the note too. Showing
it only on the counted slip would need the earner's slip list per document (review F3, declined to
keep the payload query-free); the officer reads the income figure itself on the income panel.

Served ONLY on the officer's document payload (`AdminApplicantDocumentSerializer` below, used by
`serializers_admin.AdminApplicationDetailSerializer.documents`); the student's payload is unchanged.
It lives here, not in `serializers.py` (at its size ceiling) or `serializers_admin.py` (one line of
allowance left). No query: it reads the document's own stored fields, and the application the
document's related manager already attached to it (the same one `income_proof_check` reads).
"""
from rest_framework import serializers

from .serializers import ApplicantDocumentSerializer


def _two_places(x: float) -> str:
    return f'{x:,.2f}'


def sgd_conversion(doc):
    """``{'sgd': 'S$ figure', 'rate': '3.15', 'myr': 'RM figure'}`` (formatted strings, no currency
    symbol) when the income engine converts this salary slip from Singapore dollars; else None."""
    if getattr(doc, 'doc_type', '') != 'salary_slip':
        return None
    from .income_engine import amounts
    from .income_engine.salary_figures import _doc_fields, _salary_monthly_amount
    f = _doc_fields(doc)
    amt = _salary_monthly_amount(f)
    if not amt:
        return None
    myr = amounts._to_myr(amt, f, doc.application)
    if myr is None or myr == amt:
        return None          # the engine did not convert it: a ringgit slip, or a decided case
    return {'sgd': _two_places(amt), 'rate': f'{amounts.sgd_to_myr_rate():g}', 'myr': _two_places(myr)}


class AdminApplicantDocumentSerializer(ApplicantDocumentSerializer):
    """The officer's document payload: every field the student's has, plus ``sgd_conversion``."""
    sgd_conversion = serializers.SerializerMethodField()

    class Meta(ApplicantDocumentSerializer.Meta):
        fields = ApplicantDocumentSerializer.Meta.fields + ['sgd_conversion']

    def get_sgd_conversion(self, obj):
        return sgd_conversion(obj)
