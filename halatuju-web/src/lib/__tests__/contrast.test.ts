/**
 * Layer 1 A2 — the browser's copy of the contrast check.
 *
 * ⚠ THE POINT OF THIS FILE IS AGREEMENT WITH THE SERVER, not correctness on its own. The gate is
 * `apps/courses/contrast.py`; this module only tells the person choosing a colour what will happen
 * before they press Save. If the two disagree, the screen says one thing and the save does another,
 * which is worse than having no preview at all.
 *
 * So the fixtures below are the SAME ones asserted in `apps/courses/tests/test_contrast.py`:
 * the measured pass/refuse spread, and the pair table's shape. A drift fails on the side that
 * drifted.
 */
import {
  AA_NON_TEXT,
  AA_TEXT,
  PAIRS,
  checkColour,
  contrastRatio,
  isHexColour,
  isReadable,
} from '@/lib/contrast'

// Measured 2026-09-01, after the 52 filled controls moved off `bg-primary-500`.
// Identical list to PASSES / REFUSES in test_contrast.py.
const PASSES = ['#137fec', '#1e3a8a', '#0f766e', '#166534', '#7f1d1d', '#a21caf',
  '#4338ca', '#010066', '#dc2626', '#ea580c', '#db2777', '#475569', '#111827']
const REFUSES = ['#d97706', '#0ea5e9', '#65a30d', '#6ee7b7', '#facc15']

describe('the maths', () => {
  it('gives the two ratios everybody knows', () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 4)
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1, 4)
  })

  it('is symmetric', () => {
    expect(contrastRatio([19, 127, 236], [255, 255, 255]))
      .toBe(contrastRatio([255, 255, 255], [19, 127, 236]))
  })

  it('matches the hand-checked middle value the backend also pins', () => {
    // White on the platform brand's 600 stop.
    const filled = checkColour('#137fec').find((c) => c.key === 'filled_button')!
    expect(filled.ratio).toBeCloseTo(5.24, 2)
  })
})

describe('the gate agrees with the server', () => {
  it('lets the platform colour through — the calibration canary', () => {
    // A check that refused the colour the product itself ships would be reporting a defect in the
    // PRODUCT, not in anybody's choice. That is exactly how A2 found the 52 mis-shaded buttons.
    expect(isReadable('#137fec')).toBe(true)
  })

  it('reproduces the measured spread', () => {
    PASSES.forEach((hex) => expect(isReadable(hex)).toBe(true))
    REFUSES.forEach((hex) => expect(isReadable(hex)).toBe(false))
  })

  it('reports every pair, not only the failures', () => {
    // The screen shows a list so a tenant can see how close they were and which way to move.
    const gold = checkColour('#d97706')
    expect(gold).toHaveLength(PAIRS.length)
    expect(gold.some((c) => c.passes)).toBe(true)
    expect(gold.some((c) => !c.passes)).toBe(true)
  })

  it('names a pale colour as failing the text pairs, not merely one', () => {
    const failing = checkColour('#facc15').filter((c) => !c.passes).map((c) => c.key)
    expect(failing).toEqual(expect.arrayContaining(['filled_button', 'link_on_card', 'panel_text']))
  })
})

describe('the pair table', () => {
  it('holds shapes to 3, and everything carrying words to 4.5', () => {
    const shapes = PAIRS.filter((p) => p.min === AA_NON_TEXT)
    expect(shapes.map((p) => p.key)).toEqual(['ui_shape'])
    PAIRS.filter((p) => p.key !== 'ui_shape').forEach((p) => expect(p.min).toBe(AA_TEXT))
  })

  it('uses the SERVER keys, so a refusal maps onto a row already on screen', () => {
    // Renaming one side only would leave the screen unable to explain its own 400.
    expect(PAIRS.map((p) => p.key).sort()).toEqual([
      'filled_button', 'filled_button_dark', 'link_on_card', 'link_on_page', 'panel_text', 'ui_shape',
    ])
  })
})

describe('isHexColour', () => {
  it('accepts a 6-digit hex and nothing else', () => {
    expect(isHexColour('#a21caf')).toBe(true)
    expect(isHexColour('  #A21CAF  ')).toBe(true)
    for (const bad of ['a21caf', '#a21ca', '#a21caff', 'blue', '', '#gggggg', 'rgb(1,2,3)']) {
      expect(isHexColour(bad)).toBe(false)
    }
  })
})
