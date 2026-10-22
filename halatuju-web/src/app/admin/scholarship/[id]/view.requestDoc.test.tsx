/**
 * @jest-environment jsdom
 *
 * REQUEST #40 (BrightPath): "Request a document" did not save, and the screen said nothing.
 *
 * At `shortlisted` the student has not finished their own Documents step, so the server refuses
 * every reviewer request (`querying_closed`) — the student could not see one yet. The cockpit
 * offered the form anyway, and the refusal landed in an error line far down the page. Now:
 *
 *  * while the server says `officer_requests: 'documents_step'`, the form is REPLACED by one line
 *    saying the student is still completing their documents;
 *  * any other refusal is explained BESIDE the form, in words;
 *  * a request that never reached the server says it could not be sent.
 */
import { fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const raiseBox = () => screen.queryByPlaceholderText('admin.scholarship.raiseQueryPlaceholder')
const docTitle = () => screen.queryByText('admin.scholarship.requestDocTitle')

/** The error `adminMutate` throws when the server answers with a refusal. */
const refusal = (status: number, error: string) =>
  Object.assign(new Error(error), { status, code: error, body: { error } })

/** Raise a query that fails with `rejection`; resolves to the line the screen then shows. (The
 *  wait for that line starts straight after the click, so the failed call settles inside it.) */
async function raiseAndFail(rejection: unknown): Promise<string | null> {
  const { api } = renderCockpit({ role: 'super', stage: 'profile_complete',
                                  build: { officer_requests: 'open' } })
  await loaded()
  api.raiseResolutionItem.mockRejectedValue(rejection)
  fireEvent.change(raiseBox() as HTMLElement, { target: { value: 'Whose bill is this?' } })
  fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.raiseQuerySend' }))
  return (await screen.findByRole('alert')).textContent
}

describe('while the student is still at their Documents step', () => {
  it('replaces the request controls with one line saying why', async () => {
    renderCockpit({ role: 'super', stage: 'shortlisted',
                    build: { officer_requests: 'documents_step' } })
    await loaded()
    expect(screen.getByText('admin.scholarship.requestsDocumentsStep')).toBeTruthy()
    expect(docTitle()).toBeNull()
    expect(raiseBox()).toBeNull()
  })

  it('offers the controls once requests are open', async () => {
    renderCockpit({ role: 'super', stage: 'profile_complete', build: { officer_requests: 'open' } })
    await loaded()
    expect(docTitle()).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.requestsDocumentsStep')).toBeNull()
  })
})

describe('a request that fails is never silent', () => {
  it('⚠ a server refusal is explained beside the form (the request #40 regression)', async () => {
    expect(await raiseAndFail(refusal(400, 'querying_closed')))
      .toBe('admin.scholarship.requestRefused.querying_closed')
    // Beside the controls — the form is still on screen with it.
    expect(raiseBox()).toBeTruthy()
  })

  it('⚠ the same holds for "Request a document" itself', async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'profile_complete',
                                    build: { officer_requests: 'open' } })
    await loaded()
    api.raiseResolutionItem.mockRejectedValue(refusal(400, 'querying_closed'))
    fireEvent.change(screen.getByDisplayValue('admin.scholarship.requestDocAny'),
                     { target: { value: 'offer_letter' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.requestDocSend' }))
    expect(api.raiseResolutionItem).toHaveBeenCalledWith(
      7, expect.objectContaining({ kind: 'doc', doc_type: 'offer_letter' }), { token: 'test-token' })
    expect((await screen.findByRole('alert')).textContent)
      .toBe('admin.scholarship.requestRefused.querying_closed')
  })

  it('a refusal with no code of its own shows the server\'s message', async () => {
    expect(await raiseAndFail(refusal(403, 'Your admin role cannot perform this action.')))
      .toBe('Your admin role cannot perform this action.')
  })

  it('a request that never reached the server says it could not be sent', async () => {
    expect(await raiseAndFail(new TypeError('Failed to fetch')))
      .toBe('admin.scholarship.requestInfoError')
  })
})
