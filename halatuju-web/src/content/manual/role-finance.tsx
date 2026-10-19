import type { ManualChapter } from './types'

/** Finance chapter — the payment-run APPROVER since #39 Sprint 2 (owner, 2026-10-19). Every statement traces to
 *  docs/scholarship/role-matrix.md (the authority) and the live gates in
 *  apps/scholarship/payments.py + views_admin.py. */
export const roleFinance: ManualChapter = {
  slug: 'role-finance',
  title: 'Finance admin',
  group: 'role',
  role: 'finance',
  blurb: 'You approve the money before it goes out.',
  sections: [
    {
      anchor: 'finance-remit',
      title: 'What you do',
      body: (
        <>You <strong>approve payment runs</strong>. Somebody (a general admin) builds the month&rsquo;s list of
        students and signs it as the preparer; you check it and approve it, and <strong>your approval releases the
        money</strong> &mdash; the payment instruction is emailed to Vircle, which pays the students.
        Your organisation admin no longer countersigns runs; they still put the organisation&rsquo;s money into
        Vircle, which happens outside HalaTuju. Nothing is paid until you approve. For <strong>wallet
        credits</strong> (sponsor money coming in) you are still the <strong>check</strong>: an admin records the
        credit, you check it, and your organisation admin countersigns. Your job is the money, not the students
        &mdash; you don&rsquo;t review applications, and you can&rsquo;t see applicant files.</>
      ),
    },
    {
      anchor: 'finance-where',
      title: 'Where to find Payments',
      body: (
        <>Point at the strip of icons on the left to open the menu, and choose <strong>Payments</strong> under
        your organisation. You&rsquo;ll see the list of payment runs, newest first. A run waiting for your
        approval is listed above them under <strong>Waiting for you</strong>, and the Payments row in the menu
        carries a number when one is waiting.</>
      ),
      img: '/manual/finance-payments.png',
      alt: 'The Payments page, reached from the organisation section of the menu',
    },
    {
      anchor: 'finance-checking',
      title: 'Approving a run',
      body: (
        <>Open a run to see every student on it, the amount each is due, and the total. Download the
        <strong> CSV</strong> &mdash; that is the exact file the payment instruction is built from, so check it,
        not just the screen. When you are satisfied, type your <strong>full name</strong> in the
        <strong> Approved</strong> box and click <strong>Approve &amp; send to Vircle</strong>. Your name must
        match the name on your account exactly, and it is recorded against the run permanently. The instruction
        is emailed to Vircle at once, with you copied, so you hold your own record of what was sent.</>
      ),
      img: '/manual/finance-signature.png',
      alt: 'The signature steps on a payment run',
    },
    {
      anchor: 'finance-not-right',
      title: 'If something isn’t right',
      body: (
        <>Then <strong>don&rsquo;t approve</strong>. That is the whole point of the step &mdash; the run cannot
        go anywhere without you. Ask whoever prepared it to correct it. Note that editing a run sends it back to
        <strong> draft</strong> and clears every signature collected so far, <em>including yours</em>, so
        you&rsquo;ll be asked to approve the corrected list afresh. That is deliberate: nobody should sign one
        list and have a different one go out.</>
      ),
    },
    {
      anchor: 'finance-three-signers',
      title: 'Different people sign',
      body: (
        <>Every signature on a run must belong to a <strong>different person</strong>, so you cannot approve a
        run you signed in another step. When no one else can approve a run &mdash; for instance a run you checked
        before Finance became the approver &mdash; your <strong>organisation admin</strong> approves it instead,
        and the run says so. Your organisation may also give somebody a separate <strong>check</strong> step
        before yours; a run then shows three steps and waits for that check before you can approve.</>
      ),
    },
    {
      anchor: 'finance-funding-summary',
      title: 'The funding summary',
      body: (
        <>Below the runs list you&rsquo;ll find the <strong>funding summary</strong>: every student your
        organisation is currently funding, what they were awarded, what has been paid so far, what remains, their
        eWallet ID, and when they were last paid. It is the reconciliation view &mdash; use it to answer
        &ldquo;how much of this award is left?&rdquo; without opening anything else. If Vircle has given a student
        a wallet but has not yet told us it is switched on, an amber line above the table <strong>names those
        students</strong>. Nothing emails Vircle about it any more, so this line is the reminder: ask Vircle to
        activate the wallet, or to press <em>Get Details</em> on that student&rsquo;s row.</>
      ),
      img: '/manual/finance-funding-summary.png',
      alt: 'The funding summary table on the Payments page',
    },
    {
      anchor: 'finance-overview',
      title: 'The overview: the money at a glance',
      body: (
        <>Above <strong>Payments</strong> in the menu there is now an <strong>Overview</strong> for the gift, and
        it is yours to open. It shows the money as <em>figures</em>: what has been committed, what has been
        paid, what is still outstanding and what the students have actually spent &mdash; and then four charts,
        so you can see the shape of it rather than a single total. Payments against spending, month by month, with
        the <strong>balance still in wallets</strong>, and three totals beneath: payments, spending, balance. (A
        payment released on or after the 27th counts as the <em>following</em> month&rsquo;s, because each month&rsquo;s
        money goes out a few days early &mdash; so July&rsquo;s payment sits beside July&rsquo;s spending.) What a card
        payment cost on average, week by week, with the whole-period figure beneath it. How many
        <strong> transactions</strong> a student makes in a week &mdash; one card payment is one transaction; we
        are not told what was in the basket, so the chart never claims to count items. And where the money
        goes, by category, largest first, with <strong>&ldquo;not categorised&rdquo; last</strong> rather than
        folded into the others: a total you cannot see the uncategorised part of is not a total you can rely on.
        <br /><br />
        An <strong>intake year</strong> picker at the top narrows every figure on the page to one round, the
        money included. And your organisation admin may have switched a panel off for the whole organisation
        &mdash; a chart you expected and cannot see is that, not a fault.
        <br /><br />
        These are <strong>totals only</strong>. No names, no files, no verdicts &mdash; the Overview follows
        the same line your role does everywhere else. And it does not replace <strong>Payments</strong>, which
        remains the ledger: the runs, the CSV, the signatures and the funding summary student by student. Read
        the Overview to see how the gift is going; open Payments to check and approve.</>
      ),
    },
    {
      anchor: 'finance-cannot',
      title: 'What you cannot do',
      body: (
        <>You <strong>cannot open applicant files</strong> &mdash; no applications list, no documents, no income
        details, no interview notes, no verdicts. That is by design: checking a payment doesn&rsquo;t require
        knowing a family&rsquo;s circumstances, so you aren&rsquo;t given them. You also cannot
        <strong> create</strong>, <strong>edit</strong> or <strong>cancel</strong> a run &mdash; you approve what
        others prepare. You can view the Sponsors list, but not approve or reject a sponsor. Billing &amp; usage,
        including the invoices the platform sends your organisation, is for your organisation admin.</>
      ),
    },
  ],
}
