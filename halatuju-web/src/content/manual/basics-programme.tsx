import type { ManualChapter } from './types'

/** Basics 1 — the programme picture (generalised from the reviewer guide's welcome). */
export const basicsProgramme: ManualChapter = {
  slug: 'basics-programme',
  title: 'The programme',
  group: 'basics',
  blurb: 'What the B40 programme is and how a case flows through it.',
  sections: [
    {
      anchor: 'what-it-is',
      title: 'What the B40 assistance programme is',
      body: (
        <>You&rsquo;re helping the <strong>B40 assistance programme</strong>, which supports students from
        lower-income families to continue into further study. Whatever your role, this is the work you&rsquo;re
        part of:
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Students <strong>apply online</strong> at halatuju.xyz.</li>
            <li>The system checks eligibility and <strong>shortlists</strong> those who qualify — a B40
            background, a solid academic record, and a clear study pathway.</li>
            <li>Shortlisted students are <strong>guided to complete</strong> their application: uploading
            documents, confirming family and income details, and answering follow-up questions.</li>
            <li>A <strong>reviewer</strong> checks the key facts and talks to the student; a <strong>QC</strong>
            gives it a second pair of eyes; the recommendation goes to sponsors, who fund the award.</li>
          </ul></>
      ),
    },
    {
      anchor: 'how-a-case-flows',
      title: 'How a case flows',
      body: (
        <>A case moves through clear stages: <strong>Shortlisted</strong> (invited to complete the application)
        → <strong>Awaiting review</strong> (the student has confirmed everything) → <strong>Interviewing</strong>
        → <strong>Interviewed</strong> (awaiting QC) → <strong>Recommended</strong> (QC accepted) →
        <strong> Awarded</strong> and beyond. The <em>Statuses</em> chapter explains each label. Your role decides
        which of these stages you act on — the rest you can see but leave to others.</>
      ),
    },
    {
      anchor: 'finding-your-way',
      title: 'Finding your way around',
      body: (
        <>The links along the top are your workspace. <strong>B40 Applications</strong> is where cases live;
        the other links depend on your role. This manual has a chapter for <em>your</em> role — it opens there
        automatically — plus these shared <em>Basics</em>. When something isn&rsquo;t clear, the
        <strong> FAQ</strong> has short answers, and the HalaTuju team is one email away
        (<strong>help@halatuju.xyz</strong>).</>
      ),
    },
  ],
}
