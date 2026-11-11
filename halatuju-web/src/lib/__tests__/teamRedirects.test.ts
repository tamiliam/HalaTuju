/**
 * Sprint M2a (owner ruling U1): the old Team addresses are PERMANENT redirects in `next.config.js`
 * `redirects()`, explicit and most specific first, with NO `:path*` catch-all (it would send a reviewer's
 * `/reviewers/7` to `/team/7`).
 *
 * `resolve` below follows Next's documented rule for these plain rules: the FIRST source that matches wins,
 * a `:name` is one path segment, and the incoming query is kept (merged after the destination's own).
 */
const teamConfig = require('../../../next.config.js')

type Rule = { source: string; destination: string; permanent?: boolean; has?: unknown; missing?: unknown }

async function rules(): Promise<Rule[]> {
  return teamConfig.redirects()
}

function resolve(all: Rule[], url: string): string | null {
  const [pathname, query = ''] = url.split('?')
  for (const r of all) {
    const names: string[] = []
    const pattern = new RegExp(`^${r.source.replace(/:([a-z]+)/g, (_m, n: string) => { names.push(n); return '([^/]+)' })}$`)
    const m = pathname.match(pattern)
    if (!m) continue
    let out = r.destination
    names.forEach((n, i) => { out = out.replace(`:${n}`, m[i + 1]) })
    if (!query) return out
    return out.includes('?') ? `${out}&${query}` : `${out}?${query}`
  }
  return null
}

it('has exactly the five rules, in this order, every one permanent', async () => {
  expect(await rules()).toEqual([
    { source: '/admin/organisation/reviewers', destination: '/admin/organisation/team', permanent: true },
    { source: '/admin/organisation/reviewers/admins/:id', destination: '/admin/organisation/team/admins/:id',
      permanent: true },
    { source: '/admin/organisation/reviewers/mentors/:id', destination: '/admin/organisation/team/mentors/:id',
      permanent: true },
    { source: '/admin/organisation/reviewers/:id', destination: '/admin/organisation/team/reviewers/:id',
      permanent: true },
    { source: '/admin/organisation/mentors', destination: '/admin/organisation/team?tab=mentors', permanent: true },
  ])
})

it('has no catch-all and no condition that could drop a request', async () => {
  for (const r of await rules()) {
    expect(r.source).not.toMatch(/\*|\(|:path/)
    expect(r.has).toBeUndefined()
    expect(r.missing).toBeUndefined()
  }
})

it.each([
  ['/admin/organisation/reviewers/7', '/admin/organisation/team/reviewers/7'],
  ['/admin/organisation/reviewers/admins/14', '/admin/organisation/team/admins/14'],
  ['/admin/organisation/reviewers/mentors/3', '/admin/organisation/team/mentors/3'],
  ['/admin/organisation/reviewers', '/admin/organisation/team'],
  ['/admin/organisation/mentors', '/admin/organisation/team?tab=mentors'],
])('%s → %s', async (from, to) => {
  expect(resolve(await rules(), from)).toBe(to)
})

it('keeps the query string', async () => {
  const all = await rules()
  expect(resolve(all, '/admin/organisation/reviewers?tab=admins')).toBe('/admin/organisation/team?tab=admins')
  expect(resolve(all, '/admin/organisation/reviewers/admins/14?table=reviewers'))
    .toBe('/admin/organisation/team/admins/14?table=reviewers')
})

it('leaves the new addresses and every other organisation page alone', async () => {
  const all = await rules()
  for (const url of ['/admin/organisation/team', '/admin/organisation/team/reviewers/7', '/admin/organisation/staff',
    '/admin/organisation']) {
    expect(resolve(all, url)).toBeNull()
  }
})
