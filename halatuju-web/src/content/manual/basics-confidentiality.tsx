import type { ManualChapter } from './types'

/** Basics 4 — confidentiality / PDPA + contact (from the reviewer FAQ). */
export const basicsConfidentiality: ManualChapter = {
  slug: 'basics-confidentiality',
  title: 'Confidentiality & help',
  group: 'basics',
  blurb: 'Keeping applicant data private, and where to get help.',
  sections: [
    {
      anchor: 'confidentiality',
      title: 'Everything about an applicant is private',
      body: (
        <>Treat everything you see about an applicant as <strong>confidential</strong> — names, documents, family
        and income details. Only discuss a case with the HalaTuju team. Please <strong>don&rsquo;t download,
        share, screenshot or keep</strong> applicant details outside the system. This is a PDPA obligation, not a
        preference.</>
      ),
    },
    {
      anchor: 'your-account',
      title: 'Your account',
      body: (
        <>Sign in at <strong>halatuju.xyz/admin/login</strong> with your email and password, or with Google. Any
        email address works. Forgotten your password? Use <strong>Forgot password</strong> on the sign-in page.
        Reviewing (and helping to run the programme) is <strong>voluntary</strong> — thank you for your time.</>
      ),
    },
    {
      anchor: 'getting-help',
      title: 'Getting help',
      body: (
        <>Stuck, or something looks wrong with your account or a case? Email the HalaTuju team at
        <strong> help@halatuju.xyz</strong> and we&rsquo;ll sort it out. The <strong>FAQ</strong> also has quick
        answers grouped by role.</>
      ),
    },
  ],
}
