/**
 * @jest-environment jsdom
 *
 * TD-076 (2026-10-05): the Settings page's version comes from the BUILD, never a typed literal.
 * Two different build values render two different versions — a literal could only ever show one.
 */
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'fs'
import { join } from 'path'

import SettingsPage from './page'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  LOCALE_LABELS: { en: 'English' },
}))
jest.mock('@/components/LanguageSelector', () => () => null)
jest.mock('@/components/ThemeSelector', () => () => null)
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)

const ORIGINAL = process.env.NEXT_PUBLIC_APP_VERSION
afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_APP_VERSION
  else process.env.NEXT_PUBLIC_APP_VERSION = ORIGINAL
})

const renderWith = (sha: string | undefined) => {
  if (sha === undefined) delete process.env.NEXT_PUBLIC_APP_VERSION
  else process.env.NEXT_PUBLIC_APP_VERSION = sha
  // Read at RENDER time (`appVersion()`), so one import serves every build value below.
  return render(<SettingsPage />)
}

describe('the version on the Settings page (TD-076)', () => {
  it('shows the build commit, shortened the way git does', () => {
    renderWith('9c0fe4a3b2d1e0f9')
    expect(screen.getByText('9c0fe4a')).toBeTruthy()
  })

  it('shows a DIFFERENT build’s commit — so it cannot be a literal', () => {
    renderWith('315c71af00000000')
    expect(screen.getByText('315c71a')).toBeTruthy()
    expect(screen.queryByText('9c0fe4a')).toBeNull()
  })

  it('says dev when the build stamped nothing (a local build)', () => {
    renderWith(undefined)
    expect(screen.getByText('dev')).toBeTruthy()
  })

  it('⚠ the deploy stamps it: cloudbuild passes the commit and the Dockerfile exposes it', () => {
    const cb = readFileSync(join(__dirname, '../../../cloudbuild.yaml'), 'utf8')
    const df = readFileSync(join(__dirname, '../../../Dockerfile'), 'utf8')
    expect(cb).toMatch(/- --build-arg\s+- COMMIT_SHA=\$COMMIT_SHA/)
    expect(df).toMatch(/ARG COMMIT_SHA=/)
    expect(df).toMatch(/ENV NEXT_PUBLIC_APP_VERSION=\$\{COMMIT_SHA\}/)
    expect(df.indexOf('NEXT_PUBLIC_APP_VERSION')).toBeLessThan(df.indexOf('RUN npm run build'))
  })
})
