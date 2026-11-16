/**
 * "New note" (request #73, 2026-11-16): the mark by a student's name on the applications table, on a phone and
 * on a desktop, when THIS person has a note from the other side of the org admin and reviewer notes that they
 * have not opened yet. A dot plus words (never colour alone). The flag is the list row's SERVED `new_note`; the
 * server clears it when the person opens the student's notes, so the next read of the list drops the mark.
 */
import { PHONE_PILL_SM } from '@/lib/phonePill'

export default function NewNoteMark({ label }: { label: string }) {
  return (
    <span data-new-note
      className={`ml-2 inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-primary-50 px-2 py-0.5 align-middle text-xs font-semibold text-primary-700 ${PHONE_PILL_SM}`}>
      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary-600" />
      {label}
    </span>
  )
}
