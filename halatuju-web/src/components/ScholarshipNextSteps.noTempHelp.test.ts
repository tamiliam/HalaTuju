/**
 * TD-066 (owner ruling 2026-11-05: "Remove the box") — the TEMP tech-support help box on the student
 * application page showed a personal mobile number. It is gone; this keeps it from coming back.
 *
 * A static guard (the component is too wide to render for one absence): neither the component source
 * nor any message file may carry the number or the box's message key.
 */
import fs from 'fs'
import path from 'path'

const read = (...p: string[]) => fs.readFileSync(path.join(__dirname, ...p), 'utf8')

const NUMBER = /337[\s-]?5709/

it('the component no longer renders a tech-support box', () => {
  const src = read('ScholarshipNextSteps.tsx')
  expect(src).not.toMatch(/techSupport/)
  expect(src).not.toMatch(/renderTechSupport/)
  expect(src).not.toMatch(NUMBER)
})

it.each(['en', 'ms', 'ta'])('%s messages carry neither the box key nor the number', (loc) => {
  const raw = read('..', 'messages', `${loc}.json`)
  expect(raw).not.toMatch(NUMBER)
  const nextSteps = JSON.parse(raw).scholarship.nextSteps
  expect(nextSteps).not.toHaveProperty('techSupport')
})
