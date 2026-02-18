/**
 * i18n validation script
 * Run: node scripts/check-i18n.js
 *
 * Checks:
 * 1. All locale JSON files parse correctly
 * 2. All locales have identical key structures (no missing translations)
 * 3. No empty translation values
 */

const fs = require('fs')
const path = require('path')

const MESSAGES_DIR = path.join(__dirname, '..', 'src', 'messages')
const LOCALES = ['en', 'ms', 'ta']

let errors = 0
let warnings = 0

// --- Test 1: Parse all JSON files ---
console.log('Test 1: JSON parsing')
const messages = {}
for (const locale of LOCALES) {
  const filePath = path.join(MESSAGES_DIR, `${locale}.json`)
  try {
    const raw = fs.readFileSync(filePath, 'utf-8')
    messages[locale] = JSON.parse(raw)
    console.log(`  PASS  ${locale}.json parses correctly`)
  } catch (err) {
    console.log(`  FAIL  ${locale}.json: ${err.message}`)
    errors++
  }
}

if (errors > 0) {
  console.log(`\nFailed: ${errors} JSON files could not be parsed`)
  process.exit(1)
}

// --- Helper: extract all dot-notation keys ---
function getKeys(obj, prefix = '') {
  const keys = []
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (typeof value === 'object' && value !== null) {
      keys.push(...getKeys(value, fullKey))
    } else {
      keys.push(fullKey)
    }
  }
  return keys.sort()
}

// --- Test 2: Key completeness ---
console.log('\nTest 2: Key completeness across locales')
const keySets = {}
for (const locale of LOCALES) {
  keySets[locale] = new Set(getKeys(messages[locale]))
}

const referenceLocale = 'en'
const referenceKeys = keySets[referenceLocale]
let keyErrors = 0

for (const locale of LOCALES) {
  if (locale === referenceLocale) continue

  // Keys in reference but missing from this locale
  const missing = [...referenceKeys].filter(k => !keySets[locale].has(k))
  // Keys in this locale but not in reference
  const extra = [...keySets[locale]].filter(k => !referenceKeys.has(k))

  if (missing.length === 0 && extra.length === 0) {
    console.log(`  PASS  ${locale}.json has all ${referenceKeys.size} keys`)
  } else {
    if (missing.length > 0) {
      console.log(`  FAIL  ${locale}.json missing ${missing.length} keys:`)
      missing.forEach(k => console.log(`        - ${k}`))
      keyErrors += missing.length
    }
    if (extra.length > 0) {
      console.log(`  WARN  ${locale}.json has ${extra.length} extra keys:`)
      extra.forEach(k => console.log(`        + ${k}`))
      warnings += extra.length
    }
  }
}
errors += keyErrors

// --- Test 3: No empty values ---
console.log('\nTest 3: No empty translation values')
for (const locale of LOCALES) {
  const keys = getKeys(messages[locale])
  const emptyKeys = keys.filter(k => {
    const parts = k.split('.')
    let val = messages[locale]
    for (const p of parts) val = val[p]
    return typeof val === 'string' && val.trim() === ''
  })

  if (emptyKeys.length === 0) {
    console.log(`  PASS  ${locale}.json has no empty values`)
  } else {
    console.log(`  FAIL  ${locale}.json has ${emptyKeys.length} empty values:`)
    emptyKeys.forEach(k => console.log(`        - ${k}`))
    errors += emptyKeys.length
  }
}

// --- Summary ---
console.log('\n' + '='.repeat(50))
if (errors === 0) {
  console.log(`ALL PASSED (${warnings} warnings)`)
  console.log(`Total keys per locale: ${referenceKeys.size}`)
  process.exit(0)
} else {
  console.log(`FAILED: ${errors} errors, ${warnings} warnings`)
  process.exit(1)
}
