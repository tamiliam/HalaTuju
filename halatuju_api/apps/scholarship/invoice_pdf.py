"""Invoice and receipt PDFs (2026-09-14).

Rendered from the FROZEN invoice row — its snapshots and lines — and never from the live charge,
the live issuer or the live billing details. Re-downloading January's invoice in June must give
January's document, byte for byte in content.

Same engine as the signed bursary agreement (`bursary.generate_pdf`): xhtml2pdf, pure Python,
no system libraries, so it builds on the Cloud Run buildpack. Helvetica is a PDF base font, so
nothing needs embedding and figures line up in their columns.
"""
import io
from decimal import Decimal
from html import escape

from .invoicing import InvoicingError, month_label

_METHOD_WORDS = {'bank_transfer': 'Bank transfer', 'cheque': 'Cheque', 'other': 'Other'}


def rm(value):
    """RM1,552.50 — thousands grouped, always two places."""
    return f'RM{Decimal(value):,.2f}'


def _date(d):
    return f'{d.day} {month_label(f"{d.year}-{d.month:02d}")}'


def _lines(text):
    return '<br/>'.join(escape(x) for x in (text or '').splitlines() if x.strip())


_CSS = """
@page { size: a4 portrait; margin: 18mm 16mm 18mm 16mm; }
body { font-family: Helvetica; font-size: 9.5pt; color: #1d2330; }
h1 { font-size: 20pt; margin: 0; color: #1d2330; }
.muted { color: #5b6475; }
.small { font-size: 8pt; }
.label { font-size: 8pt; color: #5b6475; }
td { vertical-align: top; }
.head td { font-size: 8pt; color: #5b6475; border-bottom: 1px solid #1d2330; padding: 4px 4px; }
.row td { padding: 6px 4px; border-bottom: 0.5px solid #d5d9e0; }
.num { text-align: right; }
.totals td { padding: 3px 4px; }
.grand td { font-size: 11pt; font-weight: bold; border-top: 1px solid #1d2330; padding-top: 6px; }
.void { color: #b42318; font-size: 16pt; font-weight: bold; }
.box { border: 0.5px solid #d5d9e0; padding: 8px; }
"""


def _header(title, number, who, meta_rows):
    reg = f'<br/><span class="small muted">Registration {escape(who["registration_no"])}</span>' \
        if who.get('registration_no') else ''
    meta = ''.join(
        f'<tr><td class="label">{escape(k)}</td><td class="num">{v}</td></tr>' for k, v in meta_rows)
    return f"""
<table width="100%"><tr>
  <td width="55%">
    <b style="font-size:12pt">{escape(who.get('legal_name', ''))}</b>{reg}<br/>
    <span class="muted">{_lines(who.get('address', ''))}</span><br/>
    <span class="muted">{escape(who.get('email', ''))}
    {(' &middot; ' + escape(who['phone'])) if who.get('phone') else ''}</span>
  </td>
  <td width="45%" class="num">
    <h1>{escape(title)}</h1>
    <div style="font-size:11pt; margin-bottom:6px">{escape(number)}</div>
    <table width="100%">{meta}</table>
  </td>
</tr></table>
"""


def render_invoice_html(invoice):
    who = invoice.issuer_snapshot or {}
    to = invoice.bill_to_snapshot or {}
    status = invoice.status
    meta = [('Issued', _date(invoice.issued_on)), ('Due', _date(invoice.due_on)),
            ('For', escape(month_label(invoice.period_month)))]

    rows = []
    for ln in invoice.lines.all():
        qty = f'{ln.quantity}' if ln.quantity is not None else ''
        unit = rm(ln.unit_amount_myr) if ln.unit_amount_myr is not None else ''
        rows.append(
            f'<tr class="row"><td width="58%">{escape(ln.description)}</td>'
            f'<td width="10%" class="num">{qty}</td><td width="14%" class="num">{unit}</td>'
            f'<td width="18%" class="num">{rm(ln.amount_myr)}</td></tr>')

    totals = [f'<tr><td class="num muted">Subtotal</td><td class="num" width="22%">'
              f'{rm(invoice.subtotal_myr)}</td></tr>']
    if invoice.discount_myr and Decimal(invoice.discount_myr) > 0:
        reason = (f'<br/><span class="small muted">{escape(invoice.discount_reason)}</span>'
                  if invoice.discount_reason else '')
        totals.append(
            f'<tr><td class="num muted">Discount ({Decimal(invoice.discount_pct).normalize():f}%)'
            f'{reason}</td><td class="num">-{rm(invoice.discount_myr)}</td></tr>')
    totals.append(f'<tr class="grand"><td class="num">Total due</td>'
                  f'<td class="num">{rm(invoice.total_myr)}</td></tr>')
    paid = invoice.amount_paid()
    if paid > 0:
        totals.append(f'<tr><td class="num muted">Paid</td><td class="num">-{rm(paid)}</td></tr>')
        totals.append(f'<tr><td class="num"><b>Balance</b></td>'
                      f'<td class="num"><b>{rm(invoice.balance())}</b></td></tr>')

    void_banner = ''
    if status == 'void':
        void_banner = (f'<p class="void">VOID</p><p class="muted">'
                       f'{escape(invoice.void_reason)}</p>')

    return f"""<html><head><meta charset="utf-8"/><style>{_CSS}</style></head><body>
{_header('Invoice', invoice.number, who, meta)}
{void_banner}
<table width="100%" style="margin-top:14px"><tr>
  <td width="55%"><div class="label">Bill to</div>
    <b>{escape(to.get('bill_to_name', ''))}</b><br/>
    <span class="muted">{_lines(to.get('address', ''))}</span></td>
  <td width="45%"></td>
</tr></table>

<table width="100%" style="margin-top:16px">
  <tr class="head"><td width="58%">Description</td><td width="10%" class="num">Hours</td>
      <td width="14%" class="num">Rate</td><td width="18%" class="num">Amount</td></tr>
  {''.join(rows)}
</table>

<table width="100%" class="totals" style="margin-top:8px"><tr><td width="40%"></td><td width="60%">
  <table width="100%">{''.join(totals)}</table>
</td></tr></table>

<table width="100%" style="margin-top:22px"><tr><td class="box">
  <span class="label">How to pay</span><br/>
  Bank transfer to <b>{escape(who.get('bank_account_name', ''))}</b>,
  {escape(who.get('bank_name', ''))}, account <b>{escape(who.get('bank_account_no', ''))}</b>.<br/>
  Please quote <b>{escape(invoice.number)}</b> as the payment reference.
  Amounts are in Malaysian ringgit.
</td></tr></table>
</body></html>"""


def render_receipt_html(receipt):
    invoice = receipt.invoice
    who = invoice.issuer_snapshot or {}
    to = invoice.bill_to_snapshot or {}
    meta = [('Received', _date(receipt.received_on)), ('Invoice', escape(invoice.number))]
    return f"""<html><head><meta charset="utf-8"/><style>{_CSS}</style></head><body>
{_header('Receipt', receipt.number, who, meta)}
<table width="100%" style="margin-top:14px"><tr>
  <td width="55%"><div class="label">Received from</div>
    <b>{escape(to.get('bill_to_name', ''))}</b><br/>
    <span class="muted">{_lines(to.get('address', ''))}</span></td>
  <td width="45%"></td>
</tr></table>

<table width="100%" style="margin-top:16px">
  <tr class="head"><td width="70%">Payment</td><td width="30%" class="num">Amount</td></tr>
  <tr class="row"><td width="70%">For invoice {escape(invoice.number)} ({escape(month_label(invoice.period_month))})<br/>
      <span class="small muted">{escape(_METHOD_WORDS.get(receipt.method, receipt.method))},
      reference {escape(receipt.reference)}</span></td>
      <td width="30%" class="num">{rm(receipt.amount_myr)}</td></tr>
</table>

<table width="100%" class="totals" style="margin-top:8px"><tr><td width="40%"></td><td width="60%"><table width="100%">
  <tr class="grand"><td class="num">Amount received</td>
      <td class="num" width="30%">{rm(receipt.amount_myr)}</td></tr>
  <tr><td class="num muted">Invoice balance after this payment</td>
      <td class="num">{rm(_balance_after(receipt))}</td></tr>
</table></td></tr></table>

<p class="muted" style="margin-top:22px">Thank you. This receipt confirms the payment above
was received.</p>
</body></html>"""


def _balance_after(receipt):
    """The balance straight after THIS receipt — not today's balance, which a later receipt moves.
    A receipt re-downloaded next year must still say what it said the day it was issued."""
    invoice = receipt.invoice
    earlier = sum((r.amount_myr for r in invoice.receipts.all()
                   if (r.received_on, r.id) <= (receipt.received_on, receipt.id)), Decimal('0.00'))
    return (Decimal(invoice.total_myr) - earlier).quantize(Decimal('0.01'))


def to_pdf(html):
    """HTML → PDF bytes. A mockable seam, like `bursary.generate_pdf`."""
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        result = pisa.CreatePDF(io.StringIO(html), dest=buf)
        if result.err:
            raise InvoicingError('pdf_failed', 'The PDF could not be produced.')
        return buf.getvalue()
    except InvoicingError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InvoicingError('pdf_failed', f'The PDF could not be produced: {exc}')


def invoice_pdf(invoice):
    return to_pdf(render_invoice_html(invoice))


def receipt_pdf(receipt):
    return to_pdf(render_receipt_html(receipt))
