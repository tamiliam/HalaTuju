import type { ManualChapter } from './types'

/** Finance chapter — the payment-run checker. Every statement traces to
 *  docs/scholarship/role-matrix.md (the authority) and the live gates in
 *  apps/scholarship/payments.py + views_admin.py. */
export const roleFinance: ManualChapter = {
  slug: 'role-finance',
  title: 'Finance admin',
  group: 'role',
  role: 'finance',
  blurb: 'You check the money before it goes out.',
  sections: [
    {
      anchor: 'finance-remit',
      title: 'What you do',
      body: (
        <>You are the <strong>check</strong> between the person who prepares a payment run and the person who
        approves it. Somebody builds the month&rsquo;s list of students and signs it; you check it; only then can
        your organisation admin countersign and release the money. Nothing is paid until all three signatures are
        in. Your job is the money, not the students &mdash; you don&rsquo;t review applications, and you
        can&rsquo;t see applicant files.</>
      ),
    },
    {
      anchor: 'finance-where',
      title: 'Where to find Payments',
      body: (
        <>Open <strong>Administration</strong> from the menu, then the <strong>Payments</strong> card. There is no
        Payments item in the main menu &mdash; the Administration page is the way in, the same as for everyone
        else who uses it. You&rsquo;ll see the list of payment runs, newest first.</>
      ),
      img: '/manual/finance-payments.png',
      alt: 'The Payments card on the Administration page',
    },
    {
      anchor: 'finance-checking',
      title: 'Checking a run',
      body: (
        <>Open a run to see every student on it, the amount each is due, and the total. Download the
        <strong> CSV</strong> &mdash; that is the exact file the bank instruction is built from, so check it, not
        just the screen. When you are satisfied, type your <strong>full name</strong> in the finance box and
        click <strong>Check</strong>. Your name must match the name on your account exactly, and it is recorded
        against the run permanently.</>
      ),
      img: '/manual/finance-signature.png',
      alt: 'The three signature steps on a payment run',
    },
    {
      anchor: 'finance-not-right',
      title: 'If something isn’t right',
      body: (
        <>Then <strong>don&rsquo;t sign</strong>. That is the whole point of the step &mdash; the run cannot go
        anywhere without you. Ask whoever prepared it to correct it. Note that editing a run sends it back to
        <strong> draft</strong> and clears every signature collected so far, <em>including yours</em>, so
        you&rsquo;ll be asked to check the corrected list afresh. That is deliberate: nobody should sign one list
        and have a different one go out.</>
      ),
    },
    {
      anchor: 'finance-three-signers',
      title: 'Three different people',
      body: (
        <>Every signature on a run must belong to a <strong>different person</strong>. You cannot check a run you
        prepared, and you cannot also countersign one you have checked. If you find yourself unable to sign, it is
        usually this rule &mdash; someone else has to take one of the steps.</>
      ),
    },
    {
      anchor: 'finance-funding-summary',
      title: 'The funding summary',
      body: (
        <>Below the runs list you&rsquo;ll find the <strong>funding summary</strong>: every student your
        organisation is currently funding, what they were awarded, what has been paid so far, what remains, their
        eWallet ID, and when they were last paid. It is the reconciliation view &mdash; use it to answer
        &ldquo;how much of this award is left?&rdquo; without opening anything else.</>
      ),
      img: '/manual/finance-funding-summary.png',
      alt: 'The funding summary table on the Payments page',
    },
    {
      anchor: 'finance-cannot',
      title: 'What you cannot do',
      body: (
        <>You <strong>cannot open applicant files</strong> &mdash; no applications list, no documents, no income
        details, no interview notes, no verdicts. That is by design: checking a payment doesn&rsquo;t require
        knowing a family&rsquo;s circumstances, so you aren&rsquo;t given them. You also cannot
        <strong> create</strong>, <strong>edit</strong> or <strong>cancel</strong> a run &mdash; you check what
        others prepare. You can view the Sponsors list, but not approve or reject a sponsor. Billing &amp; usage
        is not built yet.</>
      ),
    },
  ],
}
