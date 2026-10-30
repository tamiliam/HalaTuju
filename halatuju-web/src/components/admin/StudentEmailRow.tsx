'use client'

import Link from 'next/link'
import { formatDate } from '@/lib/formatDate'
import type { StudentEmailRow as Row, StudentEmailTemplate } from '@/lib/admin-api'
import { Toggle } from '@/components/sources/shared'
import StudentEmailLanguages, { type EditorRow } from './StudentEmailLanguages'

const PREFIX = 'admin.orgSettings.studentComms'
type T = (key: string, params?: Record<string, string>) => string

/** One chip per language she may be written in; the worded ones say whose wording each is. */
function LanguageChips({ row, templates, t }: { row: Row; templates: StudentEmailTemplate[]; t: T }) {
  if (row.languages !== 'en_ms_ta') {
    return (
      <span className="rounded-full bg-ground-100 px-2 py-0.5 text-xs text-ground-600"
        title={t(`${PREFIX}.languages.${row.languages}`)}>
        {t(`${PREFIX}.chip.${row.languages}`)}
      </span>
    )
  }
  return (
    <span className="flex gap-1" data-testid={`student-email-chips-${row.key}`}>
      {(['en', 'ms', 'ta'] as const).map((lang) => {
        const own = templates.some((x) => x.language === lang && x.customised)
        return (
          <span key={lang} title={`${t(`${PREFIX}.language.${lang}`)} — ${t(own ? `${PREFIX}.customised` : `${PREFIX}.default`)}`}
            data-customised={own ? 'true' : 'false'}
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${own
              ? 'bg-info-100 text-info-700' : 'border border-ground-200 text-ground-500'}`}>
            {t(`${PREFIX}.chip.${lang}`)}
          </span>
        )
      })}
    </span>
  )
}

/** A padlock: this email always goes, and the line beside it says why. */
function Lock({ label }: { label: string }) {
  return (
    <span role="img" aria-label={label} className="inline-flex h-6 w-11 items-center justify-center text-ground-400">
      <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
        <path fillRule="evenodd" d="M10 2a4 4 0 00-4 4v2H5a1 1 0 00-1 1v8a1 1 0 001 1h10a1 1 0 001-1V9a1 1 0 00-1-1h-1V6a4 4 0 00-4-4zm2 6V6a2 2 0 10-4 0v2h4z" clipRule="evenodd" />
      </svg>
    </span>
  )
}

/**
 * One student email on the Student communications page (S6a): switch or lock, name, when it is sent,
 * the lock's reason or the platform's hold, last sent, language chips, and the action — Edit wording
 * (organisation-worded), Show wording (a plain per-language dict), or a link to the screen that owns it.
 */
export default function StudentEmailRow({ row, templates, open, onOpen, busy, onToggle, onSave, onReset, t }: {
  row: Row
  templates: StudentEmailTemplate[]
  open: boolean
  onOpen: () => void
  busy: string | null
  onToggle: () => void
  onSave: (key: string, patch: { subject: string; body: string }) => Promise<EditorRow>
  onReset: (tpl: StudentEmailTemplate) => void
  t: T
}) {
  const name = t(`${PREFIX}.kind.${row.key}`)
  const hasWording = Object.keys(row.wording).length > 0
  return (
    <li className="px-4 py-4 sm:px-5" data-testid={`student-email-${row.key}`}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="pt-0.5 shrink-0">
          {row.switchable
            ? <Toggle on={row.enabled} disabled={busy === row.key} label={name} onClick={onToggle} />
            : <Lock label={t(`${PREFIX}.locked`)} />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ground-900">{name}</p>
          <p className="mt-0.5 text-sm text-ground-500">{t(`${PREFIX}.when.${row.key}`)}</p>
          {row.lock && <p className="mt-1 text-sm text-ground-600">{t(`${PREFIX}.lock.${row.lock}`)}</p>}
          {!row.platform_on && (
            <p className="mt-1 text-sm text-caution-700" data-testid={`student-email-held-${row.key}`}>
              {t(`${PREFIX}.heldByPlatform`)}
            </p>
          )}
          <p className="mt-1 text-xs text-ground-400">
            {!row.tracked
              ? t(`${PREFIX}.notTracked`)
              : row.last_sent_at
                ? t(`${PREFIX}.lastSent`, { date: formatDate(row.last_sent_at) })
                : t(`${PREFIX}.neverSent`)}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3">
          <LanguageChips row={row} templates={templates} t={t} />
          {row.managed_on === 'sources' ? (
            <Link href="/admin/sources" className="text-sm font-medium text-primary-600 hover:underline">
              {t(`${PREFIX}.manageOnSources`)}
            </Link>
          ) : row.editable || hasWording ? (
            <button type="button" onClick={onOpen}
              className="text-sm font-medium text-primary-600 hover:text-primary-700 hover:underline">
              {t(open ? 'common.cancel' : row.editable ? `${PREFIX}.edit` : `${PREFIX}.showWording`)}
            </button>
          ) : (
            <span className="text-xs text-ground-400">{t(`${PREFIX}.builtInCode`)}</span>
          )}
        </div>
      </div>
      {open && (
        <div className="mt-4">
          <StudentEmailLanguages row={row} templates={templates} busy={busy}
            onSave={onSave} onReset={onReset} onDone={onOpen} t={t} />
        </div>
      )}
    </li>
  )
}
