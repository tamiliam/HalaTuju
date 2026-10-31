/**
 * The measurement, run INSIDE the page (`page.evaluate(measurePage, scope)`).
 *
 * ⚠ SELF-CONTAINED ON PURPOSE. Playwright sends this function to the browser as source text, so it
 * may not use anything from outside its own body — no imports, no helpers from this file.
 *
 * The three numbers (docs/mobile-standard.md rules 1, 2 and 3):
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
 *     buttons, `[role=button]`, selects, `summary`, and checkboxes/radios — for those the LABEL is
 *     measured when they have one, because the label is what a thumb hits. EXCLUDED: an inline
 *     link inside running text (display `inline` and its block holds more words than the link),
 *     which the standard excepts. The element's own box is measured; a hit area enlarged with a
 *     pseudo-element would not be seen, so the standard asks for padding instead.
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
}

export function measurePage(scopeSelector: string): Measurement {
  const doc = document.documentElement
  const vw = doc.clientWidth
  const overflow = Math.max(0, Math.round(doc.scrollWidth - vw))
  const scope = document.querySelector(scopeSelector) ?? document.body

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
    let best: { el: Element; right: number; width: number } | null = null
    for (const el of Array.from(document.body.querySelectorAll('*'))) {
      const r = el.getBoundingClientRect()
      if (r.width < 1 || r.height < 1) continue
      const reach = Math.max(r.right, r.left + el.scrollWidth)
      if (reach <= vw + 0.5) continue
      if (getComputedStyle(el).position === 'fixed' || insideSideScroller(el)) continue
      if (!best || reach > best.right + 0.5 || (Math.abs(reach - best.right) <= 0.5 && r.width < best.width)) {
        best = { el, right: reach, width: r.width }
      }
    }
    if (best) widest = `${describe(best.el)} → right edge ${Math.round(best.right)}px of ${vw}`
  }

  // 2. Text fields under 16 px.
  const NOT_TEXT = ['checkbox', 'radio', 'hidden', 'file', 'range', 'color', 'submit', 'button', 'reset', 'image']
  const fields = Array.from(scope.querySelectorAll('input, select, textarea')).filter((el) => {
    if (el instanceof HTMLInputElement && NOT_TEXT.includes(el.type)) return false
    return visible(el)
  })
  const small = fields.filter((el) => parseFloat(getComputedStyle(el).fontSize) < 16)

  // 3. Tap targets under 44 × 44.
  const targets = new Set<Element>()
  for (const el of Array.from(scope.querySelectorAll(
    'a[href], button, [role="button"], select, summary, input[type="checkbox"], input[type="radio"]'))) {
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

  return {
    url: location.pathname + location.search,
    lang: doc.lang,
    overflow,
    widest,
    smallInputs: small.length,
    smallInputExamples: small.slice(0, 6).map(describe),
    smallTargets: tiny.length,
    smallTargetExamples: tiny.slice(0, 8).map(describe),
  }
}
