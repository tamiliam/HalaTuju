/**
 * "Returned by QC" (request #86, 2026-11-27): the mark on a case QC sent back to its interviewer, on the My-open
 * table and by the student's name on the admin list. A dot plus words (never colour alone), the same look as
 * `NewNoteMark`. The flag is the row's SERVED `returned_by_qc` (an open reopen taken from the QC stage); the
 * browser never works it out. Absent or false draws nothing.
 */
import { PHONE_PILL_SM } from '@/lib/phonePill'

export default function ReturnedByQcMark({ show, label }: { show?: boolean | null; label: string }) {
  if (!show) return null
  return (
    <span data-returned-by-qc
      className={`ml-2 inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-caution-100 px-2 py-0.5 align-middle text-xs font-semibold text-caution-700 ${PHONE_PILL_SM}`}>
      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-caution-700" />
      {label}
    </span>
  )
}
