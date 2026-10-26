'use client'

/**
 * The higher-results card's furniture (`./HigherResults`), fetched when a card asks for it instead of
 * riding in `/scholarship/application`'s first-load JS (third results route S3a/S3b, 2026-10-26).
 *
 * WHY: that route sits at its bundle budget, and only a student whose card asks for STPM /
 * Matriculation / Asasi / Diploma results ever draws these pieces. The budget is never raised; the
 * weight is paid for here. ⚠ The import is owned here, not by `next/dynamic` — the
 * `LazyAliranPicker` reason: a failed chunk draws nothing in place instead of throwing the page away.
 * The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'

import type { AcademicCheck, ApplicantDocument, HigherCheck } from '@/lib/api'

type Mod = typeof import('./HigherResults')

let cached: Mod | null = null

function useHigherModule(): Mod | null {
  const [mod, setMod] = useState<Mod | null>(cached)
  useEffect(() => {
    if (cached) return
    let live = true
    import('./HigherResults')
      .then((m) => { cached = m; if (live) setMod(m) })
      .catch(() => { /* a failed chunk draws nothing; the card still uploads */ })
    return () => { live = false }
  }, [])
  return mod
}

export function LazyKindLine({ kind, spmOnly }: { kind: string; spmOnly?: boolean }) {
  const m = useHigherModule()
  return m ? <m.KindLine kind={kind} spmOnly={spmOnly} /> : null
}

export function LazyHigherDetails({ doc, chk, token, onChanged }: {
  doc: ApplicantDocument; chk: HigherCheck; token: string | null; onChanged?: () => void
}) {
  const m = useHigherModule()
  if (!m) return null
  return (
    <>
      <m.HigherChecklist chk={chk} />
      <m.HigherNote doc={doc} chk={chk} token={token} onChanged={onChanged} />
    </>
  )
}

/** S4 (#43, D15): a higher result in the SPM card — the note, and "Move it to … results". */
export function LazySlipHigherNote({ doc, chk, token, onChanged }: {
  doc: ApplicantDocument; chk: AcademicCheck; token: string | null; onChanged?: () => void
}) {
  const m = useHigherModule()
  return m ? <m.SlipHigherNote doc={doc} chk={chk} token={token} onChanged={onChanged} /> : null
}
