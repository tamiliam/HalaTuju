# Measuring contrast on the real rendered product

Written at Layer 1 F7d (2026-09-02), which used it to walk all 25 surfaces in both modes and found
**TD-224** — 263 failing elements in light mode, live in production.

## Results, measured with this procedure

| run | light (elements / distinct) | dark |
|---|---|---|
| F7d, 2026-09-02 — the finding | **263 / 55** | 54 / 11 |
| **F7e, 2026-09-04 — after the fix** | **1 / 1** | **1 / 1** |

The one remaining element in each mode is the decorative `·` separator (`text-ground-300 mx-1.5`,
1.47 light / 3.04 dark). It carries no information and is excluded under "Reading the result"
below — **stated here rather than quietly dropped**, so a later reader can disagree with the
judgement rather than wonder whether it was made.

⚠ **THIS PROCEDURE FOUND WHAT THE STATIC PASS STRUCTURALLY COULD NOT.** F7e's codemod matched the
pair `bg-<tone>` + `text-white` within ONE LINE. `CourseCard`'s score badge holds its fill class
and its `text-white` on lines twenty apart, so no line-scanning tool could ever pair them — the
number on the merit bar measured **1.67**, and only the browser saw it. Run this before believing
a repaint is finished.

This is a **procedure, not a tool.** It needs a browser and a running dev server, so it cannot be a
CI gate, and it needs no dependency the app does not already have. Keep it as a snippet.

---

## Why the automated gates cannot do this

The project has three colour guards and this finds things all three are blind to:

| guard | reads | blind to |
|---|---|---|
| `theme.test.ts` tree scan | class names as TEXT | what a class actually computes to |
| `contrast.py` | the token values, in pairs it NAMES | every pair it does not name — tone fills, `ground-400` as ink |
| `next build` / `tsc` | types | colour entirely |

**A rendered element's contrast is a property of the whole cascade**: inherited ink, an ancestor's
background, alpha compositing, and which mode is painted. Only a browser knows all four. F7c's
white-on-white form controls were exactly this — an absent declaration plus an inherited colour,
invisible to every static scan the project has.

---

## Running it

1. Start the app with the sandbox on, so the admin, reviewer, cockpit and sponsor surfaces are
   reachable without a login:

   ```
   cd halatuju-web
   NEXT_PUBLIC_SANDBOX=1 npx next dev -p 3100
   ```

2. Open `http://localhost:3100/sandbox/pieces` and run the snippet below in the console. It loads
   each route into an offscreen iframe, so one run covers every surface.

3. Change `localStorage.setItem('halatuju.theme', ...)` between `'light'` and `'dark'` and run twice.
   **Run both.** F7d's whole finding is that the mode nobody expected to be broken was the worse one.

---

## Two things the first draft got wrong

**⚠ COMPOSITE ALPHA; DO NOT TREAT A SEMI-TRANSPARENT BACKGROUND AS OPAQUE.** The first version
walked up to the first background with non-zero alpha and measured against that raw colour. Tinted
panels (`bg-positive-900/40` and friends) then reported failures that do not exist. It invented four.

**⚠ BITE-CHECK THE SWEEP BEFORE TRUSTING A ZERO.** The landing page returned 0 failures on the first
run, which is exactly the shape of a scan that is silently matching nothing. Plant two defects and
confirm both are caught before believing any clean result:

```js
const box = document.createElement('div')
const p = document.createElement('p')
p.textContent = 'planted low contrast'
p.style.cssText = 'color:#555;background:#333;font-size:13px'
const input = document.createElement('input')
input.value = 'planted invisible'
input.style.cssText = 'background:#101010;color:#101010;font-size:13px'
box.append(p, input)
document.body.appendChild(box)
// re-run the sweep: it must report ratio 1.69 and ratio 1.00
```

The second plant is the F7c shape exactly — a control whose ink equals its own background.

---

## The snippet

```js
(async () => {
  const ROUTES = [
    '/', '/search', '/about', '/terms', '/privacy', '/settings', '/stpm/search', '/sponsor/trust',
    '/sandbox/documents', '/sandbox/documents-lean', '/sandbox/application-steps',
    '/sandbox/application-steps-lean', '/sandbox/apply-results', '/sandbox/apply-results-stpm',
    '/sandbox/apply-results-form-six', '/sandbox/sponsor-browse', '/sandbox/action-centre',
    '/sandbox/action-centre-clear', '/sandbox/pieces', '/sandbox/sponsor-landing',
    '/sandbox/category-colours', '/sandbox/course-guide', '/sandbox/officer-cockpit',
    '/sandbox/programme-config', '/sandbox/programme-config-lean',
  ]

  const parse = (c) => { const m = (c || '').match(/[\d.]+/g); if (!m) return null
    return [Number(m[0]), Number(m[1]), Number(m[2]), m[3] === undefined ? 1 : Number(m[3])] }
  const over = (fg, bg) => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat([1])
  const lum = (rgb) => { const [r, g, b] = rgb.slice(0, 3).map((v) => { v /= 255
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) })
    return 0.2126 * r + 0.7152 * g + 0.0722 * b }
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b)
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05) }

  // Walk up compositing every layer, and stop only at a fully opaque one.
  const bgOf = (el, win) => {
    const stack = []
    let p = el
    while (p) { const c = parse(win.getComputedStyle(p).backgroundColor)
      if (c && c[3] > 0) stack.push(c)
      if (c && c[3] === 1) break
      p = p.parentElement }
    let out = [255, 255, 255, 1]
    for (let i = stack.length - 1; i >= 0; i--) out = over(stack[i], out)
    return out
  }

  const sweep = (doc) => {
    const win = doc.defaultView
    const fails = []
    for (const el of doc.querySelectorAll('body *')) {
      const cs = win.getComputedStyle(el)
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') continue
      const r = el.getBoundingClientRect()
      if (r.width < 2 || r.height < 2) continue
      const isControl = /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)
      // OWN text nodes only — otherwise every ancestor is re-measured with its children's text.
      const own = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim())
        .map((n) => n.textContent.trim()).join(' ')
      const text = isControl ? (el.value || el.placeholder || ' ') : own
      if (!text) continue
      const bg = bgOf(el, win)
      let fg = parse(cs.color); if (!fg) continue
      if (fg[3] < 1) fg = over(fg, bg)
      const cr = ratio(fg, bg)
      const size = parseFloat(cs.fontSize)
      const weight = parseInt(cs.fontWeight, 10) || 400
      const bar = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3.0 : 4.5
      if (cr < bar) fails.push({ cls: (el.className || '').toString(), text: text.slice(0, 30),
        fg: `rgb(${fg.slice(0, 3).map(Math.round).join(' ')})`,
        bg: `rgb(${bg.slice(0, 3).map(Math.round).join(' ')})`,
        ratio: +cr.toFixed(2), bar, size })
    }
    return fails
  }

  localStorage.setItem('halatuju.theme', 'dark')   // <- swap to 'light' and run again
  const frame = document.createElement('iframe')
  frame.style.cssText = 'position:fixed;left:0;top:0;width:1400px;height:900px;border:0;z-index:-1'
  document.body.appendChild(frame)
  const all = []
  for (const route of ROUTES) {
    await new Promise((res) => { frame.onload = res; frame.src = route })
    await new Promise((r) => setTimeout(r, 1400))
    const doc = frame.contentDocument
    // Fail loudly rather than sweeping the wrong mode for 25 routes.
    const theme = doc.documentElement.getAttribute('data-theme')
    if (theme !== localStorage.getItem('halatuju.theme')) throw new Error(`${route}: got ${theme}`)
    for (const f of sweep(doc)) all.push({ route, ...f })
  }
  frame.remove()

  // One class + colour pair repeated 40 times is ONE defect. Group before reading.
  const seen = new Map()
  for (const f of all) { const k = `${f.cls}|${f.fg}|${f.bg}`
    if (!seen.has(k)) seen.set(k, { ...f, count: 1, routes: [f.route] })
    else { const s = seen.get(k); s.count++; if (!s.routes.includes(f.route)) s.routes.push(f.route) } }
  console.table([...seen.values()].sort((a, b) => a.ratio - b.ratio))
  return { total: all.length, distinct: seen.size }
})()
```

---

## Reading the result

- **Group before judging.** 52 copies of one disabled button is one decision, not 52.
- **Exclude disabled controls.** WCAG 1.4.3 exempts inactive components; a muted disabled button at
  1.34 is not a defect.
- **Decorative glyphs** (`·`, bullet separators) carry no information and are not text for this
  purpose. Say so explicitly rather than quietly dropping them.
- The bar is **4.5** for body text and **3.0** only for text at 24px, or 18.66px bold. Most of what
  fails here is `text-xs`, which is 12px and gets no concession.
