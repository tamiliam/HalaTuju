/**
 * @jest-environment jsdom
 *
 * Mobile M3: a course card's save button is a 44 × 44 target (it was 28), named in the student's
 * language (it was always English), says whether it is pressed, and saving never opens the course.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import CourseCard from './CourseCard'
import type { EligibleCourse } from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/hooks/useFieldTaxonomy', () => ({
  useFieldTaxonomy: () => ({ getImageUrl: () => '/x.png', getFieldName: () => 'Engineering' }),
}))

const COURSE = {
  course_id: 'POLY-DIP-019', course_name: 'Diploma Kejuruteraan Mekanikal', level: 'Diploma', field: '',
  field_key: 'mekanikal', source_type: 'poly', merit_cutoff: null, student_merit: null, merit_label: null,
  merit_color: null,
} as EligibleCourse

describe('CourseCard save button', () => {
  it('is 44 × 44, named "save" in the catalogue, not pressed, and saving does not follow the card link', () => {
    const onToggleSave = jest.fn()
    render(<CourseCard course={COURSE} isSaved={false} onToggleSave={onToggleSave} />)
    const button = screen.getByRole('button', { name: 'courseDetail.saveCourse' })
    expect(button.className.split(/\s+/)).toEqual(expect.arrayContaining(['h-11', 'w-11']))
    expect(button.getAttribute('aria-pressed')).toBe('false')
    const click = new MouseEvent('click', { bubbles: true, cancelable: true })
    button.dispatchEvent(click)
    expect(onToggleSave).toHaveBeenCalledWith('POLY-DIP-019')
    expect(click.defaultPrevented).toBe(true)
  })

  it('once saved it reads "remove from saved" and is pressed', () => {
    render(<CourseCard course={COURSE} isSaved onToggleSave={() => {}} />)
    const button = screen.getByRole('button', { name: 'saved.remove' })
    expect(button.getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(button)
  })
})
