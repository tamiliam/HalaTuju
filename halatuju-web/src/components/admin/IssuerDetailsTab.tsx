'use client'

/**
 * "Your details" — the first tab of PLATFORM → Billing, beside Rates.
 *
 * WHO IS BILLING: one row for the whole platform, printed at the top of every invoice and every
 * receipt. It lived on Billing & usage until 2026-10-28, grouped by the task you were doing
 * (issuing) rather than by the scope it has. Who is BILLED went the other way, to each
 * organisation's own settings.
 *
 * ⚠ **THE GROUPS ARE THE FIX, NOT DECORATION.** The owner filled the old flat form by typing an
 * address straight down it: the postcode landed in Phone and the city landed in Bank. Nine boxes
 * in one column read as one continuous thing. Each group now says where the address ENDS, and the
 * bank label says "Bank name" rather than the bare "Bank" that invited a city.
 *
 * ⚠ Blank is a real state and must stay cheap: HalaTuju has no registered entity, so the
 * registration number is optional and the invoice simply omits the line. `missing` comes from the
 * SERVER (`InvoiceIssuer.REQUIRED`) — this file never decides what is required, because the same
 * list is what refuses to issue an invoice.
 */
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import SaveBar, { SAVE_BAR_PRIMARY } from '@/components/admin/SaveBar'
import {
  getInvoiceIssuer, saveInvoiceIssuer, type InvoiceIssuerSettings,
} from '@/lib/admin-api'

/** The groups, in reading order. A group's fields are its own; the heading is what tells the eye
 *  that the previous subject has finished. `wide` spans both columns. */
const GROUPS: Array<{ key: string; fields: Array<{ key: string; wide?: boolean; multiline?: boolean }> }> = [
  { key: 'who', fields: [
    { key: 'legal_name', wide: true }, { key: 'registration_no' },
    { key: 'address', wide: true, multiline: true },
  ] },
  { key: 'reach', fields: [{ key: 'email' }, { key: 'phone' }] },
  { key: 'bank', fields: [
    { key: 'bank_name' }, { key: 'bank_account_name' }, { key: 'bank_account_no' },
  ] },
  { key: 'terms', fields: [{ key: 'payment_terms_days' }] },
]

const FIELDS = GROUPS.flatMap((g) => g.fields.map((f) => f.key))

type Draft = Record<string, string>

function draftFrom(issuer: InvoiceIssuerSettings): Draft {
  const src = issuer as unknown as Record<string, unknown>
  return Object.fromEntries(FIELDS.map((k) => [k, String(src[k] ?? '')]))
}

export default function IssuerDetailsTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [issuer, setIssuer] = useState<InvoiceIssuerSettings | null>(null)
  const [draft, setDraft] = useState<Draft>({})
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<'idle' | 'saved' | 'failed' | 'bad_email' | 'bad_terms'>('idle')
  const [loadError, setLoadError] = useState(false)

  // Depends on the token ONLY — never on `t`, whose handle can be a fresh function every render
  // and would wipe an edit in progress (the re-fired-fetch trap this console has been bitten by).
  const load = useCallback(async () => {
    if (!token) return
    setLoadError(false)
    try {
      const d = await getInvoiceIssuer({ token })
      setIssuer(d.issuer)
      setDraft(draftFrom(d.issuer))
    } catch {
      setLoadError(true)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const dirty = issuer !== null && FIELDS.some((k) => draft[k] !== draftFrom(issuer)[k])

  const save = useCallback(async () => {
    if (!token || !dirty) return
    setBusy(true)
    setOutcome('idle')
    try {
      // ⚠ A BLANK "days to pay" is left OUT, never sent as 0 — a zero would make every future
      // invoice due on the day it is issued, which reads as an aggressive term nobody chose.
      const body: Record<string, string | number> = {}
      for (const k of FIELDS) {
        if (k === 'payment_terms_days') continue
        body[k] = draft[k].trim()
      }
      const days = (draft.payment_terms_days || '').trim()
      if (days !== '') body.payment_terms_days = Number(days)
      const d = await saveInvoiceIssuer(body, { token })
      setIssuer(d.issuer)
      setDraft(draftFrom(d.issuer))
      setOutcome('saved')
    } catch (e) {
      const code = (e as { body?: { code?: string } }).body?.code
      setOutcome(code === 'bad_email' || code === 'bad_terms' ? code : 'failed')
    } finally {
      setBusy(false)
    }
  }, [token, dirty, draft])

  if (loadError) {
    return <p className="mt-6 text-sm text-critical-600" role="alert">{t('admin.issuer.loadFailed')}</p>
  }
  if (issuer === null) return <p className="mt-6 text-sm text-ground-500">{t('admin.issuer.loading')}</p>

  const status = outcome === 'idle' ? null
    : outcome === 'saved' ? t('admin.issuer.saved')
      : t(`admin.issuer.${outcome}`)

  return (
    <div className="mt-5" data-testid="issuer-tab">
      <p className="text-sm text-ground-600">{t('admin.issuer.sub')}</p>

      {issuer.missing.length > 0 && (
        /* Not an error — it is the state the platform ships in. It says what is missing and what
           that costs you (nothing can be issued), so the reader knows why it matters. */
        <p className="mt-3 rounded-lg bg-caution-50 px-3 py-2 text-xs text-caution-800"
          data-testid="issuer-missing">
          {t('admin.issuer.blocked', {
            fields: issuer.missing.map((k) => t(`admin.issuer.field.${k}`)).join(', '),
          })}
        </p>
      )}

      {GROUPS.map((g) => (
        <section key={g.key} className="mt-5" data-testid={`issuer-group-${g.key}`}>
          <h3 className="text-sm font-semibold text-ground-900">{t(`admin.issuer.group.${g.key}`)}</h3>
          <p className="mt-0.5 text-xs text-ground-500">{t(`admin.issuer.groupHint.${g.key}`)}</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {g.fields.map((f) => {
              const missing = issuer.missing.includes(f.key)
              const cls = 'mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm text-ground-900'
                + (missing ? ' border-critical-300' : '')
              return (
                <label key={f.key} className={`block ${f.wide ? 'sm:col-span-2' : ''}`}>
                  <span className="block text-[11px] text-ground-500">
                    {t(`admin.issuer.field.${f.key}`)}
                  </span>
                  {f.multiline ? (
                    <textarea className={`${cls} min-h-[4.5rem]`} value={draft[f.key] ?? ''}
                      onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))} />
                  ) : (
                    <input type="text" className={cls} value={draft[f.key] ?? ''}
                      inputMode={f.key === 'payment_terms_days' ? 'numeric' : undefined}
                      onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))} />
                  )}
                </label>
              )
            })}
          </div>
        </section>
      ))}

      <SaveBar status={status} testId="issuer-outcome">
        <button type="button" className={SAVE_BAR_PRIMARY} disabled={busy || !dirty}
          title={dirty ? undefined : t('common.nothingToSave')} onClick={() => { void save() }}>
          {t('admin.issuer.save')}
        </button>
      </SaveBar>
    </div>
  )
}
