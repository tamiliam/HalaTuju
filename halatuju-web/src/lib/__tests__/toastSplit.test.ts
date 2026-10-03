/**
 * TD-289 (2026-10-03): a page that only RAISES a toast imports the context, never the provider.
 *
 * `Toast.tsx` holds the provider, its state and the toast markup; the layout mounts it once.
 * `useToast` lives in `ToastContext.ts`. While the hook lived in `Toast.tsx`, the language picker
 * pulled the whole provider module into `/`'s page chunk (measured 2026-10-03: `/` 3.33 → 2.94 kB
 * page JS, 232 → 231 kB first load; six other routes one kB lighter; none heavier — against a
 * control build of the same tree without the split). A structural claim, so a source guard: every
 * `useToast` caller imports it from `ToastContext`, and only the two provider mounts import `Toast`.
 */
import fs from 'fs'
import path from 'path'

import { readWeb, walkFloor } from '@/test/sourceGuard'

const WEB = path.resolve(__dirname, '..', '..', '..')

const CALLERS = [
  'src/components/LanguageSelector.tsx',
  'src/app/dashboard/page.tsx',
  'src/app/profile/page.tsx',
  'src/app/saved/page.tsx',
  'src/hooks/useSavedCourses.ts',
]
const PROVIDER_MOUNTS = ['src/app/providers.tsx', 'src/sandbox/providers.tsx']

describe('TD-289 — the toast context is apart from its provider', () => {
  it('every raiser imports useToast from ToastContext', () => {
    for (const f of CALLERS) {
      const src = readWeb(f, 'TD-289: a page raising a toast imports only the context')
      expect(src).toContain("import { useToast } from '@/components/ToastContext'")
      expect(src).not.toMatch(/from '@\/components\/Toast'/)
    }
  })

  it('only the provider mounts import Toast.tsx, and Toast.tsx no longer exports the hook', () => {
    const files = walkFloor(path.join(WEB, 'src'), 300, 'TD-289: every source file that could import the toast module',
      { exts: ['.ts', '.tsx'] })
    const importers = files
      .filter((f) => !/\.test\.tsx?$/.test(f))
      .filter((f) => /from '@\/components\/Toast'/.test(fs.readFileSync(f, 'utf8')))
      .map((f) => path.relative(WEB, f).replace(/\\/g, '/'))
    expect(importers.sort()).toEqual(PROVIDER_MOUNTS.slice().sort())
    const toast = readWeb('src/components/Toast.tsx', 'TD-289: the provider module')
    expect(toast).toContain('export function ToastProvider')
    expect(toast).not.toContain('export function useToast')
  })
})
