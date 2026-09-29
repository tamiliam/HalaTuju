'use client'

/**
 * The two POST-AWARD tasks of the Action Centre — the bank-details card and the Vircle eWallet
 * card — moved here VERBATIM from ActionCentre.tsx (TD-306 follow-up, 2026-09-30).
 *
 * WHY THEY LIVE APART: only an AWARDED student ever holds a `bank_details_missing` or
 * `vircle_setup_pending` task, yet both cards (with the phone helpers and the Vircle account
 * rule they bring) rode in the first-load JS of `/scholarship/application` for every applicant.
 * The deploy gate refused 4583a83d on that route at 276 kB against a 275 kB budget, and the
 * budget is never raised. ActionCentre reaches this file only through
 * `scholarship/LazyPostAwardTask.tsx`, which owns the `import()`. Do not import it statically.
 */
import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { accountWarningKey, expectedAccountType, type VircleAccountType } from '@/lib/vircleAccount'
import {
  resolveResolutionItem,
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  confirmBankAccount,
  type ResolutionItem,
  type ApplicantDocument,
} from '@/lib/api'
import { countDigits } from '@/lib/actionCentre'
// The Vircle task captures a Malaysian mobile — reuse the shared, node-tested helpers rather
// than writing a second phone validator.
import { formatMyMobile, isValidMyMobile, localMobileDigits } from '@/lib/sponsorAuth'
import DocumentHelpCoach from '@/components/DocumentHelpCoach'

// ── Bank-details task (post-award payout account) ─────────────────────────
// A two-step card: (1) upload a bank statement → Gemini pre-fills the three fields;
// (2) the student reviews/corrects them and saves. The holder MUST be the student —
// the save re-checks server-side and refuses a mismatch (Gopal coaches). Account
// numbers are high-stakes, so the confirm step is deliberate.

export function BankDetailsTask({
  item, token, onResolved,
}: {
  item: ResolutionItem
  token: string | null
  onResolved: () => void
}) {
  const { t, locale } = useT()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploaded, setUploaded] = useState(false)
  const [coachDoc, setCoachDoc] = useState<ApplicantDocument | null>(null)
  const [bankName, setBankName] = useState('')
  const [accountNumber, setAccountNumber] = useState('')
  const [accountHolder, setAccountHolder] = useState('')

  // Upload the bank statement → pre-fill the three fields from the extraction.
  const onFile = async (file: File) => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument('bank_statement', { token })
      await uploadFileToSignedUrl(upload_url, file)
      const doc = await recordDocument(
        { doc_type: 'bank_statement', storage_path, original_filename: file.name, content_type: file.type, size: file.size },
        { token },
      )
      const f = (doc.vision_fields?.fields || {}) as Record<string, string>
      setBankName(f.bank_name || '')
      setAccountNumber(f.account_number || '')
      setAccountHolder(f.account_holder || '')
      setUploaded(true)
      // A weak read (holder isn't the student / a field unclear) → Gopal advises; the
      // student can still correct the fields below. 'pending'/'ok' → no coach.
      setCoachDoc(doc.match_verdict && doc.match_verdict !== 'ok' && doc.match_verdict !== 'pending' ? doc : null)
    } catch {
      setError(t('scholarship.actionCentre.uploadError'))
    } finally {
      setBusy(false)
    }
  }

  const onSave = async () => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await confirmBankAccount(
        { bank_name: bankName.trim(), account_number: accountNumber.trim(), account_holder: accountHolder.trim() },
        { token },
      )
      onResolved()   // task resolves server-side → the card clears on refresh
    } catch (e) {
      // DRF FIELD errors (400) carry no top-level code — map the account-number rule
      // specifically so the student learns WHICH field to fix instead of a generic
      // "couldn't save" dead-end (code-health S3 #9).
      const err = e as Error & { code?: string; fieldErrors?: Record<string, unknown> }
      const acctErrs = err.fieldErrors?.account_number
      const acctInvalid = Array.isArray(acctErrs)
        && acctErrs.some((m) => String(m).includes('account_number_invalid'))
      setError(err.code === 'bank_holder_mismatch'
        ? t('scholarship.actionCentre.bank.holderMismatch')
        : acctInvalid
          ? t('scholarship.actionCentre.bank.accountNumberInvalid')
          : t('scholarship.actionCentre.bank.saveError'))
    } finally {
      setBusy(false)
    }
  }

  // Mirror the API's account-number floor (≥5 digits) client-side so a truncated OCR
  // fragment is flagged inline before the save round-trip ever happens.
  const accountNumberTooShort = accountNumber.trim() !== '' && countDigits(accountNumber) < 5
  const canSave = !busy && bankName.trim() && accountNumber.trim() && accountHolder.trim()
    && !accountNumberTooShort

  return (
    <div className="rounded-2xl border border-ground-100 bg-ground-0 p-5 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-shape">
          <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 10l9-6 9 6M5 10v8a2 2 0 002 2h10a2 2 0 002-2v-8" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-ground-900">{t('scholarship.actionCentre.bank.title')}</h3>
            <span className="shrink-0 rounded-full bg-caution-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-caution-800">
              {t('scholarship.actionCentre.toDo')}
            </span>
          </div>
          <p className="mt-1 text-sm text-ground-500">{t('scholarship.actionCentre.bank.intro')}</p>

          <div className="mt-4 space-y-4">
            {/* Step 1: upload the statement */}
            <label className={`block w-full cursor-pointer rounded-xl bg-brand-fill px-4 py-2.5 text-center text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover ${busy ? 'opacity-50' : ''}`}>
              {busy && !uploaded ? t('scholarship.actionCentre.uploading')
                : uploaded ? t('scholarship.actionCentre.bank.reupload')
                : t('scholarship.actionCentre.bank.upload')}
              <input
                type="file" accept="image/*,.pdf" className="hidden" disabled={busy}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }}
              />
            </label>

            {coachDoc && <DocumentHelpCoach doc={coachDoc} token={token} t={t} lang={locale} coachLabelKey="scholarship.actionCentre.coachLabel" />}

            {/* Step 2: confirm/correct the three fields (shown after an upload) */}
            {uploaded && (
              <div className="space-y-3 rounded-xl bg-ground-50 p-4">
                <p className="text-xs font-medium text-ground-500">{t('scholarship.actionCentre.bank.checkPrompt')}</p>
                <div>
                  <label className="block text-sm font-medium text-ground-700">{t('scholarship.actionCentre.bank.bankName')}</label>
                  <input className="input mt-1" value={bankName} onChange={(e) => setBankName(e.target.value)} disabled={busy} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ground-700">{t('scholarship.actionCentre.bank.accountNumber')}</label>
                  <input className="input mt-1 font-mono" inputMode="numeric" value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} disabled={busy} />
                  {accountNumberTooShort
                    ? <p className="mt-1 text-xs text-critical-600">{t('scholarship.actionCentre.bank.accountNumberInvalid')}</p>
                    : <p className="mt-1 text-xs text-ground-500">{t('scholarship.actionCentre.bank.numberHint')}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-ground-700">{t('scholarship.actionCentre.bank.accountHolder')}</label>
                  <input className="input mt-1" value={accountHolder} onChange={(e) => setAccountHolder(e.target.value)} disabled={busy} />
                  <p className="mt-1 text-xs text-ground-500">{t('scholarship.actionCentre.bank.holderHint')}</p>
                </div>
                <button
                  type="button" onClick={onSave} disabled={!canSave}
                  className="w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50"
                >
                  {busy ? t('scholarship.actionCentre.bank.saving') : t('scholarship.actionCentre.bank.save')}
                </button>
              </div>
            )}

            {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Post-award Vircle eWallet setup: the student installs Vircle (per the emailed guide), then
 *  confirms here with the mobile number they registered. That confirmation is what we relay to
 *  Vircle to switch their account on.
 *
 *  Two things this card must get right:
 *  - The mobile is the ONLY join key between our record and their Vircle account, so it is
 *    pre-filled but editable, validated, and shown back before they commit.
 *  - The "stuck?" note repeats the two blockers that strand people mid-setup (a photo of a
 *    photocopy is rejected; a very old phone can fail activation). A stuck student is looking at
 *    THIS card, not hunting back through their inbox for the email.
 *
 *  V2a (2026-09-09): the wallet-ID box is GONE. The eWallet ID now arrives from Vircle's own
 *  Airtable callback after the confirm — typing it was the source of every wallet-id defect on
 *  record (DuitNow truncations, roll-over refusals). Do not add the box back. */
export function VircleTask({
  item, token, contactPhone, onResolved,
}: {
  item: ResolutionItem
  token: string | null
  contactPhone: string
  onResolved: () => void
}) {
  const { t } = useT()
  const [mobile, setMobile] = useState(() => formatMyMobile(contactPhone))
  // Account-type self-check (owner, 2026-09-09): defaults to what Vircle's birth-year rule
  // expects (served as `vircle_expected`); a disagreeing pick COACHES, it never blocks —
  // see lib/vircleAccount.ts for why.
  const expected = expectedAccountType(item.vircle_expected)
  const [accountType, setAccountType] = useState<VircleAccountType>(expected)
  const warnKey = accountWarningKey(accountType, expected)
  // Owner, 2026-09-10: a real student confirmed here without ever registering in Vircle
  // (Vircle: "could not find his IC"). The confirm now needs an explicit tick that the app
  // is installed AND the account registered — the button alone was doubling as the
  // declaration. Client-side gate only; the server stores the claim but never requires it.
  const [installed, setInstalled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const valid = isValidMyMobile(mobile)

  const onConfirmDone = async () => {
    if (!token || !valid || !installed || busy) return
    setBusy(true)
    setError(null)
    try {
      await resolveResolutionItem(item.id, `+60${localMobileDigits(mobile)}`, { token },
                                  undefined, undefined, accountType, true)
      onResolved()
    } catch {
      setError(t('scholarship.actionCentre.vircle.error'))
      setBusy(false)
    }
  }

  return (
    <div className="rounded-2xl border border-ground-200 bg-ground-0 p-4 shadow-sm">
      <div className="flex gap-3">
        <span aria-hidden className="text-xl">💳</span>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-ground-900">{t('scholarship.actionCentre.vircle.title')}</h3>
          <p className="mt-1 text-sm text-ground-600">{t('scholarship.actionCentre.vircle.intro')}</p>

          <div className="mt-3">
            <label className="block text-sm font-medium text-ground-700" htmlFor="vircle-mobile">
              {t('scholarship.actionCentre.vircle.mobile')}
            </label>
            <div className="mt-1 flex items-center gap-2">
              <span className="rounded-lg bg-ground-100 px-3 py-2 text-sm text-ground-600">+60</span>
              <input
                id="vircle-mobile"
                className="input flex-1"
                inputMode="tel"
                placeholder="12-345 6789"
                value={mobile}
                onChange={(e) => setMobile(formatMyMobile(e.target.value))}
                disabled={busy}
              />
            </div>
            <p className="mt-1 text-xs text-ground-500">{t('scholarship.actionCentre.vircle.mobileHint')}</p>
          </div>

          <div className="mt-3">
            <label className="block text-sm font-medium text-ground-700" htmlFor="vircle-account-type">
              {t('scholarship.actionCentre.vircle.accountType')}
            </label>
            <select
              id="vircle-account-type"
              className="input mt-1 w-full"
              value={accountType}
              onChange={(e) => setAccountType(e.target.value === 'child' ? 'child' : 'principal')}
              disabled={busy}
            >
              <option value="principal">{t('scholarship.actionCentre.vircle.accountPrincipal')}</option>
              <option value="child">{t('scholarship.actionCentre.vircle.accountChild')}</option>
            </select>
            {warnKey && (
              <p className="mt-2 rounded-lg border border-caution-100 bg-caution-50/40 px-3 py-2 text-sm text-ground-700">
                {t(warnKey)}
              </p>
            )}
          </div>

          <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-lg border border-ground-200 bg-ground-50 px-3 py-2">
            <input
              id="vircle-installed"
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 accent-brand-600"
              checked={installed}
              onChange={(e) => setInstalled(e.target.checked)}
              disabled={busy}
            />
            <span className="text-sm text-ground-700">
              {t('scholarship.actionCentre.vircle.installedDeclare')}
            </span>
          </label>

          <button
            type="button" onClick={onConfirmDone} disabled={!valid || !installed || busy}
            className="mt-3 w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50"
          >
            {busy ? t('scholarship.actionCentre.vircle.confirming') : t('scholarship.actionCentre.vircle.confirm')}
          </button>

          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium text-ground-700">
              {t('scholarship.actionCentre.vircle.stuckTitle')}
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ground-600">
              <li>{t('scholarship.actionCentre.vircle.stuckCard')}</li>
              <li>{t('scholarship.actionCentre.vircle.stuckPhone')}</li>
              <li>{t('scholarship.actionCentre.vircle.stuckSupport')}</li>
            </ul>
          </details>

          {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}
        </div>
      </div>
    </div>
  )
}
