'use client'

/**
 * THE COCKPIT'S QUERIES, DOCUMENT REQUESTS, REFEREES AND VISION RE-RUN (audit A3.3 — moved out of
 * `view.tsx`, code unchanged): everything an officer asks of the student or the document reader.
 */
import { useState } from 'react'
import {
  raiseResolutionItem, actionResolutionItem, addReferee, deleteReferee, reRunVision,
} from '@/lib/admin-api'
import { isValidPhone } from '@/lib/scholarship'
import { docTypeToRequestFact } from '@/lib/docCategory'
import { EMPTY_REFEREE, resolveReq } from './shared'
import { requestRefusalText } from './OutstandingPanel'
import type { CockpitCtx } from './cockpitCtx'

export function useRequests(ctx: CockpitCtx) {
  const { id, token, t, setApp, setBusy, setError, refreshApp } = ctx
  // Request #40: a refused raise / document request is explained BESIDE its form. It used to go to
  // `error`, which renders in the decision panel far down the page — so the screen looked silent.
  const [requestError, setRequestError] = useState('')
  const [refForm, setRefForm] = useState({ ...EMPTY_REFEREE })
  const [infoNote, setInfoNote] = useState('')
  const [reqCategory, setReqCategory] = useState('')
  const [reqQualifier, setReqQualifier] = useState('')   // the 'whose' member OR the 'which' sub-value
  const [reqDocNote, setReqDocNote] = useState('')

  const doRaiseQuery = async () => {
    if (!token || !infoNote.trim()) return
    setBusy('raise'); setError(''); setRequestError('')
    try {
      setApp(await raiseResolutionItem(id, { kind: 'explanation', prompt: infoNote.trim(), fact: 'identity' }, { token }))
      setInfoNote('')
    } catch (e) { setRequestError(requestRefusalText(e, t)) } finally { setBusy('') }
  }

  // A standard request line for the selected (doc, person) — prefills the note box so the
  // reviewer can elaborate, and is the fallback if they clear it.
  const stdDocRequest = (dt: string, m: string, kind = '') => {   // kind: S4 results by name
    if (!dt) return ''
    // "Other document" has no standard clause — the reviewer types exactly what they need,
    // so leave the box empty (the generic "the requested document …" prefill was unhelpful).
    if (dt === 'other') return ''
    // Rich per-document clause (says what we look for) — clarity for the student.
    const docTxt = t(`admin.scholarship.requestDocStd.${kind ? `higher_${kind}` : dt}`)
    const memberTxt = m ? t(`scholarship.docs.income.wizard.member.${m}`) : ''
    return m
      ? t('admin.scholarship.requestDocPromptMember', { member: memberTxt, doc: docTxt })
      : t('admin.scholarship.requestDocPrompt', { doc: docTxt })
  }
  // The concrete (doc_type, member) the current category+qualifier resolves to — null until a
  // required qualifier is chosen (which keeps the Request button disabled).
  const reqResolved = resolveReq(reqCategory, reqQualifier)
  const onReqCategory = (key: string) => {
    setReqCategory(key)
    setReqQualifier('')                                  // reset the qualifier when the category changes
    const r = resolveReq(key, '')                         // prefills only for a no-qualifier category
    setReqDocNote(r ? stdDocRequest(r.docType, r.member) : '')
  }
  const onReqQualifier = (q: string) => {
    setReqQualifier(q)
    const r = resolveReq(reqCategory, q)
    setReqDocNote(r ? stdDocRequest(r.docType, r.member, r.kind) : '')
  }
  const doRequestDoc = async () => {
    if (!token || !reqResolved) return
    const { docType, member, kind } = reqResolved
    const prompt = reqDocNote.trim() || stdDocRequest(docType, member, kind)
    setBusy('reqdoc'); setError(''); setRequestError('')
    try {
      setApp(await raiseResolutionItem(
        id,
        { kind: 'doc', doc_type: docType, household_member: member, prompt, fact: docTypeToRequestFact(docType), ...(kind ? { results_kind: kind } : {}) },
        { token },
      ))
      setReqDocNote(''); setReqCategory(''); setReqQualifier('')
    } catch (e) { setRequestError(requestRefusalText(e, t)) } finally { setBusy('') }
  }

  const doActionResolution = async (itemId: number, action: 'waive' | 'resolve' | 'reopen') => {
    if (!token) return
    setBusy(`res${itemId}`); setError('')
    try {
      setApp(await actionResolutionItem(itemId, action, { token }))
    } catch { setError(t('admin.scholarship.requestInfoError')) } finally { setBusy('') }
  }

  const doAddReferee = async () => {
    if (!token || !refForm.name.trim()) return
    // Referee phone is optional, but if given it must be a valid Malaysian number.
    if (refForm.phone.trim() && !isValidPhone(refForm.phone)) {
      setError(t('scholarship.apply.error.phone')); return
    }
    setBusy('ref'); setError('')
    try {
      await addReferee(id, refForm, { token })
      setRefForm({ ...EMPTY_REFEREE })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doDeleteReferee = async (refId: number) => {
    if (!token) return
    setBusy('ref'); setError('')
    try {
      await deleteReferee(id, refId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doReRunVision = async (docId: number) => {
    if (!token) return
    setBusy('vision'); setError('')
    try {
      await reRunVision(id, docId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.visionError')) } finally { setBusy('') }
  }

  return {
    requestError, refForm, setRefForm, infoNote, setInfoNote, reqCategory, reqQualifier,
    reqDocNote, setReqDocNote, reqResolved, onReqCategory, onReqQualifier,
    doRaiseQuery, doRequestDoc, doActionResolution, doAddReferee, doDeleteReferee, doReRunVision,
  }
}
