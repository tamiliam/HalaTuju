'use client'

/**
 * "Billing" — the third tab of ORGANISATION → Settings, beside Colours and Configuration.
 *
 * WHERE THIS ORGANISATION'S INVOICES GO: the name printed under "Bill to", the address beneath it,
 * and the inboxes Send delivers to. It moved here from Billing & usage on 2026-10-28 because its
 * scope is the organisation, and the organisation is who knows it.
 *
 * ⚠ **THE TENANT MAY EDIT THIS, AND THAT IS THE ONE INVOICE SETTING IT MAY TOUCH** (owner ruling).
 * Not what it is billed FOR (build hours, super-only), not what it is billed AT (rates,
 * super-only) — only where its own bill is addressed. Safe because the debt is recorded against
 * the organisation id, an issued invoice carries a FROZEN copy of these values, and a super reads
 * the printed name at Send. The server enforces all of that; this file only draws it.
 *
 * Organisation resolution copies the two sibling tabs exactly: ask with no code, and if the server
 * answers `organisation_required` show its list. A reader of this page should recognise the third
 * tab from the first two.
 */
import { useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import SaveBar, { SAVE_BAR_PRIMARY } from '@/components/admin/SaveBar'
import { splitEmails } from '@/lib/invoices'
import {
  getOrgBillingDetails, saveOrgBillingDetails, type TenantBillingDetails,
} from '@/lib/admin-api'

type Draft = { bill_to_name: string; address: string; emails: string }

function draftFrom(d: TenantBillingDetails): Draft {
  return { bill_to_name: d.bill_to_name, address: d.address, emails: d.emails.join(', ') }
}

export default function OrganisationBillingTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [details, setDetails] = useState<TenantBillingDetails | null>(null)
  const [draft, setDraft] = useState<Draft>({ bill_to_name: '', address: '', emails: '' })
  const [orgChoices, setOrgChoices] = useState<string[] | null>(null)
  // ⚠ `?organisation=<code>` is how Billing & usage sends a super straight here when it says
  // "BrightPath's billing details are incomplete". Without this the link would land on a "which
  // organisation?" picker that re-asks a question the card already answered.
  const fromLink = useSearchParams()?.get('organisation') || undefined
  const [org, setOrg] = useState<string | undefined>(fromLink)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<'idle' | 'saved' | 'failed' | 'bad_email'>('idle')
  const [loadError, setLoadError] = useState(false)

  // Token and chosen organisation ONLY — never `t`, which can be a new handle each render and
  // would wipe an edit in progress.
  const load = useCallback(async (code?: string) => {
    if (!token) return
    setLoadError(false)
    try {
      const d = await getOrgBillingDetails(code, { token })
      setDetails(d)
      setDraft(draftFrom(d))
      setOrgChoices(null)
    } catch (e) {
      const err = e as Error & { body?: { code?: string; organisations?: string[] } }
      if (err.body?.code === 'organisation_required' && Array.isArray(err.body.organisations)) {
        setOrgChoices(err.body.organisations)
      } else {
        setLoadError(true)
      }
    }
  }, [token])

  useEffect(() => { void load(org) }, [load, org])

  const dirty = details !== null && (['bill_to_name', 'address', 'emails'] as const)
    .some((k) => draft[k] !== draftFrom(details)[k])

  const save = useCallback(async () => {
    if (!token || !details || !dirty) return
    setBusy(true)
    setOutcome('idle')
    try {
      const d = await saveOrgBillingDetails({
        // The code the READ resolved, so a save can never land on a different organisation than
        // the one on screen.
        organisation: details.organisation_code,
        bill_to_name: draft.bill_to_name.trim(),
        address: draft.address.trim(),
        // Split here so "a@x.com; b@x.com" is one box for the reader and a list on the wire.
        emails: splitEmails(draft.emails),
      }, { token })
      setDetails(d)
      setDraft(draftFrom(d))
      setOutcome('saved')
    } catch (e) {
      const code = (e as { body?: { code?: string } }).body?.code
      setOutcome(code === 'bad_email' ? 'bad_email' : 'failed')
    } finally {
      setBusy(false)
    }
  }, [token, details, dirty, draft])

  if (orgChoices) {
    return (
      <div className="mt-5" data-testid="billing-org-picker">
        <p className="text-sm text-ground-600">{t('admin.orgBilling.pickOrganisation')}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {orgChoices.map((code) => (
            <button key={code} type="button" onClick={() => setOrg(code)}
              className="rounded-lg border bg-ground-0 px-3 py-1.5 text-sm text-ground-700 hover:bg-ground-50">
              {code}
            </button>
          ))}
        </div>
      </div>
    )
  }
  if (loadError) {
    return <p className="mt-6 text-sm text-critical-600" role="alert">{t('admin.orgBilling.loadFailed')}</p>
  }
  if (details === null) {
    return <p className="mt-6 text-sm text-ground-500">{t('admin.orgBilling.loading')}</p>
  }

  const status = outcome === 'idle' ? null
    : outcome === 'saved' ? t('admin.orgBilling.saved')
      : t(`admin.orgBilling.${outcome}`)

  const box = (k: keyof Draft) => 'mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm'
    + ' text-ground-900' + (details.missing.includes(k) ? ' border-critical-300' : '')

  return (
    <div className="mt-5" data-testid="org-billing-tab">
      <p className="text-sm text-ground-600">{t('admin.orgBilling.sub')}</p>
      {/* The one sentence that stops this reading as "edit your past invoices". */}
      <p className="mt-3 rounded-lg bg-info-50 px-3 py-2 text-xs text-info-800">
        {t('admin.orgBilling.nextInvoiceOnly')}
      </p>

      <div className="mt-4 grid max-w-xl gap-3">
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.orgBilling.field.bill_to_name')}</span>
          <input type="text" className={box('bill_to_name')} value={draft.bill_to_name}
            onChange={(e) => setDraft((d) => ({ ...d, bill_to_name: e.target.value }))} />
        </label>
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.orgBilling.field.address')}</span>
          <textarea className={`${box('address')} min-h-[4.5rem]`} value={draft.address}
            onChange={(e) => setDraft((d) => ({ ...d, address: e.target.value }))} />
        </label>
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.orgBilling.field.emails')}</span>
          <input type="text" className={box('emails')} value={draft.emails}
            onChange={(e) => setDraft((d) => ({ ...d, emails: e.target.value }))} />
          <span className="mt-1 block text-[11px] text-ground-400">{t('admin.orgBilling.emailsHint')}</span>
        </label>
      </div>

      <SaveBar status={status} testId="org-billing-outcome">
        <button type="button" className={SAVE_BAR_PRIMARY} disabled={busy || !dirty}
          title={dirty ? undefined : t('common.nothingToSave')} onClick={() => { void save() }}>
          {t('admin.orgBilling.save')}
        </button>
      </SaveBar>
    </div>
  )
}
