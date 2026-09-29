/**
 * A console shell in miniature for "which gift am I in" tests (2026-09-28).
 *
 * Mounts the REAL `ProgrammeScopeProvider` and the REAL breadcrumb (`BreadcrumbScopes`, on a
 * Programme-scope page) around a page, plus a probe that prints what the scope resolved. That is
 * the whole chain the owner sees — page → scope → crumb — without the shell's fetches, so a test
 * can mount a page with NO prior choice (a fresh tab, a bookmark) and read what the crumb says.
 *
 * `@/lib/i18n` must be mocked by the caller (the house pattern: `t` echoes its key).
 */
import type { ReactNode } from 'react'
import { screen } from '@testing-library/react'

import { BreadcrumbScopes } from '@/components/admin/ScopeSwitcher'
import { ProgrammeScopeProvider, useProgrammeScope, type ProgrammeChoice } from '@/lib/programmeScope'

/** The defect's shape — one organisation, two ACTIVE gifts, nothing chosen. The CODES are the
 *  live ones from the report; the names are neutral, because `brand-guard.test.ts` keeps the
 *  tenant's brand out of every non-test source file, and this helper is one. */
export const TWO_GIFTS: readonly ProgrammeChoice[] = [
  { code: 'brightpath-flagship', name: 'Flagship Bursary', isActive: true },
  { code: 'bpb-sabah-2026', name: 'Sabah Bursary 2026', isActive: true },
]

function Probe() {
  const { chosen, pinned } = useProgrammeScope()
  return (
    <div>
      <span data-testid="scope-chosen">{chosen || '(none)'}</span>
      <span data-testid="scope-pinned">{String(pinned)}</span>
    </div>
  )
}

/** The provider + crumb + probe, around `children`. Re-render it with other children to
 *  unmount the page while KEEPING the scope's state — which is what navigating away does. */
export function GiftScope({ choices = TWO_GIFTS, settled = true, children }: {
  choices?: readonly ProgrammeChoice[]
  /** False = the shell's scopes fetch has not come back yet. */
  settled?: boolean
  children?: ReactNode
}) {
  return (
    <ProgrammeScopeProvider choices={choices} settled={settled}>
      <nav data-testid="crumb">
        {/* The page's path from jsdom's address bar, as the shell passes `usePathname()`. */}
        <BreadcrumbScopes organisations={[]} selectedOrg="" onSelectOrg={() => {}} scope="programme"
          pathname={window.location.pathname} />
      </nav>
      <Probe />
      {children}
    </ProgrammeScopeProvider>
  )
}

export const scopeChosen = () => screen.getByTestId('scope-chosen').textContent
export const scopePinned = () => screen.getByTestId('scope-pinned').textContent
/** The gift crumb's switch, or null when the crumb is plain text. */
export const crumbSwitch = () => screen.queryByRole('button', { name: 'admin.shell.switchProgramme' })
export const crumbText = () => screen.getByTestId('crumb').textContent
