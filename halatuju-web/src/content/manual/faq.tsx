import type { ReactNode } from 'react'
import type { Audience, ManualRole } from './types'

export type QA = { q: ReactNode; a: ReactNode }

/** FAQ grouped by audience. `everyone` shows for all roles; the rest are role-scoped.
 *  Every existing reviewer Q&A is re-homed here (not rewritten). New QC / org-admin /
 *  general-admin Q&As trace to docs/scholarship/role-matrix.md. */
export const FAQ: Record<Audience, QA[]> = {
  everyone: [
    {
      q: <>Is this paid? Do I get any compensation?</>,
      a: <>No — helping to run and review the programme is <strong>voluntary</strong>, and there&rsquo;s no
        payment. Thank you for giving your time to these students.</>,
    },
    {
      q: <>How do I sign in next time?</>,
      a: <>Go to <strong>halatuju.xyz/admin/login</strong> and enter your email and password, or sign in with
        Google.</>,
    },
    {
      q: <>How do I change or reset my password?</>,
      a: <>On the sign-in page, click <strong>Forgot password</strong>, enter your email, and follow the link we
        send to set a new one.</>,
    },
    {
      q: <>Does my email have to be Gmail?</>,
      a: <>No — any email address works.</>,
    },
    {
      q: <>Is the information I see confidential?</>,
      a: <>Yes. Treat everything about an applicant as <strong>private</strong> — only discuss it with the
        HalaTuju team. Please don&rsquo;t download, share or keep applicant details.</>,
    },
    {
      q: <>What do the application statuses mean?</>,
      a: <>In order: <strong>Shortlisted</strong> (invited to complete their application) → <strong>Awaiting
        review</strong> (details and documents confirmed, not yet reviewed) → <strong>Interviewing</strong> →
        <strong> Interviewed</strong> (awaiting QC) → <strong>Recommended</strong> (QC accepted) →
        <strong> Awarded</strong> and beyond. <strong>Rejected</strong>/<strong>Expired</strong> close a case.</>,
    },
    {
      q: <>What are the four checks?</>,
      a: <>Identity (is this really them), Academic record (do the grades match the slip), Pathway (is their study
        plan or offer in order), and Income (are they genuinely B40 / in need).</>,
    },
    {
      q: <>Should I just trust the AI?</>,
      a: <>No — the AI gives a <em>suggestion</em> for each fact and a draft profile. <strong>A person
        decides.</strong> Always check its reading against the documents.</>,
    },
    {
      q: <>I&rsquo;m stuck, or something looks wrong — whom do I contact?</>,
      a: <>Email the HalaTuju team at <strong>help@halatuju.xyz</strong> and we&rsquo;ll help.</>,
    },
  ],
  reviewer: [
    {
      q: <>Why do I only see some applicants?</>,
      a: <>You see <strong>only the applicants assigned to you</strong>, so you can focus on your own. That&rsquo;s
        normal.</>,
    },
    {
      q: <>Why does my profile ask for my languages?</>,
      a: <>So we can assign you students you can speak with comfortably. Set your fluency in English, Bahasa Melayu
        and Tamil on your <strong>Profile</strong> — we match you to applicants whose preferred language you
        share.</>,
    },
    {
      q: <>Will my phone number be shared with students?</>,
      a: <>Your number may be shared with the students assigned to you, so they know to expect your call. It&rsquo;s
        on by default — you can <strong>opt out anytime</strong> on your Profile.</>,
    },
    {
      q: <>What is the &ldquo;Student profile (draft)&rdquo;?</>,
      a: <>A short summary written automatically from the student&rsquo;s own application. A helpful starting point
        — always check it against the uploaded documents before relying on it.</>,
    },
    {
      q: <>How do I judge the Income (B40) check? It&rsquo;s the hardest one.</>,
      a: <>Two routes. <strong>STR route:</strong> the proof is an <em>approved</em> MySTR record — a
        <strong> SALINAN application-record is not proof</strong>; if the status isn&rsquo;t clearly
        &ldquo;Lulus&rdquo;, ask for the MySTR Semakan Status / Dashboard, or the approval letter.
        <strong> Salary route:</strong> payslips / EPF, judged per head against the B40 line. When it&rsquo;s
        genuinely borderline, that&rsquo;s what the interview is for — don&rsquo;t force a verdict on weak
        evidence.</>,
    },
    {
      q: <>How do I ask the student a question?</>,
      a: <>Use <strong>Raise a query</strong> or <strong>Request a document</strong>. They get an email; their
        reply shows in the <strong>Outstanding</strong> box.</>,
    },
    {
      q: <>What does &ldquo;Save verdict &amp; generate final profile&rdquo; do?</>,
      a: <>It records your decision and creates the final, polished profile — and sends the case on for
        <strong> QC</strong>. The student becomes visible to sponsors only once QC accepts it.</>,
    },
    {
      q: <>What&rsquo;s the difference between rating Pass/Fail and approving?</>,
      a: <>The <strong>Pass/Fail</strong> on each fact says whether the <em>AI read that fact correctly</em>.
        <strong> Approve / Decline</strong> is your actual recommendation. They&rsquo;re separate: you can Pass all
        four facts and still <strong>Decline</strong> — for instance, income verified but above the B40 line.</>,
    },
    {
      q: <>Can I undo a decision after I Save?</>,
      a: <>Not as a reviewer — <strong>Save is final from your side</strong>. If something needs changing, contact
        the HalaTuju team (<strong>help@halatuju.xyz</strong>); a super-admin can reopen the case. Check the facts
        before you save.</>,
    },
    {
      q: <>What&rsquo;s the recommended amount for?</>,
      a: <>It&rsquo;s your suggestion of how much assistance would help, set on the slider. It guides the
        sponsor.</>,
    },
    {
      q: <>The offer letter doesn&rsquo;t match the stated pathway — what do I do?</>,
      a: <>Note it and ask in the interview (or raise a query). They may have updated their plan; you can also ask
        them to upload the latest offer letter, which replaces the old one.</>,
    },
    {
      q: <>The student has completed a semester or two — should I ask for more?</>,
      a: <>If they have their results (CGPA), you may ask them to upload the latest result. If it&rsquo;s
        satisfactory (above 3.0), you may consider recommending them for support.</>,
    },
    {
      q: <>How do the suggested interview questions work?</>,
      a: <>In the <strong>Interview Stage</strong>, tap <strong>Suggest interview questions</strong> — the system
        proposes a few from this student&rsquo;s record; tap <strong>Generate more</strong> for others. A prompt,
        not a script: ask your own too, and jot <strong>one line</strong> per point before you submit.</>,
    },
    {
      q: <>Why is there always a &ldquo;Motivation &amp; grit&rdquo; point on the agenda?</>,
      a: <>Motivation is deliberately a human judgement — the system never scores it — so it&rsquo;s always on the
        agenda, and flagged for extra attention when the statement of intent is thin.</>,
    },
    {
      q: <>How do I schedule the interview?</>,
      a: <>On the applicant&rsquo;s page, use <strong>Interview scheduling</strong> to propose two or three times.
        The student picks one and a <strong>Google Meet</strong> link is created automatically — you both get a
        confirmation, plus reminders the day before and an hour before.</>,
    },
    {
      q: <>What if the student needs a different time, or doesn&rsquo;t book?</>,
      a: <>They can <strong>reschedule or cancel</strong> up to a few hours before, and you&rsquo;ll see the
        change. If they cancel, just propose fresh times.</>,
    },
  ],
  qc: [
    {
      q: <>Can I review cases now, not just QC them?</>,
      a: <>Yes. QC is a <strong>review-all</strong> role — you can act on any case in your organisation and step in
        as an overflow reviewer. Assignment still routes most cases to reviewers; this is for clearing the
        queue.</>,
    },
    {
      q: <>Why was my QC refused on a case I reviewed?</>,
      a: <>Two-person control: you can never QC a case whose verdict <em>you</em> recorded, or that you were the
        assigned reviewer of. It routes to another QC (or a super-admin). This protects every award&rsquo;s
        integrity.</>,
    },
    {
      q: <>Why is Accept blocked on this case?</>,
      a: <>A verdict fact is still <strong className="text-red-700">red</strong> — the gap floor blocks Accept so a
        red fact never reaches sponsors unexamined. Resolve the gap or reopen to the reviewer; if you&rsquo;re
        certain despite it, override with a recorded reason.</>,
    },
  ],
  org_admin: [
    {
      q: <>Why can&rsquo;t I countersign this payment run yet?</>,
      a: <>Because your organisation has a <strong>finance admin</strong>, and the run hasn&rsquo;t been checked
        yet. The chain is: someone prepares and signs it, finance checks it, then you countersign and the money
        goes. You&rsquo;ll see &ldquo;waiting for the finance check&rdquo; until that middle step is done. If you
        have no finance admin, this step doesn&rsquo;t exist and you countersign straight after the first
        signature.</>,
    },
    {
      q: <>How does a payment run work?</>,
      a: <>Open <strong>Administration → Payments</strong> and create a run for the month. The system lists the
        students who qualify and skips the rest with a reason. Someone signs it as the preparer, and you
        countersign &mdash; and only then is the instruction emailed to Vircle with the payment file. Every
        signature must be a different person, and editing the list after any signature returns the run to
        <strong> draft</strong> and clears the signatures collected so far.</>,
    },
    {
      q: <>Can I appoint a finance admin myself?</>,
      a: <>Yes. <strong>Administration → Invite staff → Finance</strong>. The moment their account is active, the
        finance check becomes part of your payment chain &mdash; including for a run that is already waiting for
        your countersignature.</>,
    },
    {
      q: <>Why can&rsquo;t I revoke my other organisation admin?</>,
      a: <>You can&rsquo;t revoke the <strong>last</strong> organisation admin — the Revoke option isn&rsquo;t
        offered on the sole admin, so your organisation is never left without one. Invite or appoint another admin
        first (adding an org admin is a platform action — ask the HalaTuju team).</>,
    },
    {
      q: <>Why was my QC refused on a case I reviewed?</>,
      a: <>The same two-person-control rule applies to you as to a QC: you can never QC a case whose verdict you
        recorded or that you reviewed. It goes to someone else.</>,
    },
    {
      q: <>Can I add another organisation admin?</>,
      a: <>No — appointing another organisation admin (and adding a whole organisation) stays with the HalaTuju
        platform team. Ask us and we&rsquo;ll set it up.</>,
    },
    {
      q: <>What will &ldquo;Billing &amp; usage&rdquo; show?</>,
      a: <>It&rsquo;s marked <em>coming soon</em>. Once per-programme metering is switched on it will show your
        programme&rsquo;s costs and usage. Nothing is billed today.</>,
    },
    {
      q: <>Can I set the award amount?</>,
      a: <>No — the amount is fixed by pathway, and setting/overriding it stays with the platform (a dedicated
        Finance role will take money powers when payouts go live). You recommend; the platform confirms.</>,
    },
  ],
  admin: [
    {
      q: <>Why can&rsquo;t I click anything?</>,
      a: <>Your role is <strong>view-only</strong>: you can see everything in your organisation (applications, the
        Sponsors list, the Administration staff list) but the buttons that change things aren&rsquo;t shown to
        you. Ask your organisation admin to make a change.</>,
    },
  ],
  finance: [
    {
      q: <>What can I do as a finance admin?</>,
      a: <>You <strong>check</strong> payment runs. Somebody prepares the month&rsquo;s list and signs it, you
        check it, then your organisation admin countersigns and the money is released. You can also read the
        <strong> funding summary</strong> &mdash; what each student was awarded, paid and still has left. You
        cannot create, edit or cancel a run.</>,
    },
    {
      q: <>Why can&rsquo;t I open a student&rsquo;s application?</>,
      a: <>Because checking a payment doesn&rsquo;t require it. Your role deliberately has no access to applicant
        files, documents, income details or verdicts &mdash; only the payment figures. If you need something
        about a student explained, ask your organisation admin.</>,
    },
    {
      q: <>I found a mistake on a run. What do I do?</>,
      a: <>Don&rsquo;t sign it. Tell whoever prepared it. When they correct it the run goes back to
        <strong> draft</strong> and every signature so far is cleared &mdash; including yours &mdash; so
        you&rsquo;ll check the corrected list again before it can move on.</>,
    },
    {
      q: <>It won&rsquo;t accept my signature. Why?</>,
      a: <>Two common reasons. Your typed name must match the name on your account <strong>exactly</strong>. And
        every signature on a run must be a <strong>different person</strong> &mdash; you can&rsquo;t check a run
        you prepared yourself.</>,
    },
    {
      q: <>Where is Payments? I don&rsquo;t see it in the menu.</>,
      a: <>It&rsquo;s inside <strong>Administration</strong> &mdash; open that, then the <strong>Payments</strong>
        card. There is no separate menu entry for it.</>,
    },
  ],
}

const ROLE_TO_AUDIENCE: Record<ManualRole, Audience | null> = {
  reviewer: 'reviewer', qc: 'qc', org_admin: 'org_admin', admin: 'admin',
  finance: 'finance', super: null,
}

/** Which audience sections a caller sees by default (Everyone + their own role). super/org_admin
 *  can widen to `all` (handled by the page via a chip); this is the default-filter set. */
export function defaultFaqAudiences(role: ManualRole | undefined): Audience[] {
  const own = role ? ROLE_TO_AUDIENCE[role] : null
  // super has no own section → default to everything so it isn't an empty page.
  if (role === 'super') return ['everyone', 'reviewer', 'qc', 'org_admin', 'admin', 'finance']
  return own ? ['everyone', own] : ['everyone']
}

/** Whether the caller may widen the FAQ to all audiences (the "All" chip). */
export function canSeeAllFaq(role: ManualRole | undefined): boolean {
  return role === 'super' || role === 'org_admin'
}

export const ALL_FAQ_AUDIENCES: Audience[] = ['everyone', 'reviewer', 'qc', 'org_admin', 'admin', 'finance']

export const AUDIENCE_LABEL: Record<Audience, string> = {
  everyone: 'Everyone', reviewer: 'Reviewer', qc: 'QC', org_admin: 'Org admin',
  admin: 'General admin', finance: 'Finance',
}
