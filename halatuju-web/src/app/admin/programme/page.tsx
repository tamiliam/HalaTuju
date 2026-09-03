'use client'

// Programme → Configuration — everything a person SETS about one gift, on one screen.
//
// THREE TABS, IN THE OWNER'S ORDER (2026-09-03): Rules · What we ask for · Intake year.
//
// ⚠ FOUR MENU ROWS WERE DELETED TO BUILD THIS, and the reasoning matters more than the layout.
// The console had grown a Programme group of six rows, four of them reserved slots that each
// guessed at the shape of unscoped work. Following one rule — what is a subset of what — settled
// every one of them:
//   · RULES are the six thresholds stored on the intake year, which the create form already
//     wrote. A Rules page would have been a second view of an existing form, so it is tab one —
//     and it comes FIRST because who qualifies precedes what they are asked to send.
//   · INTAKE YEAR is a child of the gift, not a sibling of its settings. The owner's own model:
//     "the intake year is merely a column within the application table, and not a superset."
//   · REVIEWER SCOPING is one field on a reviewer's record, under Organisation → Reviewers.
//   · FUND is a report, not a setting.
// `/admin/programme/years` redirects here; the registry matches it so the bookmark lights this row.
//
// ⚠ COLOURS LEFT. `OrganisationTheme` is one colour for the whole tenant and its endpoint derives
// the organisation, so a tenant-wide setting was being changed from inside a single gift — silent
// while there is one gift, wrong the day there are two. It is Organisation → Settings now.
//
// ⚠ WHICH GIFT COMES FROM THE BREADCRUMB, and it is a display preference passed explicitly, never
// an ambient scope — see `lib/programmeScope`. With several gifts and no choice made, each tab
// ASKS rather than picking one (PF-1's refuse-don't-guess rule, applied to a screen).
//
// ⚠ THE TABS ARE NOT A FENCE. Every tab reads and writes through org-fenced endpoints; `mayView`
// below only avoids rendering a page that would 403.
//
// Each tab keeps its OWN draft and its own loader, and an unmounted tab loses its draft. That is
// deliberate: one shared draft across two unrelated saves is how a person ends up pressing Save on
// a screen and changing something they cannot see.

import { useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { useProgrammeScope } from '@/lib/programmeScope'
import ProgrammeRulesTab from '@/components/admin/ProgrammeRulesTab'
import ProgrammeConfigTab from '@/components/admin/ProgrammeConfigTab'
import IntakeYearTab from '@/components/admin/IntakeYearTab'

const TABS = ['rules', 'config', 'year'] as const
type Tab = (typeof TABS)[number]

export default function AdminProgrammePage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/programme', effectiveRole(role))
  const [tab, setTab] = useState<Tab>('rules')
  const { programme } = useProgrammeScope()

  if (!mayView) return null

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.programme.title')}</h1>
      <p className="mt-1 text-sm text-ground-600">
        {programme ? `${programme.name} — ` : ''}{t('admin.programme.subtitle')}
      </p>

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
        {tab === 'rules' ? <ProgrammeRulesTab />
          : tab === 'config' ? <ProgrammeConfigTab />
            : <IntakeYearTab />}
      </div>
    </div>
  )
}
