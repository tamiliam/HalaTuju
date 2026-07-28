import { readFileSync, readdirSync, statSync } from 'fs'
import { join } from 'path'

/**
 * The sandbox is handed to people outside the organisation, so the things that make it safe have
 * to be mechanical rather than remembered.
 *
 * Four properties, each of which would be silently lost otherwise:
 *  1. No fixture resembles a real person.
 *  2. The sandbox mounts real components; it never contains a copy of one.
 *  3. It is compiled out of a normal build, and the default stays off.
 *  4. Its provider stack has not drifted from the app's.
 *
 * Modelled on `src/lib/__tests__/brand-guard.test.ts`, including its self-check habit: every scan
 * asserts it actually read something, so a broken glob fails loudly instead of passing vacuously.
 */

const SANDBOX_DIR = join(__dirname, '..')
const APP_SANDBOX_DIR = join(__dirname, '..', '..', 'app', 'sandbox')

function walk(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      if (entry === '__tests__') continue
      out.push(...walk(full))
    } else if (/\.(ts|tsx)$/.test(entry)) {
      out.push(full)
    }
  }
  return out
}

const sandboxFiles = [...walk(SANDBOX_DIR), ...walk(APP_SANDBOX_DIR)]
const fixtureFiles = walk(join(SANDBOX_DIR, 'fixtures'))

describe('sandbox fixtures contain no real person', () => {
  it('scans a non-trivial amount of fixture text', () => {
    // Self-check: if the fixtures move, the scans below must not silently pass on nothing.
    expect(fixtureFiles.length).toBeGreaterThan(0)
    const chars = fixtureFiles.reduce((n, f) => n + readFileSync(f, 'utf-8').length, 0)
    expect(chars).toBeGreaterThan(2000)
  })

  it('has no NRIC-shaped digits anywhere', () => {
    // A Malaysian identity number is the highest-consequence string that could leak into a
    // screenshot. Fixtures render `XXXXXX-XX-XXXX` instead — unmistakably not a card.
    for (const file of fixtureFiles) {
      const matches = readFileSync(file, 'utf-8').match(/\d{6}-\d{2}-\d{4}/g)
      expect({ file, matches: matches ?? [] }).toEqual({ file, matches: [] })
    }
  })

  it('routes every email address to a domain that cannot receive mail', () => {
    // `.invalid` is reserved by RFC 2606 and resolves nowhere, so a stray send in a design review
    // cannot reach a person. A plausible-looking address could.
    for (const file of fixtureFiles) {
      const emails = readFileSync(file, 'utf-8').match(/[\w.+-]+@[\w.-]+\.\w+/g) ?? []
      const offenders = emails.filter((e) => !e.endsWith('.invalid'))
      expect({ file, offenders }).toEqual({ file, offenders: [] })
    }
  })

  it('names nobody from the live roster', () => {
    // Real people who appear in production data or documentation. A fixture borrowing one of these
    // names would read as genuine to anyone who knows them.
    const REAL_PEOPLE = ['Poongulali', 'Suresh', 'Elanjelian', 'Vanitha', 'Adhitya', 'Athian']
    for (const file of fixtureFiles) {
      const text = readFileSync(file, 'utf-8')
      const found = REAL_PEOPLE.filter((name) => text.includes(name))
      expect({ file, found }).toEqual({ file, found: [] })
    }
  })
})

describe('the sandbox mounts real components and never copies one', () => {
  it('imports its surfaces from the app, not from a local re-implementation', () => {
    // The failure this prevents: someone hand-writes an approximation of a screen because mounting
    // the real one was awkward, a designer approves it, and we build something that was never on
    // the actual page. Every product import must come from the app's own modules.
    const offenders: string[] = []
    for (const file of sandboxFiles) {
      const imports = readFileSync(file, 'utf-8').match(/from ['"]([^'"]+)['"]/g) ?? []
      for (const imp of imports) {
        const spec = imp.replace(/from ['"]|['"]/g, '')
        const isRelativeWithinSandbox = spec.startsWith('.')
        const isApp = spec.startsWith('@/components') || spec.startsWith('@/lib') || spec.startsWith('@/app')
        const isSandbox = spec.startsWith('@/sandbox')
        const isPackage = !spec.startsWith('.') && !spec.startsWith('@/')
        if (!isRelativeWithinSandbox && !isApp && !isSandbox && !isPackage) {
          offenders.push(`${file}: ${spec}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('mounts at least one real product component', () => {
    // Self-check with teeth: a sandbox that imports nothing from `@/components` is not rendering
    // the product, whatever else it does.
    const text = sandboxFiles.map((f) => readFileSync(f, 'utf-8')).join('\n')
    expect(text).toMatch(/from '@\/components\//)
  })
})

describe('the sandbox is compiled out of a normal build', () => {
  const config = readFileSync(join(__dirname, '..', '..', '..', 'next.config.js'), 'utf-8')

  it('gates the sandbox page extension on NEXT_PUBLIC_SANDBOX', () => {
    expect(config).toMatch(/pageExtensions/)
    expect(config).toMatch(/NEXT_PUBLIC_SANDBOX/)
    expect(config).toMatch(/'sandbox\.tsx'/)
  })

  it('is OFF unless the variable is set', () => {
    // The property that matters: an ordinary build ships neither the fixtures nor the stubbed
    // fetch. Asserting the default here means a change to it has to be deliberate.
    expect(process.env.NEXT_PUBLIC_SANDBOX).toBeFalsy()
  })

  it('names every sandbox route with the gated extension', () => {
    // A page named `page.tsx` under /app/sandbox would be a live production route, which is the
    // one mistake this whole mechanism exists to prevent.
    const routeFiles = walk(APP_SANDBOX_DIR).filter((f) => /[\\/](page|layout)\./.test(f))
    expect(routeFiles.length).toBeGreaterThan(0)
    const ungated = routeFiles.filter((f) => !f.endsWith('.sandbox.tsx'))
    expect(ungated).toEqual([])
  })
})

describe('the sandbox provider stack has not drifted from the app', () => {
  it('mounts every provider the app mounts, minus the two it must not', () => {
    // `tsc` cannot catch this: adding a provider to the app leaves the sandbox compiling happily
    // and rendering a subtly different tree. AuthProvider is excluded on purpose (it mints an
    // anonymous Supabase user on mount — real auth rows for a design review), and AuthGateModal
    // would open over the screens the designer came to see.
    const EXCLUDED = ['AuthProvider', 'AuthGateModal']
    const appStack = readFileSync(join(__dirname, '..', '..', 'app', 'providers.tsx'), 'utf-8')
    const sandboxStack = readFileSync(join(__dirname, '..', 'providers.tsx'), 'utf-8')

    const providersIn = (src: string) =>
      Array.from(src.matchAll(/<(\w+Provider|AuthGateModal)[\s/>]/g)).map((m) => m[1])

    const expected = Array.from(new Set(providersIn(appStack))).filter((p) => !EXCLUDED.includes(p))
    expect(expected.length).toBeGreaterThan(2)  // self-check

    const missing = expected.filter((p) => !sandboxStack.includes(`<${p}`))
    expect({ missing }).toEqual({ missing: [] })
  })
})
