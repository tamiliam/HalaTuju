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

/*
 * CAPTCHA REPAIR (2026-11-19) — the typed outcome, the longer silent budget, the retry, the
 * script-load budget and expiry. Supabase's captcha switch is ON: an outcome other than `ok` now
 * stops the auth callers from calling Supabase at all (lib/captchaAuth.ts), so each outcome has
 * to be the RIGHT one.
 */
describe('getTurnstileResult', () => {
  const ORIG = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
  const g = global as unknown as { window?: unknown; document?: unknown }

  afterEach(() => {
    jest.useRealTimers()
    if (ORIG === undefined) delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
    else process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = ORIG
    delete g.window
    delete g.document
  })

  /** A widget whose execute() runs `onExecute(opts, n)` for the n-th call (1-based). */
  function widget(onExecute: (opts: Record<string, unknown>, n: number) => void) {
    const calls = { execute: 0, reset: [] as unknown[] }
    let opts: Record<string, unknown> = {}
    g.window = {
      turnstile: {
        render: (_e: unknown, o: Record<string, unknown>) => { opts = o; return 'wid-1' },
        execute: () => { calls.execute += 1; onExecute(opts, calls.execute) },
        reset: (id: unknown) => { calls.reset.push(id) },
        remove: () => {},
      },
    }
    g.document = {
      createElement: () => ({ style: {} }),
      head: { appendChild: () => {} },
      body: { appendChild: () => {}, removeChild: () => {} },
    }
    return { calls, opts: () => opts }
  }

  type FakeScript = { onload?: () => void; onerror?: () => void; remove: () => void }

  /** No window.turnstile yet: the script tag is appended, and `onAppend` decides its fate. */
  function scriptTag(onAppend: (s: FakeScript) => void) {
    const appended: unknown[] = []
    g.window = {}
    g.document = {
      createElement: () => ({ style: {}, remove: jest.fn() }),
      head: {
        appendChild: (s: FakeScript) => {
          appended.push(s)
          onAppend(s)
        },
      },
      body: { appendChild: () => {}, removeChild: () => {} },
    }
    return appended
  }

  it('off: no site key, and nothing is loaded', async () => {
    delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
    const appended = scriptTag(() => {})
    const mod = loadFresh()
    await expect(mod.getTurnstileResult('admin_signin')).resolves.toEqual({ status: 'off' })
    expect(appended).toHaveLength(0)
  })

  it('ok: the token comes back typed', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    widget((o) => (o.callback as (t: string) => void)('tok-1'))
    const mod = loadFresh()
    await expect(mod.getTurnstileResult('admin_signin')).resolves.toEqual({ status: 'ok', token: 'tok-1' })
  })

  it('blocked: the script is refused (ad blocker), and the next call asks for it again', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    const appended = scriptTag((s) => s.onerror?.())
    const mod = loadFresh()
    await expect(mod.getTurnstileResult()).resolves.toEqual({ status: 'blocked' })
    await expect(mod.getTurnstileResult()).resolves.toEqual({ status: 'blocked' })
    expect(appended).toHaveLength(2)
  })

  it('blocked: the script never arrives (a firewall drops it silently), so it gives up after the load budget', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    scriptTag(() => { /* never loads, never errors */ })
    const mod = loadFresh()
    let result: unknown = null
    void mod.getTurnstileResult().then((r) => { result = r })
    await jest.advanceTimersByTimeAsync(mod.SCRIPT_LOAD_TIMEOUT_MS - 1)
    expect(result).toBeNull()
    await jest.advanceTimersByTimeAsync(1)
    expect(result).toEqual({ status: 'blocked' })
  })

  it('a slow script that loads within the budget still works', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    let opts: Record<string, unknown> = {}
    const api = {
      render: (_e: unknown, o: Record<string, unknown>) => { opts = o; return 'wid-1' },
      execute: () => (opts.callback as (t: string) => void)('tok-slow'),
      reset: () => {}, remove: () => {},
    }
    scriptTag((s) => {
      setTimeout(() => { (g.window as { turnstile?: unknown }).turnstile = api; s.onload?.() }, 6000)
    })
    const mod = loadFresh()
    const p = mod.getTurnstileResult()
    await jest.advanceTimersByTimeAsync(6000)
    await expect(p).resolves.toEqual({ status: 'ok', token: 'tok-slow' })
  })

  it('the silent budget is longer than the old 8 s: a pass at 12 s succeeds first time', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    const w = widget((o) => { setTimeout(() => (o.callback as (t: string) => void)('tok-12s'), 12000) })
    const mod = loadFresh()
    expect(mod.SILENT_TIMEOUT_MS).toBeGreaterThan(8000)
    const p = mod.getTurnstileResult()
    await jest.advanceTimersByTimeAsync(12000)
    await expect(p).resolves.toEqual({ status: 'ok', token: 'tok-12s' })
    expect(w.calls.execute).toBe(1)
  })

  it('failed: both attempts time out silently (reset + execute each time)', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    const w = widget(() => { /* Cloudflare never answers */ })
    const mod = loadFresh()
    let result: unknown = null
    void mod.getTurnstileResult().then((r) => { result = r })
    await jest.advanceTimersByTimeAsync(mod.SILENT_TIMEOUT_MS)
    expect(result).toBeNull()                       // the first timeout starts the retry
    expect(w.calls.execute).toBe(2)
    await jest.advanceTimersByTimeAsync(mod.SILENT_TIMEOUT_MS)
    expect(result).toEqual({ status: 'failed' })
    expect(w.calls.reset).toEqual(['wid-1', 'wid-1'])
    expect(mod.MAX_ATTEMPTS).toBe(2)
  })

  it('retry then success: an error on the first attempt, a token on the second', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    const w = widget((o, n) => {
      if (n === 1) (o['error-callback'] as () => void)()
      else (o.callback as (t: string) => void)('tok-retry')
    })
    const mod = loadFresh()
    await expect(mod.getTurnstileResult()).resolves.toEqual({ status: 'ok', token: 'tok-retry' })
    expect(w.calls.execute).toBe(2)
  })

  it('timeout then success: a silent timeout, then a token on the retry', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    widget((o, n) => { if (n === 2) (o.callback as (t: string) => void)('tok-2nd') })
    const mod = loadFresh()
    const p = mod.getTurnstileResult()
    await jest.advanceTimersByTimeAsync(mod.SILENT_TIMEOUT_MS)
    await expect(p).resolves.toEqual({ status: 'ok', token: 'tok-2nd' })
  })

  it('a late token from a timed-out attempt is dropped, never handed to the next caller', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    let n = 0
    widget((o) => {
      n += 1
      if (n === 1) setTimeout(() => (o.callback as (t: string) => void)('tok-late'), 20000)
      else (o.callback as (t: string) => void)(`tok-fresh-${n}`)
    })
    const mod = loadFresh()
    const p = mod.getTurnstileResult()
    await jest.advanceTimersByTimeAsync(mod.SILENT_TIMEOUT_MS)
    await expect(p).resolves.toEqual({ status: 'ok', token: 'tok-fresh-2' })
    await jest.advanceTimersByTimeAsync(10000)       // the stale token turns up now, with nobody waiting
    await expect(mod.getTurnstileResult()).resolves.toEqual({ status: 'ok', token: 'tok-fresh-3' })
  })

  it('a visible challenge nobody solves is NOT retried (no second two-minute wait)', async () => {
    jest.useFakeTimers()
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    const w = widget((o) => (o['before-interactive-callback'] as () => void)())
    const mod = loadFresh()
    let result: unknown = null
    void mod.getTurnstileResult().then((r) => { result = r })
    await jest.advanceTimersByTimeAsync(mod.SILENT_TIMEOUT_MS + 1)
    expect(result).toBeNull()                       // the human budget replaced the silent one
    await jest.advanceTimersByTimeAsync(mod.INTERACTIVE_TIMEOUT_MS)
    expect(result).toEqual({ status: 'failed' })
    expect(w.calls.execute).toBe(1)
  })

  it('expiry: tokens are never auto-refreshed, and an expired one resets the widget', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    let n = 0
    const w = widget((o) => { n += 1; (o.callback as (t: string) => void)(`tok-${n}`) })
    const mod = loadFresh()
    await expect(mod.getTurnstileResult()).resolves.toEqual({ status: 'ok', token: 'tok-1' })
    expect(w.opts()['refresh-expired']).toBe('manual')
    const resetsBefore = w.calls.reset.length
    ;(w.opts()['expired-callback'] as () => void)()   // about 300 s later, the unused token lapses
    expect(w.calls.reset.length).toBe(resetsBefore + 1)
    // The next caller gets a FRESH token from a new execute, never the lapsed one.
    await expect(mod.getTurnstileResult()).resolves.toEqual({ status: 'ok', token: 'tok-2' })
  })

  it('the contact form wrapper still answers string | undefined', async () => {
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = '0xTESTKEY'
    scriptTag((s) => s.onerror?.())
    const mod = loadFresh()
    await expect(mod.getTurnstileToken('contact')).resolves.toBeUndefined()
  })
})
