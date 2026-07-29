#!/usr/bin/env node
/**
 * Rewrite a surface's raw Tailwind colours onto the theme tokens (Layer 1).
 *
 *   node scripts/theme-codemod.js "src/app/sponsor/**" --dry
 *   node scripts/theme-codemod.js src/app/sponsor src/components/sponsors --write
 *
 * It renames the FAMILY and keeps the position: `bg-gray-50` → `bg-ground-50`,
 * `text-green-700` → `text-positive-700`. Because the token values in globals.css are
 * Tailwind's own, a converted surface is pixel-identical in light mode — which is what
 * makes "nothing moved" a checkable claim rather than a hope.
 *
 * ⚠ THIS TOOL IS NOT THE SPRINT. It does the ~88% that is mechanical. The rest — and every
 * line it DID touch — is reviewed by hand and then looked at in a browser in both modes.
 * "The codemod ran" is not evidence of anything.
 *
 * ── Three rules that are easy to get wrong, and are therefore encoded here ──
 *
 * 1. **`text-white` / `border-white` / `ring-white` STAY LITERAL.** 214 uses, nearly all
 *    sitting on a coloured or dark surface: a button label, a badge, a filled chip. They
 *    must NOT invert with the ground, or every primary button in dark mode gets black text.
 *    Only a BACKGROUND white becomes `--ground-0`.
 * 2. **`slate` folds into the same ground ramp as `gray`.** 10 uses against 3,097 — drift,
 *    not a second neutral. Those ten shift very slightly (slate is bluer); that is a
 *    correction, and it is called out here so nobody reads it later as a regression.
 * 3. **Only the four tone families convert.** purple / indigo / orange / teal and friends
 *    are left alone and reported, because a colour outside the four either means something
 *    the vocabulary has not named, or it is a mistake — and both need a human.
 */
const fs = require('fs')
const path = require('path')

const GROUND = ['gray', 'slate']
const TONE = { green: 'positive', emerald: 'positive', blue: 'info', sky: 'info',
               amber: 'caution', yellow: 'caution', red: 'critical', rose: 'critical' }
/** Reported, never converted — see rule 3. */
const UNMAPPED = ['orange', 'lime', 'teal', 'cyan', 'indigo', 'violet', 'purple', 'fuchsia', 'pink']

const PROPS = 'bg|text|border|ring|divide|placeholder|from|to|via|fill|stroke|outline|shadow|accent|decoration|caret'
/** Prefixes Tailwind allows before a utility — `hover:`, `md:`, `group-hover:`, `dark:`… */
const PRE = '(?:[a-z-]+(?:\\[[^\\]]*\\])?:)*'

const numbered = new RegExp(`(${PRE})(${PROPS})-(${[...GROUND, ...Object.keys(TONE)].join('|')})-(\\d{2,3})\\b`, 'g')
const bgWhite = new RegExp(`(${PRE})(bg|from|to|via)-white\\b`, 'g')
const unmapped = new RegExp(`(${PRE})(${PROPS})-(${UNMAPPED.join('|')})-(\\d{2,3})\\b`, 'g')

function convert(src) {
  const notes = []
  let out = src.replace(numbered, (m, pre, prop, fam, stop) => {
    const to = GROUND.includes(fam) ? 'ground' : TONE[fam]
    if (fam === 'slate') notes.push(`slate→ground (hue shifts slightly): ${m}`)
    return `${pre}${prop}-${to}-${stop}`
  })
  // Rule 1: background white becomes the ground's top stop; text/border/ring white does not.
  out = out.replace(bgWhite, (m, pre, prop) => `${pre}${prop}-ground-0`)
  for (const m of src.matchAll(unmapped)) notes.push(`left alone (outside the four tones): ${m[0]}`)
  return { out, notes }
}

function walk(target, acc) {
  const st = fs.statSync(target)
  if (st.isDirectory()) {
    for (const e of fs.readdirSync(target)) {
      if (e === 'node_modules' || e === '__tests__') continue
      walk(path.join(target, e), acc)
    }
  } else if (/\.(tsx?|jsx?)$/.test(target) && !/\.test\.[jt]sx?$/.test(target)) {
    acc.push(target)
  }
  return acc
}

function main() {
  const args = process.argv.slice(2)
  const write = args.includes('--write')
  const targets = args.filter((a) => !a.startsWith('--'))
  if (!targets.length) {
    console.error('usage: theme-codemod.js <path…> [--write]   (default is a dry run)')
    process.exit(2)
  }
  const files = targets.flatMap((t) => walk(t, []))
  let changed = 0, edits = 0
  const allNotes = []
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8')
    const { out, notes } = convert(src)
    if (out !== src) {
      changed++
      edits += out.split('-ground-').length + out.split('-positive-').length
             + out.split('-info-').length + out.split('-caution-').length
             + out.split('-critical-').length - 5
      if (write) fs.writeFileSync(f, out)
    }
    notes.forEach((n) => allNotes.push(`  ${f}: ${n}`))
  }
  console.log(`${write ? 'rewrote' : 'would rewrite'} ${changed} of ${files.length} files (~${edits} utilities)`)
  if (allNotes.length) {
    console.log(`\n${allNotes.length} thing(s) a human has to look at:`)
    allNotes.slice(0, 40).forEach((n) => console.log(n))
    if (allNotes.length > 40) console.log(`  … and ${allNotes.length - 40} more`)
  }
  if (!write) console.log('\ndry run — pass --write to apply')
}

main()
module.exports = { convert }
