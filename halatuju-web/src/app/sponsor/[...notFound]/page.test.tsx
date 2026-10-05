import fs from 'fs'
import path from 'path'

/**
 * THE SPONSOR PORTAL'S 404 SINK — the twin of the console's, pinned the same way.
 *
 * ⚠ **WHY A FILESYSTEM TEST AND NOT A RENDER TEST.** What broke here was not behaviour, it was
 * REACHABILITY: `app/sponsor/not-found.tsx` shipped with request #25 and every suite stayed green
 * while nothing on earth could render it, because nothing under `/sponsor` threw `notFound()`.
 * A render test of the 404 page would have passed then and passes now, so it cannot be the guard.
 * The thing to pin is the PAIR — a sink that throws, and a boundary for it to throw to — because
 * either one alone is silently inert.
 */
const SPONSOR_DIR = path.join(process.cwd(), 'src', 'app', 'sponsor')

const routeDirs = () =>
  fs.readdirSync(SPONSOR_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)

const isCatchAll = (seg: string) => seg.startsWith('[...')

describe('the sponsor portal 404 sink', () => {
  it('keeps exactly one catch-all, and it is the top-level one', () => {
    expect(routeDirs().filter(isCatchAll)).toEqual(['[...notFound]'])
  })

  it('throws rather than rendering, so the address 404s instead of becoming a page', () => {
    // A catch-all that RENDERED something would turn every unmatched sponsor address into a real
    // page. Throwing is the whole job.
    const src = fs.readFileSync(path.join(SPONSOR_DIR, '[...notFound]', 'page.tsx'), 'utf8')
    expect(src).toContain('notFound()')
  })

  it('has a boundary to throw to, or Next falls back to the PUBLIC 404', () => {
    // This is the assertion that would have caught the original gap: without this file the sink
    // throws past the portal and lands on the root 404, whose way out is the public site — the
    // exact defect request #25 set out to fix.
    expect(fs.existsSync(path.join(SPONSOR_DIR, 'not-found.tsx'))).toBe(true)
  })

  it('sends a sponsor back into the PORTAL, never to the public site', () => {
    const src = fs.readFileSync(path.join(SPONSOR_DIR, 'not-found.tsx'), 'utf8')
    expect(src).toContain('href="/sponsor"')
    // `href="/"` is the root 404's way out and the thing being fixed; it must not reappear here.
    expect(src).not.toContain('href="/"')
  })

  it('does not shadow a real portal route — every sibling is still its own directory', () => {
    // Static and dynamic segments beat a catch-all in the router, so these win. The test exists
    // so that DELETING one of them is noticed here rather than in production.
    const dirs = routeDirs()
    for (const real of ['login', 'register', 'pool', 'auth', '(portal)']) {
      expect(dirs).toContain(real)
    }
  })
})
