/**
 * @jest-environment jsdom
 *
 * THE COCKPIT'S TWO READINGS OF "WHICH FACT IS THIS DOCUMENT?" — the drawer, and a doc REQUEST.
 *
 * TD-262 / W5. Three components each spelled out which verification fact a document type belongs
 * to, and only `officerCockpit`'s copy gained `income_support_doc` when the support letter became
 * income evidence (2026-09-07). `view.tsx` held a second copy, `DOC_FACT`, whose only consumer is
 * the `fact` stamped on a document REQUEST — latent, because `REQUEST_CATEGORIES` offers no such
 * request today, and live the moment one is added. Both now read `@/lib/docCategory`.
 *
 * What is asserted here is what an OFFICER sees and what the request actually SENDS:
 *   * the support letter sits in the income section of the document drawer, not the "other" one;
 *   * a request carries the fact its type belongs to, with `additional` folded to `other` —
 *     `ResolutionItem.fact` is stored and read back by the Action Centre, which knows only the
 *     four verdict facts plus `other`, so a fifth word would land in the database unreadable.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail, buildDocument } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

const GROUP = (key: string) => `admin.scholarship.docsDrawer.group.${key}`
const DRAWER_TYPE = (docType: string) => `admin.scholarship.docsDrawer.type.${docType}`

/** The drawer block under a group heading — the heading's own parent holds its rows. */
const groupBlock = (key: string): HTMLElement => {
  const heading = screen.getByText(GROUP(key))
  const block = heading.parentElement
  if (!block) throw new Error(`the ${key} group heading has no block around it`)
  return block
}

describe('the document drawer files the support letter under income', () => {
  /** An UNTAGGED support letter — the shape an Action-Centre upload really lands in. */
  const letter = () => buildDocument('income_support_doc', { id: 310 })
  const bankStatement = () => buildDocument('bank_statement', { id: 311 })

  it('⚠ THE INCOME-SUPPORT LETTER IS IN THE INCOME SECTION', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing',
                    build: { documents: [letter()] } })
    await loaded()
    expect(within(groupBlock('income')).getByText(DRAWER_TYPE('income_support_doc'))).toBeTruthy()
    // Nothing else is on this case, so an "other" bucket would mean the letter fell into it.
    expect(screen.queryByText(GROUP('other'))).toBeNull()
  })

  it('and a real "other" document still lands in the other bucket', async () => {
    // The control: without it the assertion above also passes on a map that swept every type
    // into income, which is the same defect pointing the other way.
    renderCockpit({ role: 'super', stage: 'interviewing',
                    build: { documents: [letter(), bankStatement()] } })
    await loaded()
    expect(within(groupBlock('other')).getByText(DRAWER_TYPE('bank_statement'))).toBeTruthy()
    expect(within(groupBlock('other')).queryByText(DRAWER_TYPE('income_support_doc'))).toBeNull()
    expect(within(groupBlock('income')).getByText(DRAWER_TYPE('income_support_doc'))).toBeTruthy()
  })
})

describe('a document request carries the fact its type belongs to', () => {
  /** The request controls, addressed through the heading above them. */
  const requestBox = (): HTMLElement => {
    const heading = screen.getByText('admin.scholarship.requestDocTitle')
    const box = heading.parentElement
    if (!box) throw new Error('the request-document heading has no box around it')
    return box
  }
  const selects = () => within(requestBox()).getAllByRole('combobox') as HTMLSelectElement[]
  const sendButton = () => within(requestBox())
    .getByRole('button', { name: 'admin.scholarship.requestDocSend' })

  /** Pick a category, then its qualifier, press Request, and wait for the send to settle — the
   *  controls clear themselves on success, which is the officer's own signal that it went. */
  const request = async (category: string, qualifier: string) => {
    fireEvent.change(selects()[0], { target: { value: category } })
    fireEvent.change(selects()[1], { target: { value: qualifier } })
    fireEvent.click(sendButton())
    await waitFor(() => expect(screen.queryByText('admin.scholarship.requestDocSend')).toBeNull())
  }

  const mounted = async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'shortlisted' })
    await loaded()
    api.raiseResolutionItem.mockResolvedValue(buildApplicationDetail('shortlisted', {}))
    return api
  }

  it('an income document is stamped income', async () => {
    const api = await mounted()
    await request('salary_slip', 'father')
    expect(api.raiseResolutionItem).toHaveBeenCalledWith(
      7, expect.objectContaining({ doc_type: 'salary_slip', fact: 'income' }),
      { token: 'test-token' })
  })

  it('the current-semester result slip is stamped academic', async () => {
    const api = await mounted()
    await request('results_slip', 'cgpa')
    expect(api.raiseResolutionItem).toHaveBeenCalledWith(
      7, expect.objectContaining({ doc_type: 'semester_result', fact: 'academic' }),
      { token: 'test-token' })
  })

  it('⚠ A SUPPORTING EXTRA FOLDS TO "other" — the stored fact stays one the readers know', async () => {
    // `school_leaving_cert` is `additional` in the officer's DRAWER (its own supporting-context
    // bucket) and must still be `other` on the TICKET. `ActionCentre` branches on
    // `item.fact === 'income'` and `confirmTargetFor` routes the student by substring; neither
    // has copy or behaviour for a fifth word. The fold is deliberate, and this is where it lives.
    const api = await mounted()
    await request('other', 'school_leaving_cert')
    expect(api.raiseResolutionItem).toHaveBeenCalledWith(
      7, expect.objectContaining({ doc_type: 'school_leaving_cert', fact: 'other' }),
      { token: 'test-token' })
  })
})
