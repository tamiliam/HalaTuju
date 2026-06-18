/**
 * Tests for the Turnstile token utility. The jest env is 'node' (no real DOM), so
 * we stub a minimal window.turnstile + document to drive the render/execute path,
 * and separately assert the graceful-degradation property that makes the rollout
 * safe: with no site key, getTurnstileToken resolves undefined and never throws.
 */

type Mod = typeof import('../turnstile')

function loadFresh(): Mod {
  let mod!: Mod
  jest.isolateModules(() => {
    mod = require('../turnstile')
  })
  return mod
}

function stubDom(executeImpl: (opts: Record<string, unknown>) => void) {
  let savedOpts: Record<string, unknown> = {}
  ;(global as unknown as { window: unknown }).window = {
    turnstile: {
      render: (_el: unknown, opts: Record<string, unknown>) => {
        savedOpts = opts
        return 'wid-1'
      },
      execute: () => executeImpl(savedOpts),
      reset: () => {},
      remove: () => {},
    },
  }
  ;(global as unknown as { document: unknown }).document = {
    createElement: () => ({ style: {} }),
    head: { appendChild: () => {} },
    body: { appendChild: () => {}, removeChild: () => {} },
  }
}

describe('turnstile', () => {
  const ORIG = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY

  afterEach(() => {
    if (ORIG === undefined) delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
    else process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = ORIG
    delete (global as unknown as { window?: unknown }).window
    delete (global as unknown as { document?: unknown }).document
  })

  it('degrades gracefully with no site key: not configured, resolves undefined, no throw', async () => {
    delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
    const mod = loadFresh()
    expect(mod.isTurnstileConfigured()).toBe(false)
    await expect(mod.getTurnstileToken()).resolves.toBeUndefined()
  })

  it('fetches a token via render + execute when configured', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    stubDom((opts) => (opts.callback as (t: string) => void)('tok-abc'))
    const mod = loadFresh()
    expect(mod.isTurnstileConfigured()).toBe(true)
    await expect(mod.getTurnstileToken('contact')).resolves.toBe('tok-abc')
  })

  it('resolves undefined when Turnstile fires its error-callback', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    stubDom((opts) => (opts['error-callback'] as () => void)())
    const mod = loadFresh()
    await expect(mod.getTurnstileToken()).resolves.toBeUndefined()
  })

  it('reveals the box for an interaction challenge then hides it once solved (no lingering box)', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    const el = { style: {} as Record<string, string> }
    let opts: Record<string, unknown> = {}
    ;(global as unknown as { window: unknown }).window = {
      turnstile: {
        render: (_e: unknown, o: Record<string, unknown>) => { opts = o; return 'wid-1' },
        execute: () => {
          // Cloudflare decides a human must solve it: the box is revealed...
          ;(opts['before-interactive-callback'] as () => void)()
          expect(el.style.display).toBe('') // visible WHILE the challenge is up
          // ...and the human solves it (well past the 8s silent budget in real life).
          ;(opts.callback as (t: string) => void)('tok-int')
        },
        reset: () => {}, remove: () => {},
      },
    }
    ;(global as unknown as { document: unknown }).document = {
      createElement: () => el,
      head: { appendChild: () => {} },
      body: { appendChild: () => {}, removeChild: () => {} },
    }
    const mod = loadFresh()
    await expect(mod.getTurnstileToken('admin_signin')).resolves.toBe('tok-int')
    expect(el.style.display).toBe('none') // cleared after — never lingers over the app
  })

  it('serialises concurrent calls so each gets its own fresh token', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    let n = 0
    stubDom((opts) => {
      n += 1
      ;(opts.callback as (t: string) => void)(`tok-${n}`)
    })
    const mod = loadFresh()
    const [a, b] = await Promise.all([mod.getTurnstileToken(), mod.getTurnstileToken()])
    expect(a).toBe('tok-1')
    expect(b).toBe('tok-2')
  })
})
