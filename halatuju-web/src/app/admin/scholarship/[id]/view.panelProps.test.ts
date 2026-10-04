/**
 * EVERY PROP A COCKPIT PANEL DECLARES, IT READS (TD-273, 2026-10-04).
 *
 * Code health H14 lifted thirteen panels out of `view.tsx`, turning ~180 closure references into
 * explicit props. `tsc` proves every prop a panel USES is declared and passed; nothing proved the
 * reverse. A prop that is declared, passed and no longer read is invisible to `tsc` and to
 * `next lint` (a destructured parameter counts as "used"), and it reads as a dependency the panel
 * does not have. `noUnusedParameters` does not look inside a destructured object either.
 *
 * So this is the small check the entry names: for every exported component in `view/` whose first
 * parameter is a destructured object, each destructured name (the LOCAL name, after a rename;
 * a `...rest` is skipped) must appear in the function body below the signature — not merely in
 * the parameter list or its type annotation.
 *
 * It is a source-shape test on purpose: the claim is structural ("no declared prop is unread"),
 * which a render cannot prove. The parser is bitten on a synthetic component first, and the walk
 * and the prop count are floored, so a signature style it stopped recognising goes red here.
 */
import * as path from 'path'
import { walkFloor, floorCount, readWeb, WEB_ROOT } from '@/test/sourceGuard'

type Finding = { component: string; declared: string[]; unread: string[] }

/** Index of the bracket that closes the one opening at `open` (`(`/`{`), or -1. */
function closing(src: string, open: number): number {
  const pair: Record<string, string> = { '(': ')', '{': '}', '[': ']', '<': '>' }
  const opener = src[open]
  let depth = 0
  for (let i = open; i < src.length; i++) {
    if (src[i] === opener) depth++
    else if (src[i] === pair[opener]) {
      depth--
      if (depth === 0) return i
    }
  }
  return -1
}

/** Split a destructuring body on its top-level commas. */
function topLevel(list: string): string[] {
  const out: string[] = []
  let depth = 0
  let cur = ''
  for (const ch of list) {
    if ('({['.includes(ch)) depth++
    if (')}]'.includes(ch)) depth--
    if (ch === ',' && depth === 0) {
      out.push(cur)
      cur = ''
    } else cur += ch
  }
  out.push(cur)
  return out.map((s) => s.trim()).filter(Boolean)
}

/** The local binding a destructured entry creates: `a` · `a = 1` · `a: b` · `a: b = 1`. */
function localName(entry: string): string | null {
  if (entry.startsWith('...')) return null
  const noDefault = entry.split('=')[0].trim()
  const renamed = noDefault.includes(':') ? noDefault.split(':')[1].trim() : noDefault
  return /^[A-Za-z_$][\w$]*$/.test(renamed) ? renamed : null
}

function scan(src: string): Finding[] {
  const out: Finding[] = []
  const re = /export function ([A-Z]\w*)\s*\(\s*\{/g
  for (const m of src.matchAll(re)) {
    const open = (m.index as number) + m[0].length - 1
    const close = closing(src, open)
    const names = topLevel(src.slice(open + 1, close)).map(localName).filter((n): n is string => !!n)
    // Past the parameter list (the type annotation lives inside it) to the body's own brace.
    const paren = src.lastIndexOf('(', open)
    const paramsEnd = closing(src, paren)
    const bodyOpen = src.indexOf('{', paramsEnd)
    const body = src.slice(bodyOpen, closing(src, bodyOpen) + 1)
    const unread = names.filter((n) => !new RegExp(`(?<![\\w$.])${n.replace('$', '\\$')}(?![\\w$])`).test(body))
    out.push({ component: m[1], declared: names, unread })
  }
  return out
}

describe('the scanner bites (a synthetic panel)', () => {
  const src = [
    'export function Good({ app, t, busy = false, onSave: save }: { app: A; t: T; busy?: boolean; onSave: () => void }) {',
    '  return <div onClick={save}>{t(app.id)}{busy ? 1 : 0}</div>',
    '}',
    'export function Stale({ app, t, setViewerDoc }: {',
    '  app: A',
    '  t: (k: string) => string',
    '  setViewerDoc: (d: D) => void',
    '}) {',
    '  return <div>{t(app.id)}{props.setViewerDocX}</div>',
    '}',
  ].join('\n')

  it('reads renames and defaults, and finds a prop named only in the signature', () => {
    expect(scan(src)).toEqual([
      { component: 'Good', declared: ['app', 't', 'busy', 'save'], unread: [] },
      // `setViewerDoc` is in the parameter list and its type, and in the body only as part of a
      // longer name after a dot — neither is a read.
      { component: 'Stale', declared: ['app', 't', 'setViewerDoc'], unread: ['setViewerDoc'] },
    ])
  })
})

describe('cockpit panels read every prop they declare', () => {
  const dir = path.join(WEB_ROOT, 'src', 'app', 'admin', 'scholarship', '[id]', 'view')
  const files = walkFloor(dir, 13,
    'the thirteen panels H14 lifted out of view.tsx hold their props here; a moved folder would '
    + 'leave this check reading nothing',
    { exts: ['.tsx'] })
  const findings = files.flatMap((f) => scan(readWeb(
    path.relative(WEB_ROOT, f).split(path.sep).join('/'),
    'each panel declares its props in its own signature')).map((x) => ({ ...x, file: path.basename(f) })))
  floorCount(findings, 17, 'panel components with a destructured props object',
    '19 on 2026-10-04 (the panels and their sub-panels); a signature style the scanner stopped matching '
    + 'would empty this and pass for ever')
  floorCount(findings.flatMap((x) => x.declared), 160, 'declared props',
    '183 on 2026-10-04 (about 180 closure references became props at H14); far fewer means the parser lost them')

  it('no panel declares a prop it never reads', () => {
    expect(findings.filter((x) => x.unread.length).map((x) => `${x.file} ${x.component}: ${x.unread.join(', ')}`))
      .toEqual([])
  })
})
