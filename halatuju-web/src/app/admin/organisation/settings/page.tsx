'use client'

// Organisation → Settings — the tabbed shell for what an ORGANISATION decides about itself
// (owner, 2026-09-03: "each Org would have its own config/setting, and each programme would
// likewise have its own config/setting").
//
// TWO TABS since Org Config Sprint A (2026-09-07): Colours (the tenant's brand colour, Layer 1
// A2/A3) and Configuration (the organisation-wide tunable values — the "second organisation-level
// setting" the one-tab shell was waiting for). Understated text tabs on a full-width rule,
// matching the Programme screen exactly — the two are siblings one level apart and a reader
// should recognise the second from the first.
//
// ⚠ THE TABS ARE NOT A FENCE. Both endpoints are org-fenced on the caller's own
// `owning_organisation`; `mayView` below only avoids rendering a page that would 403.

import { useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import OrganisationColoursTab from '@/components/admin/OrganisationColoursTab'
import OrganisationConfigurationTab from '@/components/admin/OrganisationConfigurationTab'

const TABS = ['colours', 'configuration'] as const
type Tab = (typeof TABS)[number]

export default function AdminOrganisationSettingsPage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const [tab, setTab] = useState<Tab>('colours')
  const mayView = canAccess('/admin/organisation/settings', effectiveRole(role))

  if (!mayView) return null

  return (
    <div>
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.orgSettings.title')}</h1>
      <p className="mt-1 text-sm text-ground-600">{t('admin.orgSettings.subtitle')}</p>

      <div role="tablist" aria-label={t('admin.orgSettings.title')}
        className="mt-5 flex gap-6 border-b border-ground-200">
        {TABS.map((key) => (
          <button key={key} type="button" role="tab" id={`tab-${key}`}
            aria-selected={tab === key} aria-controls={`panel-${key}`}
            data-testid={`tab-${key}`} onClick={() => setTab(key)}
            className={`-mb-px border-b-2 pb-3 text-sm ${
              tab === key
                ? 'border-primary-600 font-semibold text-ground-900'
                : 'border-transparent font-medium text-ground-500 hover:text-ground-700'}`}>
            {t(`admin.orgSettings.tab.${key}`)}
          </button>
        ))}
      </div>

      {/* The inactive panel UNMOUNTS rather than hides — each tab re-fetches on mount, so a value
          saved on one visit is never shown stale on the next. */}
      {tab === 'colours' && (
        <div role="tabpanel" id="panel-colours" aria-labelledby="tab-colours">
          <OrganisationColoursTab />
        </div>
      )}
      {tab === 'configuration' && (
        <div role="tabpanel" id="panel-configuration" aria-labelledby="tab-configuration">
          <OrganisationConfigurationTab />
        </div>
      )}
    </div>
  )
}
