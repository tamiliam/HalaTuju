/**
 * The source reader behind the Mobile Standard's static guards (Mobile M0, 2026-10-31).
 *
 * `src/lib/__tests__/mobileStandard.test.ts` counts the places the code breaks a rule of
 * `docs/mobile-standard.md` and holds each count to a floor that may only go down. This file is the
 * part that READS the code: it finds JSX opening tags, pulls the class strings off them and resolves
 * a shared class constant to its text. It is kept apart from the test so the rules there read as
 * rules, and so the reader's limits are written down in one place:
 *
 *   - It reads SOURCE TEXT, not a parsed tree. A tag is found by its name, and its end by walking
 *     braces and quotes. That is enough for how this repo writes JSX; it is not a TypeScript parser.
 *   - It sees native tags only (`<input>`, `<button>`, `<a>`, `<Link>`). A wrapper component that
 *     renders an `<input>` inside is judged where its `<input>` is written, not where it is used.
 *   - A class string is every string literal inside `className=`, plus the text of any identifier
 *     there that names a `const` holding a string — in the same file, or imported by name from
 *     another scanned file. A class built at run time from props, or a constant re-exported under
 *     another name, is NOT followed. A reader that cannot see a class says nothing about it.
 *   - Comments are blanked before any rule looks (newlines kept, so line numbers stay true). A
 *     guard that matched its own explanation would be deleted inside a month.
 *
 * The browser check (`npm run mobile-check`) measures what this cannot: inherited font sizes,
 * computed tap sizes, real overflow. The two are meant to be read together.
 */
import * as fs from 'fs'
import * as path from 'path'
import { WEB_ROOT } from './sourceGuard'

/** One scanned file: its path from `halatuju-web/`, the raw text and the comment-blanked text. */
export interface Scanned {
  rel: string
  raw: string
  code: string
}

/** One finding, already formatted for a failure message: `path:line  snippet`. */
export type Offender = string

/**
 * Comments replaced by spaces, everything else kept, newlines kept. Strings and template literals
 * are respected, so a `//` inside a URL string is not a comment. ⚠ A regex literal holding a quote
 * can still confuse it; this repo's `.tsx` files have none that matter, and the worst case is a
 * comment left in place, never code removed.
 */
export function blankComments(src: string): string {
  const out = src.split('')
  // A stack of contexts: code (with its brace depth, so `${…}` knows where it closes) or a template.
  const stack: Array<{ kind: 'code' | 'tpl'; depth: number }> = [{ kind: 'code', depth: 0 }]
  let i = 0
  const n = src.length
  const blank = (from: number, to: number) => {
    for (let k = from; k < to; k++) if (out[k] !== '\n') out[k] = ' '
  }
  while (i < n) {
    const top = stack[stack.length - 1]
    const c = src[i]
    if (top.kind === 'tpl') {
      if (c === '\\') { i += 2; continue }
      if (c === '`') { stack.pop(); i++; continue }
      if (c === '$' && src[i + 1] === '{') { stack.push({ kind: 'code', depth: 0 }); i += 2; continue }
      i++
      continue
    }
    if (c === '"' || c === "'") {
      let j = i + 1
      while (j < n && src[j] !== c && src[j] !== '\n') j += src[j] === '\\' ? 2 : 1
      i = j + 1
      continue
    }
    if (c === '`') { stack.push({ kind: 'tpl', depth: 0 }); i++; continue }
    if (c === '/' && src[i + 1] === '*') {
      const j = src.indexOf('*/', i + 2)
      const end = j === -1 ? n : j + 2
      blank(i, end)
      i = end
      continue
    }
    if (c === '/' && src[i + 1] === '/') {
      const j = src.indexOf('\n', i)
      const end = j === -1 ? n : j
      blank(i, end)
      i = end
      continue
    }
    if (c === '{') top.depth++
    if (c === '}') {
      if (top.depth === 0 && stack.length > 1) { stack.pop(); i++; continue }
      top.depth--
    }
    i++
  }
  return out.join('')
}

/** Every file given, read once, as `Scanned`. */
export function scanFiles(files: string[]): Scanned[] {
  return files.map((full) => {
    const raw = fs.readFileSync(full, 'utf8').replace(/\r\n?/g, '\n')
    return { rel: path.relative(WEB_ROOT, full).split(path.sep).join('/'), raw, code: blankComments(raw) }
  })
}

/** `path:line  first part of the snippet`, so a failure names the exact place. */
export function where(file: Scanned, index: number, snippet: string): Offender {
  const line = file.code.slice(0, index).split('\n').length
  return `${file.rel}:${line}  ${snippet.replace(/\s+/g, ' ').trim().slice(0, 110)}`
}

/** A JSX opening tag: its name, the attribute text, where it starts and where its `>` is. */
export interface OpenTag {
  name: string
  attrs: string
  start: number
  end: number
  selfClosing: boolean
}

/**
 * Every opening tag called `name` (exactly — `<input` does not match `<inputs`). The end is the
 * first `>` outside braces and quotes, so `onClick={() => x}` does not end the tag early.
 */
export function openTags(code: string, name: string): OpenTag[] {
  const out: OpenTag[] = []
  for (const m of Array.from(code.matchAll(new RegExp(`<${name}(?=[\\s/>])`, 'g')))) {
    const from = (m.index ?? 0) + m[0].length
    let i = from
    let depth = 0
    let quote: string | null = null
    while (i < code.length) {
      const c = code[i]
      if (quote) {
        if (c === '\\') { i += 2; continue }
        if (c === quote) quote = null
      } else if (c === '"' || c === "'" || c === '`') {
        quote = c
      } else if (c === '{') {
        depth++
      } else if (c === '}') {
        depth--
      } else if (c === '>' && depth === 0) {
        break
      }
      i++
    }
    const attrs = code.slice(from, i)
    out.push({ name, attrs, start: m.index ?? 0, end: i, selfClosing: /\/\s*$/.test(attrs) })
  }
  return out
}

/**
 * The raw value of attribute `name` in a tag's attribute text: the quoted text for `a="…"`, the
 * expression for `a={…}` (balanced), or null when the attribute is absent.
 */
export function attr(attrs: string, name: string): { literal: string } | { expr: string } | null {
  const m = attrs.match(new RegExp(`(?:^|\\s)${name}=`))
  if (!m) return null
  let i = (m.index ?? 0) + m[0].length
  const open = attrs[i]
  if (open === '"' || open === "'") {
    const close = attrs.indexOf(open, i + 1)
    return { literal: attrs.slice(i + 1, close === -1 ? attrs.length : close) }
  }
  if (open !== '{') return null
  let depth = 0
  const from = i
  for (; i < attrs.length; i++) {
    if (attrs[i] === '{') depth++
    if (attrs[i] === '}') { depth--; if (depth === 0) break }
  }
  return { expr: attrs.slice(from + 1, i) }
}

const LITERAL = /'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g

/** The text of every string literal (quotes and template text) inside an expression. */
export function literalsIn(expr: string): string[] {
  const out: string[] = []
  for (const m of Array.from(expr.matchAll(LITERAL))) {
    const text = m[1] ?? m[2] ?? m[3] ?? ''
    // A template's `${…}` holes may hold more literals (`${on ? 'a' : 'b'}`): read them too.
    out.push(text.replace(/\$\{[^}]*\}/g, ' '))
    for (const hole of text.match(/\$\{[^}]*\}/g) ?? []) out.push(...literalsIn(hole))
  }
  return out
}

/**
 * `const NAME = '…'` (or `"…"`, a template, or literals joined with `+`) in a file, as name → text.
 * The class constants this repo shares (`inputCls`, `INPUT`, …) are all written that way.
 */
export function stringConsts(code: string): Record<string, string> {
  const out: Record<string, string> = {}
  const re = /\bconst\s+([A-Za-z_$][\w$]*)\s*(?::\s*string\s*)?=\s*((?:(?:'[^'\n]*'|"[^"\n]*"|`[^`]*`)\s*\+?\s*)+)/g
  for (const m of Array.from(code.matchAll(re))) out[m[1]] = literalsIn(m[2]).join(' ')
  return out
}

/** The named imports of a file, as local name → the scanned file (`rel`) it comes from. */
export function namedImports(file: Scanned, known: Set<string>): Record<string, string> {
  const out: Record<string, string> = {}
  const re = /import\s*(?:type\s+)?\{([^}]*)\}\s*from\s*'([^']+)'/g
  for (const m of Array.from(file.code.matchAll(re))) {
    const spec = m[2]
    let base: string | null = null
    if (spec.startsWith('@/')) base = `src/${spec.slice(2)}`
    else if (spec.startsWith('.')) base = path.posix.join(path.posix.dirname(file.rel), spec)
    if (!base) continue
    const target = [`${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`]
      .find((c) => known.has(c))
    if (!target) continue
    for (const part of m[1].split(',')) {
      const [orig, alias] = part.replace(/\btype\s+/, '').split(/\s+as\s+/).map((s) => s.trim())
      if (orig) out[alias || orig] = target
    }
  }
  return out
}

/** Resolves an identifier used in `className={…}` to the text of the constant it names. */
export type ConstResolver = (file: Scanned, name: string) => string | undefined

/** Builds a resolver over every scanned file: a local `const` first, then a named import. */
export function constResolver(files: Scanned[]): ConstResolver {
  const consts: Record<string, Record<string, string>> = {}
  for (const f of files) consts[f.rel] = stringConsts(f.code)
  const known = new Set(files.map((f) => f.rel))
  const imports: Record<string, Record<string, string>> = {}
  return (file, name) => {
    const local = consts[file.rel]?.[name]
    if (local !== undefined) return local
    imports[file.rel] = imports[file.rel] ?? namedImports(file, known)
    const from = imports[file.rel][name]
    return from ? consts[from]?.[name] : undefined
  }
}

/** The whole class text of a tag, as far as the reader can see it (see the file header). */
export function classText(file: Scanned, tag: OpenTag, resolve: ConstResolver): string {
  const v = attr(tag.attrs, 'className')
  if (!v) return ''
  if ('literal' in v) return v.literal
  const parts = literalsIn(v.expr)
  // Identifiers OUTSIDE string literals: a shared constant like `inputCls` or `INPUT`.
  const bare = v.expr.replace(/'[^'\n]*'|"[^"\n]*"|`[^`]*`/g, ' ')
  for (const id of bare.match(/(?<![.\w$])[A-Za-z_$][\w$]*/g) ?? []) {
    const text = resolve(file, id)
    if (text !== undefined) parts.push(text)
  }
  return parts.join(' ')
}

/** The class tokens of a class text, split on whitespace. */
export const tokens = (text: string): string[] => text.split(/\s+/).filter(Boolean)
