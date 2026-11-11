/**
 * The measurement, run INSIDE the page (`page.evaluate(measurePage, scope)`).
 *
 * ⚠ SELF-CONTAINED ON PURPOSE. Playwright sends this function to the browser as source text, so it
 * may not use anything from outside its own body — no imports, no helpers from this file.
 *
 * The four numbers (docs/mobile-standard.md rules 1, 2, 3 and 16):
 *
 *  1. overflow — `scrollWidth - clientWidth` of the page, in CSS px. 0 means no sideways scroll.
 *     When it is above 0, `widest` names the element whose box OR content reaches furthest right
 *     (the innermost one, if several end at the same edge), skipping anything fixed, or inside a
 *     box that scrolls or clips
 *     sideways by itself — those are allowed to be wider than the screen (a framed table).
 *  2. smallInputs — visible text-entry controls whose COMPUTED font size is under 16 px (what
 *     makes iPhone zoom on tap). Checkbox, radio, file, range, colour and button inputs are not
 *     text entry and are skipped.
 *  3. smallTargets — visible controls whose box is under 44 × 44 CSS px: links with an href,
 *     buttons, `[role=button]`, selects, `summary`, and checkboxes/radios/FILE inputs — for those the
 *     LABEL is measured when they have one, because the label is what a thumb hits. (File inputs
 *     since Mobile M4: an `sr-only` file input is invisible, so the label that opens the picker —
 *     "Choose file", "Replace", 20 px text links on the documents tab — was never measured at all.
 *     Counting it raised the documents cells for an honest reason; decisions.md.) EXCLUDED: an inline
 *     link inside running text (display `inline` and its block holds more words than the link),
 *     which the standard excepts. The element's own box is measured; a hit area enlarged with a
 *     pseudo-element would not be seen, so the standard asks for padding instead.
 *  4. spills (Mobile M8 follow-up, rule 16) — content passing out of the box that holds it while the page
 *     itself does not scroll: "RM40,000.00" running past its card, a Tamil word out of a 64 px circle, a
 *     fourth figure 70 px past the edge. Two kinds of item are judged: every TEXT run (a text node's words —
 *     a space hanging at the end of a wrapped line is not ink) and every DRAWN box (a border, a fill or a shadow — a chip, a card). An item spills when it
 *     reaches more than 1.5 px past the left or right edge of ANY block box above it, up to the first
 *     ancestor that scrolls or clips sideways. NOT judged: anything fixed (a tab bar, a toast); anything
 *     inside a side-scroller or clipping box (a framed table's rows, a `truncate`); an absolutely placed
 *     item (a popover, a corner badge) or one pulled out by a NEGATIVE margin (a full-bleed section, the
 *     44 px hit area Toggle and InfoTip pad around a small mark) — the walk stops there, since passing its
 *     parent is what such an item is for; SVG (charts scale with their viewBox); and invisible wrappers,
 *     which are neither text nor drawn. One fault counts once: words inside a box that itself spills are
 *     not counted again. `spillExamples` names each item, how far it passes and which box it leaves.
 *
 * "Visible" means a box at least 2 × 2 px (so `sr-only` inputs are out), not `visibility:
 * hidden`, not fully transparent. Off-screen content further down the page still counts: the
 * whole page is one cell, not just its first screen.
 */
export interface Measurement {
  url: string
  lang: string
  overflow: number
  widest: string | null
  smallInputs: number
  smallInputExamples: string[]
  smallTargets: number
  smallTargetExamples: string[]
  spills: number
  spillExamples: string[]
}

export function measurePage(scopeSelector: string): Measurement {
  const doc = document.documentElement
  const vw = doc.clientWidth
  const overflow = Math.max(0, Math.round(doc.scrollWidth - vw))
  // The parts of the page that are measured: every element the selector matches (a sandbox surface
  // is its <main> AND any open dialog, which is portalled outside it), else the whole body.
  const roots = Array.from(document.querySelectorAll(scopeSelector))
  if (roots.length === 0) roots.push(document.body)
  const within = (sel: string): Element[] => roots.flatMap((r) => Array.from(r.querySelectorAll(sel)))

  const describe = (el: Element): string => {
    const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/).slice(0, 4).join('.') : ''
    const text = (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)
    const r = el.getBoundingClientRect()
    return `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${cls ? `.${cls}` : ''}`
      + ` [${Math.round(r.width)}x${Math.round(r.height)}]${text ? ` “${text}”` : ''}`
  }
  const visible = (el: Element): boolean => {
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) return false
    const cs = getComputedStyle(el)
    return cs.visibility !== 'hidden' && cs.opacity !== '0'
  }

  // 1. The widest offender, only worth finding when the page really scrolls sideways.
  let widest: string | null = null
  if (overflow > 0) {
    const clips = new Map<Element, boolean>()
    const insideSideScroller = (el: Element): boolean => {
      const chain: Element[] = []
      let cur = el.parentElement
      let found = false
      while (cur && cur !== document.body && cur !== doc) {
        const known = clips.get(cur)
        if (known !== undefined) { found = known; break }
        chain.push(cur)
        const ox = getComputedStyle(cur).overflowX
        if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') { found = true; break }
        cur = cur.parentElement
      }
      for (const c of chain) clips.set(c, found)
      return found
    }
    // An element "reaches" its own right edge, or further when its CONTENT spills out of it — a
    // long unbreakable word overflows its heading while the heading's box stays inside the screen
    // (TD-311's Tamil hero is exactly that), so box edges alone find nothing.
    // TD-464: anything INSIDE a fixed ancestor is not the page's flow either (a fixed tab bar's tab, not the
    // real offender), so the walk skips the whole subtree, not just the fixed element itself.
    const fixedUp = new Map<Element, boolean>()
    const insideFixed = (el: Element): boolean => {
      const chain: Element[] = []
      let cur: Element | null = el
      let found = false
      while (cur && cur !== document.body) {
        const known = fixedUp.get(cur)
        if (known !== undefined) { found = known; break }
        chain.push(cur)
        if (getComputedStyle(cur).position === 'fixed') { found = true; break }
        cur = cur.parentElement
      }
      for (const c of chain) fixedUp.set(c, found)
      return found
    }
    let best: { el: Element; right: number; width: number } | null = null
    for (const el of Array.from(document.body.querySelectorAll('*'))) {
      const r = el.getBoundingClientRect()
      if (r.width < 2 || r.height < 2) continue   // an sr-only control (1 × 1) is never "the widest"
      const reach = Math.max(r.right, r.left + el.scrollWidth)
      if (reach <= vw + 0.5) continue
      if (insideFixed(el) || insideSideScroller(el)) continue
      if (!best || reach > best.right + 0.5 || (Math.abs(reach - best.right) <= 0.5 && r.width < best.width)) {
        best = { el, right: reach, width: r.width }
      }
    }
    if (best) widest = `${describe(best.el)} → right edge ${Math.round(best.right)}px of ${vw}`
  }

  // 2. Text fields under 16 px.
  const NOT_TEXT = ['checkbox', 'radio', 'hidden', 'file', 'range', 'color', 'submit', 'button', 'reset', 'image']
  const fields = within('input, select, textarea').filter((el) => {
    if (el instanceof HTMLInputElement && NOT_TEXT.includes(el.type)) return false
    return visible(el)
  })
  const small = fields.filter((el) => parseFloat(getComputedStyle(el).fontSize) < 16)

  // 3. Tap targets under 44 × 44.
  const targets = new Set<Element>()
  for (const el of within(
    'a[href], button, [role="button"], select, summary, input[type="checkbox"], input[type="radio"], '
    + 'input[type="file"]')) {
    if (el instanceof HTMLInputElement) {
      const label = el.closest('label') ?? (el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null)
      targets.add(label ?? el)
      continue
    }
    if (el.tagName === 'A' && getComputedStyle(el).display === 'inline') {
      let block = el.parentElement
      while (block && getComputedStyle(block).display.startsWith('inline')) block = block.parentElement
      const own = (el.textContent ?? '').trim().length
      const around = (block?.textContent ?? '').trim().length
      if (around > own + 1) continue
    }
    targets.add(el)
  }
  const tiny = Array.from(targets).filter((el) => {
    if (!visible(el)) return false
    const r = el.getBoundingClientRect()
    return r.width < 44 || r.height < 44
  })

  // 4. Spills — words or a drawn box passing out of the box that holds them (Mobile M8 follow-up).
  const SPILL_SLACK_PX = 1.5   // sub-pixel text metrics; a real spill in this app has been 4 px or more
  const styles = new Map<Element, CSSStyleDeclaration>()
  const style = (el: Element): CSSStyleDeclaration => {
    let s = styles.get(el)
    if (!s) { s = getComputedStyle(el); styles.set(el, s) }
    return s
  }
  // A box a reader SEES: a border, a fill (colour or gradient) or a shadow. Text and drawn boxes are the
  // items judged; an invisible wrapper (an InfoTip's 44 px hit area) is neither.
  const drawn = (el: Element): boolean => {
    const cs = style(el)
    const bg = cs.backgroundColor
    return parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth) > 0
      || (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') || cs.boxShadow !== 'none' || cs.backgroundImage !== 'none'
  }
  const pulledOut = (el: Element): boolean =>
    parseFloat(style(el).marginLeft) < -0.5 || parseFloat(style(el).marginRight) < -0.5
  /** How far [left, right] passes out of the boxes holding it, walking up from `start` (`below` is the item's
   *  own element for a drawn box, null for text). null = within every box, or not judged. */
  const spillOf = (left: number, right: number, below: Element | null, start: Element | null) => {
    let worst = 0
    let into: Element | null = null
    let child = below
    for (let a = start; a && a !== doc; a = a.parentElement) {
      if (child) {
        const pos = style(child).position
        if (pos === 'fixed') return null       // a tab bar, a toast: not in the page's flow
        if (pos === 'absolute') break          // placed, not flowed: a popover, a badge on a corner
        if (pulledOut(child)) break            // full-bleed section / padded hit area: MEANT to pass its parent
      }
      const cs = style(a)
      if (cs.position === 'fixed') return null
      if (cs.overflowX !== 'visible') break    // a side-scroller or clipping box holds it (a framed table)
      if (cs.display !== 'inline' && cs.display !== 'contents') {
        const r = a.getBoundingClientRect()
        if (r.width >= 2) {
          const s = Math.max(right - r.right, r.left - left)
          if (s > worst) { worst = s; into = a }
        }
      }
      child = a
    }
    return worst > SPILL_SLACK_PX && into ? { px: worst, into } : null
  }
  const found: { el: Element; text: string | null; px: number; into: Element }[] = []
  const spilledBoxes = new Set<Element>()
  // A sandbox surface's <main> holds the console shell's own <main>: walk each part of the page once.
  const outer = roots.filter((r) => !roots.some((o) => o !== r && o.contains(r)))
  for (const root of outer) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const p = n.parentElement
      if (!n.nodeValue?.trim() || !p || p.closest('script, style, noscript, svg')) continue
      const cs = style(p)
      if (cs.visibility === 'hidden' || cs.opacity === '0') continue
      const range = document.createRange()
      range.selectNodeContents(n)
      const rects = Array.from(range.getClientRects()).filter((x) => x.width > 0 && x.height > 0)
      if (rects.length === 0) continue
      let s = spillOf(Math.min(...rects.map((x) => x.left)), Math.max(...rects.map((x) => x.right)), null, p)
      if (s) {
        // Measured again on the WORDS alone: a space at the end of a wrapped line (`whitespace-pre-wrap`
        // keeps it) hangs past the box, and is not something anybody sees.
        const ink: DOMRect[] = []
        for (const w of Array.from(n.nodeValue.matchAll(/\S+/g))) {
          range.setStart(n, w.index ?? 0)
          range.setEnd(n, (w.index ?? 0) + w[0].length)
          ink.push(...Array.from(range.getClientRects()).filter((x) => x.width > 0 && x.height > 0))
        }
        s = ink.length ? spillOf(Math.min(...ink.map((x) => x.left)), Math.max(...ink.map((x) => x.right)), null, p) : null
      }
      if (s) found.push({ el: p, text: n.nodeValue.trim(), ...s })
    }
    for (const el of Array.from(root.querySelectorAll('*'))) {
      if (el.closest('svg') || !drawn(el)) continue
      const cs = style(el)
      if (cs.display === 'inline' || cs.display === 'contents' || !visible(el)) continue
      const r = el.getBoundingClientRect()
      const s = spillOf(r.left, r.right, el, el.parentElement)
      if (s) { found.push({ el, text: null, ...s }); spilledBoxes.add(el) }
    }
  }
  // One fault, one count: words inside a box that itself spills are that box's spill.
  const spills = found.filter((f) => {
    for (let a: Element | null = f.text === null ? f.el.parentElement : f.el; a; a = a.parentElement) {
      if (spilledBoxes.has(a)) return false
    }
    return true
  })
  const tag = (el: Element) => describe(el).split(' [')[0]

  return {
    url: location.pathname + location.search,
    lang: doc.lang,
    overflow,
    widest,
    smallInputs: small.length,
    smallInputExamples: small.slice(0, 6).map(describe),
    smallTargets: tiny.length,
    smallTargetExamples: tiny.slice(0, 8).map(describe),
    spills: spills.length,
    spillExamples: spills.slice(0, 8).map((f) => `${f.text === null ? describe(f.el) : `“${f.text.slice(0, 30)}” in ${tag(f.el)}`}`
      + ` → ${Math.round(f.px)}px out of ${tag(f.into)}`),
  }
}

/**
 * Mobile M4b: the student tab bar's two promises, measured in the page AFTER the screenshot (it
 * scrolls). Self-contained like `measurePage`.
 *
 *  - bottomBars — how many bottom bars are drawn at once: the tab bar (`[data-tab-bar]`) and a page's
 *    own bar (`[data-page-bar]`, OR any sticky / fixed bar resting on the foot of the screen, marked or
 *    not — any number of them counting as one). More than 1 means the swap rule
 *    failed: two bars stacked, the page's main action fighting the tabs.
 *  - coveredByBar — scrolled to the very end, how many CSS px of the page's own content (the last
 *    lines, the footer) lie UNDER the fixed tab bar. 0 means the page is padded by the bar's height.
 *    Anything fixed itself (a toast, a sheet) is not page content and is skipped.
 */
export interface BarCheck {
  bottomBars: number
  coveredByBar: number
  covered: string | null
}

export function measureBars(): BarCheck {
  const drawn = (el: Element): boolean => {
    const r = el.getBoundingClientRect()
    const cs = getComputedStyle(el)
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width >= 2 && r.height >= 2
  }
  const tabs = Array.from(document.querySelectorAll('[data-tab-bar]')).filter(drawn)
  const pageBars = Array.from(document.querySelectorAll('[data-page-bar]')).filter(drawn)
  // ANY bar resting on the foot of the screen counts as a page bar, marked or not (M4b review: an
  // UNMARKED page bar is exactly the bug — the tabs would not give way to it). A bar: sticky or fixed,
  // its bottom on the screen's bottom, at least half the screen wide and 20 px to 40 % of it tall (a
  // sheet's full-screen backdrop is not a bar), not inside the tab bar or a dialog.
  const vh = window.innerHeight
  const vw = document.documentElement.clientWidth
  for (const el of Array.from(document.body.querySelectorAll('*'))) {
    if (el.closest('[data-tab-bar], [role="dialog"]') || pageBars.some((b) => b.contains(el) || el.contains(b))) continue
    const pos = getComputedStyle(el).position
    if (pos !== 'sticky' && pos !== 'fixed') continue
    const r = el.getBoundingClientRect()
    if (!drawn(el) || Math.abs(r.bottom - vh) > 2 || r.width < vw / 2 || r.height < 20 || r.height > vh * 0.4) continue
    pageBars.push(el)
  }
  const bottomBars = tabs.length + (pageBars.length > 0 ? 1 : 0)
  if (tabs.length === 0) return { bottomBars, coveredByBar: 0, covered: null }

  window.scrollTo(0, document.documentElement.scrollHeight)
  const top = tabs[0].getBoundingClientRect().top
  const fixedCache = new Map<Element, boolean>()
  const inFixed = (el: Element): boolean => {
    const chain: Element[] = []
    let cur: Element | null = el
    let found = false
    while (cur && cur !== document.body) {
      const known = fixedCache.get(cur)
      if (known !== undefined) { found = known; break }
      chain.push(cur)
      if (getComputedStyle(cur).position === 'fixed') { found = true; break }
      cur = cur.parentElement
    }
    for (const c of chain) fixedCache.set(c, found)
    return found
  }
  let worst = 0
  let covered: string | null = null
  for (const el of Array.from(document.body.querySelectorAll('*'))) {
    if (el.children.length > 0) continue            // leaves only: the words and controls themselves
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2 || r.bottom <= top + 0.5) continue
    if (inFixed(el)) continue
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.opacity === '0') continue
    const over = r.bottom - top
    if (over > worst) {
      worst = over
      covered = `${el.tagName.toLowerCase()} “${(el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)}”`
    }
  }
  return { bottomBars, coveredByBar: Math.round(worst), covered }
}
