'use client'

import Link from 'next/link'
import { formatDate } from '@/lib/formatDate'
import type { WorkRow } from '@/lib/admin-api/development'

const K = 'admin.scholars.growth'
const LINK = 'inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:underline'

type T = (k: string, vars?: Record<string, string>) => string

/**
 * One scholar's development modules and their work — the scholar file's Growth tab (staff) and the mentor's
 * My students page share it (student maintenance S10). Read-only: lessons read x of y, the task and what they
 * sent, the review, "Late". ``openFile`` opens an uploaded task (staff: the Progress page's file door; the mentor:
 * the short link already on the row). ``progressLinks`` adds a link to the module's Progress page (staff only).
 */
export default function GrowthWork({ rows, t, openFile, progressLinks }: {
  rows: WorkRow[]; t: T; openFile?: (row: WorkRow) => void; progressLinks?: boolean
}) {
  if (rows.length === 0) return <p className="text-sm text-ground-600" data-testid="growth-none">{t(`${K}.none`)}</p>
  return (
    <ul className="flex flex-col divide-y divide-ground-100" data-testid="growth-work">
      {rows.map((r) => {
        const state = r.done ? 'done' : r.read > 0 || r.task_sent_at ? 'inProgress' : 'notStarted'
        return (
          <li key={r.id} className="flex flex-col gap-1 py-3" data-testid={`growth-row-${r.id}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <strong className="break-words text-sm text-ground-900">{r.title}</strong>
              <span className="flex flex-wrap gap-2 text-xs">
                <span className={state === 'done' ? 'font-semibold text-positive-700' : 'text-ground-600'}>
                  {t(`${K}.${state}`)}
                </span>
                {r.late && <span className="font-semibold text-critical-700" data-testid={`growth-late-${r.id}`}>{t(`${K}.late`)}</span>}
              </span>
            </div>
            <p className="text-xs text-ground-600">
              {[t(`${K}.readOf`, { read: String(r.read), count: String(r.lessons) }),
                r.task_kind === 'none' ? t(`${K}.noTask`)
                  : r.task_sent_at ? t(`${K}.sentOn`, { date: formatDate(r.task_sent_at) }) : t(`${K}.notSent`),
                r.reviewed_at ? t(`${K}.reviewed`, { date: formatDate(r.reviewed_at) }) : '']
                .filter(Boolean).join(' · ')}
            </p>
            {r.task_text && (
              <p className="whitespace-pre-line break-words text-sm text-ground-800">
                <span className="text-xs text-ground-600">{t(`${K}.reflection`)}: </span>{r.task_text}
              </p>
            )}
            {r.task_file && openFile && (
              <button type="button" onClick={() => openFile(r)} className={`${LINK} self-start`}
                data-testid={`growth-file-${r.id}`}>{t(`${K}.file`, { name: r.task_file.name })}</button>
            )}
            {r.review_comment && (
              <p className="whitespace-pre-line break-words text-xs text-ground-700">{t(`${K}.comment`, { comment: r.review_comment })}</p>
            )}
            {progressLinks && (
              <Link href={`/admin/programme/development/${r.id}`} className={`${LINK} self-start`}>{t(`${K}.progress`)}</Link>
            )}
          </li>
        )
      })}
    </ul>
  )
}
