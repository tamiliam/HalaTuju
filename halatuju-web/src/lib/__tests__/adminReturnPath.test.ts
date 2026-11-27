/**
 * @jest-environment jsdom
 *
 * The admin sign-in's return path (#86, review round 1): only a same-origin `/admin/` path is ever
 * followed after sign-in. The hostile inputs are the point of this file.
 */
import {
  adminLoginHref, adminReturnTarget, adminSignedOutHref, markAdminSigningOut, nextFromSearch,
  rememberAdminNext, safeAdminNext, takeRememberedAdminNext,
} from '@/lib/adminReturnPath'
import { CHROMELESS } from '@/lib/navigation'

const CASE = '/admin/scholarship/513'

describe('safeAdminNext accepts only a same-origin /admin/ path', () => {
  it.each([
    CASE,
    '/admin/scholarship?assigned=me&band=open',
    '/admin/scholarship/513#notes',
  ])('accepts %s', (p) => expect(safeAdminNext(p)).toBe(p))

  it.each([
    null, undefined, '', '/', '/admin', 'admin/scholarship/513',
    '//evil.example', '///evil.example', '/\\evil.example', '\\\\evil.example',
    '/admin//evil.example', '/admin/\\evil.example', '/admin/..\\evil',
    'https://evil.example/admin/x', 'javascript:alert(1)', 'data:text/html,x',
    '/admin/%2F%2Fevil.example', '/admin/%2f%2fevil', '/admin/%5Cevil', '/admin/%2e%2e/x',
    '/admin/../evil', '/admin/./x', '/admin/x/../../evil',
    '/admin/x\nLocation: //evil', '/admin/x\t', '/admin/ x', '/admin/\u0000x',
    '/admin/login', '/admin/auth/callback',
    // review round 2: every chromeless sign-in page, with a trailing slash, a subpath or a query
    '/admin/login/', '/admin/login/x', '/admin/login?next=%2Fadmin%2Fx', '/admin/login#x',
    '/admin/set-password', '/admin/set-password/', '/admin/set-password?x=1',
    '/admin/auth', '/admin/auth/', '/admin/auth/callback?code=x',
    '/admin/' + 'a'.repeat(2050),
  ])('refuses %p', (p) => expect(safeAdminNext(p as string)).toBeNull())

  it('refuses every page the layout renders without chrome (its own CHROMELESS list)', () => {
    for (const c of CHROMELESS) {
      expect(safeAdminNext(c)).toBeNull()
      expect(safeAdminNext(c.replace(/\/$/, '') + '/x')).toBeNull()
    }
  })
})

describe('a deliberate sign-out never carries next (review round 2)', () => {
  beforeEach(() => { window.sessionStorage.clear(); adminSignedOutHref('/') })   // no mark left over
  afterEach(() => jest.restoreAllMocks())

  it('plain login once after the mark, then the page again', () => {
    markAdminSigningOut()
    expect(adminSignedOutHref(CASE)).toBe('/admin/login')
    expect(adminSignedOutHref(CASE)).toBe(adminLoginHref(CASE))
  })
  it('without a mark (expiry, unauthenticated visit) the page is kept', () => {
    expect(adminSignedOutHref(CASE)).toBe(`/admin/login?next=${encodeURIComponent(CASE)}`)
  })
  it('clears a remembered next', () => {
    rememberAdminNext(CASE)
    markAdminSigningOut()
    expect(takeRememberedAdminNext()).toBeNull()
  })
  it('a stale mark (a sign-out that never reached the guard) does not swallow a later expiry', () => {
    const now = Date.now()
    jest.spyOn(Date, 'now').mockReturnValue(now)
    markAdminSigningOut()
    jest.spyOn(Date, 'now').mockReturnValue(now + 60_000)
    expect(adminSignedOutHref(CASE)).toBe(adminLoginHref(CASE))
  })
})

describe('nextFromSearch decodes once, then validates', () => {
  it('reads an encoded safe path', () => {
    expect(nextFromSearch(`?next=${encodeURIComponent(CASE)}`)).toBe(CASE)
  })
  it.each([
    '?next=%2F%2Fevil.example',          // -> //evil.example
    '?next=%252F%252Fevil.example',      // -> %2F%2Fevil.example (still encoded: refused)
    '?next=%2Fadmin%2F%252F%252Fevil',   // -> /admin/%2F%2Fevil
    '?next=%2F%5Cevil.example',          // -> /\evil.example
    '?next=https%3A%2F%2Fevil.example',  // -> https://evil.example
    '?next=%2Fadmin%2F%2E%2E%2Fevil',    // -> /admin/../evil
    '?other=1', '',
  ])('refuses %s', (q) => expect(nextFromSearch(q)).toBeNull())
})

describe('adminLoginHref carries only a safe page', () => {
  it('adds next for an admin page', () => {
    expect(adminLoginHref(CASE)).toBe(`/admin/login?next=${encodeURIComponent(CASE)}`)
    expect(nextFromSearch(adminLoginHref(CASE).split('?')[1])).toBe(CASE)
  })
  it.each(['/', '//evil.example', '/admin/login'])('plain login for %s', (p) => {
    expect(adminLoginHref(p)).toBe('/admin/login')
  })
})

describe('adminReturnTarget', () => {
  const reviewer = { role: 'reviewer', reviewer_profile_complete: true, permissions: [] }
  it('goes to a safe next', () => expect(adminReturnTarget(reviewer, CASE)).toBe(CASE))
  it('falls back to the landing for a hostile or missing next', () => {
    const landing = adminReturnTarget(reviewer, null)
    expect(landing).not.toBe(CASE)
    expect(adminReturnTarget(reviewer, '//evil.example')).toBe(landing)
  })
  it('keeps the first-login profile hold', () => {
    const fresh = { ...reviewer, reviewer_profile_complete: false }
    expect(adminReturnTarget(fresh, CASE)).toBe('/admin/profile')
  })
})

describe('the OAuth hop keeps the page in this tab, once', () => {
  beforeEach(() => window.sessionStorage.clear())
  it('remembers, takes and clears a safe next', () => {
    rememberAdminNext(CASE)
    expect(takeRememberedAdminNext()).toBe(CASE)
    expect(takeRememberedAdminNext()).toBeNull()
  })
  it('never keeps a hostile one, and re-validates what it reads', () => {
    rememberAdminNext('//evil.example')
    expect(takeRememberedAdminNext()).toBeNull()
    window.sessionStorage.setItem('halatuju_admin_next', 'https://evil.example')
    expect(takeRememberedAdminNext()).toBeNull()
  })
})
