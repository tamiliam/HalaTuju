'use client'

// Programme settings — the TABBED shell (Layer 1 A2, 2026-09-01).
//
// The owner ruled on 2026-07-29 that Layer 0's "what a programme asks for" and Layer 1's colour
// picker are the same person doing two related jobs, so they share one route with two tabs rather
// than two menu entries. The roadmap warned that whichever shipped first would own the shell and
// the second would arrive as a retro-fit; Layer 0 Sprint 5 shipped a single-purpose page, so this
// is that retro-fit. The config tab moved to `components/admin/ProgrammeConfigTab` UNCHANGED.
//
// ⚠ THE TABS ARE NOT A FENCE. Both tabs read and write through endpoints that are themselves
// org-fenced. `mayView` below only avoids rendering a page that would 403 — the endpoints are the
// authority, and each fences on the caller's own `owning_organisation`.
//
// Each tab keeps its OWN draft and its own loader, and an unmounted tab loses its draft. That is
// deliberate: one shared draft across two unrelated saves is how a person ends up pressing Save on
// a screen and changing something they cannot see.

import { useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import ProgrammeConfigTab from '@/components/admin/ProgrammeConfigTab'
import ProgrammeColoursTab from '@/components/admin/ProgrammeColoursTab'

const TABS = ['config', 'colours'] as const
type Tab = (typeof TABS)[number]

export default function AdminProgrammePage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/programme', effectiveRole(role))
  const [tab, setTab] = useState<Tab>('config')

  if (!mayView) return null

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.programme.title')}</h1>
      <p className="mt-1 text-sm text-ground-600">{t('admin.programme.subtitle')}</p>

      {/* Understated text tabs on a full-width rule — the console's own restraint. A pill or a
          boxed tab would compete with the brand actions inside each tab. */}
      <div role="tablist" aria-label={t('admin.programme.title')}
        className="mt-5 flex gap-6 border-b border-ground-200">
        {TABS.map((key) => (
          <button key={key} type="button" role="tab" id={`tab-${key}`}
            aria-selected={tab === key} aria-controls={`panel-${key}`}
            data-testid={`tab-${key}`}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 pb-3 text-sm transition-colors ${
              tab === key
                ? 'border-primary-600 font-semibold text-ground-900'
                : 'border-transparent text-ground-500 hover:text-ground-800'}`}>
            {t(`admin.programme.tab.${key}`)}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'config' ? <ProgrammeConfigTab /> : <ProgrammeColoursTab />}
      </div>
    </div>
  )
}
