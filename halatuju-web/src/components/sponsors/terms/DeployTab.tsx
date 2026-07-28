'use client'

import { btnPrimary } from '@/components/contracts/shared'
import type { SponsorTermsDetail, SponsorTermsValidation } from '@/lib/admin-api'

/**
 * Deploy — the publish checklist and the button.
 *
 * Every rule label comes from the SERVER, so this panel knows none of them: a rule can be added or
 * reworded without touching the client. Publish is super-only, and an org_admin is told who does it
 * rather than being shown a button that could only 403.
 */
export default function DeployTab({ terms, validation, isSuper, dirty, busy, onPublish, t }: {
  terms: SponsorTermsDetail
  validation: SponsorTermsValidation | null
  isSuper: boolean
  dirty: boolean
  busy: boolean
  onPublish: () => void
  t: (k: string, p?: Record<string, string>) => string
}) {
  const editable = terms.status === 'draft'

  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      <p className="text-sm text-gray-500">{t('admin.sponsors.terms.deployIntro')}</p>

      {!editable && (
        <p className="text-sm text-gray-600 rounded-lg bg-gray-50 border border-gray-200 px-3 py-2">
          {t('admin.sponsors.terms.readOnly', {
            status: t(`admin.sponsors.terms.status.${terms.status}`),
          })}
        </p>
      )}

      {terms.acceptance_count > 0 && (
        <p className="text-xs text-gray-500">
          {t('admin.sponsors.terms.acceptedBy', { n: String(terms.acceptance_count) })}
        </p>
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold">{t('admin.sponsors.terms.checklist')}</h3>
        {validation?.errors.map((e) => (
          <p key={e.code} className="text-xs text-red-600">✗ {e.label}</p>
        ))}
        {validation?.warnings.map((w) => (
          <p key={w.code} className="text-xs text-amber-700">! {w.label}</p>
        ))}
        {validation?.ok && validation.warnings.length === 0 && (
          <p className="text-xs text-green-700">✓ {t('admin.sponsors.terms.allClear')}</p>
        )}

        {editable && (
          isSuper ? (
            <button type="button" className={`${btnPrimary} mt-2 self-start`}
              disabled={busy || !validation?.ok || dirty} onClick={onPublish}>
              {t('admin.sponsors.terms.publish')}
            </button>
          ) : (
            <p className="text-xs text-gray-500 mt-2">{t('admin.sponsors.terms.superOnly')}</p>
          )
        )}
        {editable && dirty && (
          <p className="text-xs text-gray-500">{t('admin.sponsors.terms.saveFirst')}</p>
        )}
      </div>
    </div>
  )
}
