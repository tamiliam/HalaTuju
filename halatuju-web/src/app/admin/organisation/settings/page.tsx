'use client'

// Organisation → Settings — the tabbed shell for what an ORGANISATION decides about itself
// (owner, 2026-09-03: "each Org would have its own config/setting, and each programme would
// likewise have its own config/setting").
//
// ⚠ ONE TAB TODAY, AND THAT IS NOT AN OVERSIGHT. Colours moved here from the Programme screen,
// where it had never belonged: `OrganisationTheme` is one colour for the whole tenant and its
// endpoint derives the organisation, so setting it while standing inside a gift would silently
// have changed every other gift too. A single-tab shell reads oddly for exactly as long as it
// takes the second organisation-level setting to arrive, and the alternative — a page called
// "Colours" — would have to be re-cut when it does. The Programme screen made the same call for
// the same reason (Layer 1 A2) and it held.
//
// ⚠ THE TABS ARE NOT A FENCE. The colour endpoint is org-fenced on the caller's own
// `owning_organisation`; `mayView` below only avoids rendering a page that would 403.

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import OrganisationColoursTab from '@/components/admin/OrganisationColoursTab'

export default function AdminOrganisationSettingsPage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/organisation/settings', effectiveRole(role))

  if (!mayView) return null

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.orgSettings.title')}</h1>
      <p className="mt-1 text-sm text-ground-600">{t('admin.orgSettings.subtitle')}</p>

      {/* Understated text tabs on a full-width rule, matching the Programme screen exactly — the
          two are siblings one level apart and a reader should recognise the second from the first. */}
      <div role="tablist" aria-label={t('admin.orgSettings.title')}
        className="mt-5 flex gap-6 border-b border-ground-200">
        <button type="button" role="tab" id="tab-colours" aria-selected
          aria-controls="panel-colours" data-testid="tab-colours"
          className="-mb-px border-b-2 border-primary-600 pb-3 text-sm font-semibold text-ground-900">
          {t('admin.orgSettings.tab.colours')}
        </button>
      </div>

      <div role="tabpanel" id="panel-colours" aria-labelledby="tab-colours">
        <OrganisationColoursTab />
      </div>
    </div>
  )
}
