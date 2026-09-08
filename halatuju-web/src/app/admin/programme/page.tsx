'use client'

// Programme → Configuration — everything a person SETS about one gift, on one screen.
//
// THREE TABS, IN THE OWNER'S ORDER (2026-09-06): Intake year · Rules · What we ask for.
//
// ⚠⚠ THE ORDER WAS REVERSED ON 2026-09-06, AND THE 2026-09-03 REASONING IS KEPT BECAUSE IT WAS
// NOT WRONG. It read: *"Rules… comes FIRST because who qualifies precedes what they are asked to
// send."* That is true of READING a gift already running, and it stays true. It is not true of
// SETTING ONE UP, and setting one up is what this screen is reached by:
//
//   **The rules ARE COLUMNS ON THE INTAKE YEAR.** A gift created a minute ago has no year, so the
//   Rules tab has nothing to write to and renders `admin.rules.noYear`. Opening a brand-new gift
//   on Rules therefore landed a person on the one screen that could not work yet — the owner's
//   words, 2026-09-06: *"we do not want a disconnected flow."*
//
// Setup order must follow DATA order. The year exists first because everything else is stored on
// it or judged against it.
//
// ⚠ FOUR MENU ROWS WERE DELETED TO BUILD THIS, and the reasoning matters more than the layout.
// The console had grown a Programme group of six rows, four of them reserved slots that each
// guessed at the shape of unscoped work. Following one rule — what is a subset of what — settled
// every one of them:
//   · RULES are the six thresholds stored on the intake year, which the create form already
//     wrote. A Rules page would have been a second view of an existing form, so it is a tab here.
//   · INTAKE YEAR is a child of the gift, not a sibling of its settings. The owner's own model:
//     "the intake year is merely a column within the application table, and not a superset."
//     Being a child is why it is tab ONE: a child that must exist before its siblings can work.
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

import { useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { useProgrammeScope } from '@/lib/programmeScope'
import ProgrammeRulesTab from '@/components/admin/ProgrammeRulesTab'
import ProgrammeConfigTab from '@/components/admin/ProgrammeConfigTab'
import IntakeYearTab from '@/components/admin/IntakeYearTab'

const TABS = ['year', 'rules', 'config'] as const
type Tab = (typeof TABS)[number]

const isTab = (v: string): v is Tab => (TABS as readonly string[]).includes(v)

export default function AdminProgrammePage() {
  const { role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/programme', effectiveRole(role))
  const [tab, setTab] = useState<Tab>('year')
  const { programme } = useProgrammeScope()

  // ⚠ `?tab=` IS READ FROM `window.location`, NOT `useSearchParams`, AND THAT IS DELIBERATE.
  // This is a PAGE file, and Next's own typing plus static generation is a contract the other
  // gates do not enforce — `useSearchParams` in a page requires a Suspense boundary or `next
  // build` refuses, which is precisely the trap F7c hit three times (docs/lessons.md: "when a
  // framework owns a file's shape, the type-checker you run by hand does not know about it").
  // A tab is a display preference, not routing: reading it once on mount is the whole need.
  useEffect(() => {
    const want = new URLSearchParams(window.location.search).get('tab') ?? ''
    if (isTab(want)) setTab(want)
  }, [])

  if (!mayView) return null

  return (
    <div>
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

      {/* ⚠ A TAB MAY POINT AT THE NEXT ONE; IT MAY NEVER DO THE NEXT ONE FOR YOU. PF-1's rule on a
          screen: `ProgrammeRulesTab` with no year offers a button to the Intake year tab rather
          than creating a year for you. Suggesting is help; choosing is a guess about somebody's
          money.

          ⚠ THE POINTER ONLY EXISTS IN THAT ONE DIRECTION NOW (owner, 2026-09-07). The Intake year
          tab used to carry a matching "Next: set the rules" button, but its condition was
          "a year exists" — so it never went away, and on a gift running its second intake it read
          as unfinished work. A pointer is for a DEAD END, not for a step somebody has passed. */}
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'year' ? <IntakeYearTab />
          : tab === 'rules' ? <ProgrammeRulesTab goToYear={() => setTab('year')} />
            : <ProgrammeConfigTab />}
      </div>
    </div>
  )
}
