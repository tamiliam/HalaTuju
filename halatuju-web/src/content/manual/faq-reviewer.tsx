/** The reviewer FAQ — moved out of `faq.tsx` whole (2026-10-30) when that file passed the 600-line
 *  standard. Moves only: every Q&A below is the line it was. */
import type { QA } from './types'

export const REVIEWER_FAQ: QA[] = [
    {
      q: <>I land on an <strong>Overview</strong> now instead of the list. What is it?</>,
      a: <>It is your own work, gathered on one page: the cases currently with you, <strong>the date each
        verdict is due</strong>, and how many are due soon or already overdue. It is the first entry under your
        gift in the menu, and you can go straight to <strong>Applications</strong> from there as before &mdash;
        nothing was taken away. The due dates are the same ones the reminder emails quote. You will not find
        money or the programme&rsquo;s overall figures on it; those belong to the people who run the gift.</>,
    },
    {
      q: <>Who sets the <strong>rules</strong> a student must pass, and can they change mid-round?</>,
      a: <>Your organisation admin sets them on the gift&rsquo;s Rules tab. A change applies from the moment it
        is saved, to students already in as well, so a student may be shortlisted, or not, under the new
        rules. A student outside the gift&rsquo;s course-start years is flagged for you to look at, never
        declined.</>,
    },
    {
      q: <>An STPM student&rsquo;s Academic card now shows <strong>SPM prerequisites</strong>. What are they?</>,
      a: <>The SPM grades an STPM student enters alongside her STPM results, because many degree courses also
        set SPM requirements. Since 2 October 2026 they are saved to her profile instead of only to her
        browser, so they appear on the card once she has entered or re-saved them. They are what she typed;
        check them against her SPM slip as you would her other grades. A student who has not entered any
        shows none.</>,
    },
    {
      q: <>What does each slot of the <strong>Academic card</strong> show, and what does <strong>N/A</strong> mean?</>,
      a: <>Every student&rsquo;s Academic card is a set of rows in the same order for their route, each with a thin
        line above it; two slots share a row on a wider screen and stack on a phone. <strong>SPM:</strong>
        <strong> Secondary school</strong> and <strong>Merit score</strong>; their <strong>SPM grades</strong>;
        <strong> Chosen programme</strong> and <strong>Reporting date</strong>; <strong>Institution</strong>.
        <strong> STPM, Matriculation, Asasi or Diploma</strong> (since 26 November 2026): Secondary school on a
        row of its own; <strong>Pre-U institution</strong> and Merit score; <strong>CGPA</strong> and <strong>MUET</strong>;
        their <strong>STPM grades</strong> (STPM only); their <strong>SPM prerequisites</strong>; then the programme,
        reporting date and institution rows. <strong>Pre-U institution</strong> is where the student says they
        completed their STPM, Matriculation, Asasi or Diploma &mdash; the form asks them. It carries no tick yet (a
        later step will tick it against their results slip). An older STPM case with this field empty shows the
        Form 6 school they gave earlier. Secondary school is always in capitals, as their documents print it. The
        merit score carries its exam and, where we have read it, the year in brackets on the same line &mdash;
        <em>85.4 (SPM 2024)</em> from their SPM slip, <em>92.1 (STPM 2025)</em> from their STPM results, and for a
        Matriculation, Asasi or Diploma student their qualification and the year their transcript&rsquo;s session ends,
        e.g. <em>85.4 (Matriculation 2025)</em> for a 2024/2025 session; a year off the expected sitting is shown in amber.
        When no year has been read, the merit shows as the number alone, with no bracket; documents read before
        25 November 2026 show a Matriculation, Asasi or Diploma year only when their title prints the session. A grey
        <strong> Stated by student</strong> line under the programme or institution means no offer letter confirms it
        yet. For a Matriculation, Asasi or Diploma student, the college they typed is the next one they plan to attend,
        so it appears on the institution row as <strong>Stated by student</strong>. That is not the
        <strong> Pre-U institution</strong> slot, which is where they completed their pre-U. <strong>N/A</strong> in a muted colour means the slot is required but empty: nothing was entered or read.
        It is not a mismatch. The reporting date always shows, and reads N/A until a date is stored or read from their
        offer letter.</>,
    },
    {
      q: <>What is a <strong>Matriculation, Asasi or Diploma</strong> student on the Academic card?</>,
      a: <>Since 26 October 2026 a student may enter Matriculation, Asasi (Foundation) or Diploma results
        instead of STPM. They count as <strong>STPM-equivalent</strong>: the gift&rsquo;s minimum CGPA is
        tested on their overall CGPA, and their merit is that CGPA ÷ 4 × 100, as for an STPM student. The card
        uses the same slots as every other student (see the next question): their merit score, with their qualification
        and transcript year in brackets where we can read it, a <strong>Pre-U institution</strong> slot (where they
        say they completed it, as asked on the form; no tick yet), their <strong>CGPA</strong> as printed on their results
        (Matriculation and Asasi: their overall CGPA is 90% CGPA and 10% co-curriculum; a Diploma&rsquo;s overall
        CGPA is its CGPA as it is &mdash; the co-curriculum score no longer has a line of its own), their
        <strong> MUET</strong> band and the SPM grades they entered, under <strong>SPM prerequisites</strong>
        (as on an STPM card). Only a diploma from a <strong>public</strong> institution counts; a
        private-college diploma does not qualify. Their results document is the separate
        <strong> STPM / Matriculation / Asasi / Diploma results</strong> upload (see the next question).</>,
    },
    {
      q: <>Which <strong>results</strong> must a student upload, and what does the Academic card check?</>,
      a: <>It follows the course they have chosen. Bound for a <strong>university degree</strong> with STPM,
        Matriculation, Asasi or Diploma results, they upload those results (<strong>required</strong>); their SPM
        slip is <strong>optional</strong> and never stops them submitting. A student with only SPM results who
        chose a degree must upload higher results too (a degree needs them), as well as their SPM slip. On a <strong>post-SPM pathway</strong>
        (Matriculation, Form 6, Polytechnic, ILKBS, PISMP and so on) only the <strong>SPM results slip</strong> is
        required. With no course chosen yet, it follows the results they hold. An application keeps the
        requirement it was submitted under &mdash; but one submitted before the higher-results upload existed (26 October 2026) by a degree-bound student holding STPM, Matriculation, Asasi or Diploma results, with none uploaded, shows that slot as <strong>Missing</strong>, its Academic card is at most <strong>Probable</strong> (&ldquo;STPM results not on file&rdquo;), and the system asks her for them (raised while the case is Completed, instead of the semester-result request); nothing sends it back to her. The Academic card checks the higher results&rsquo; name, which
        results they are and the CGPA (and, for STPM, the subject grades) against what she entered; an SPM slip
        is compared only if one is on file. STPM results (slip or certificate) are checked for genuineness like an SPM slip: a screenshot of the online results-checker page is flagged, and her Documents page asks her to re-upload the real document (after she submits, request it yourself); a printout of the MPM results web page (PDF, scan or photo) or a certified copy is fine. On the cockpit, an STPM student&rsquo;s grades carry <strong>one tick</strong> after the subjects when every grade matches her STPM results (as SPM grades do), and her CGPA (worked out from her grades: Pengajian Am + her best three others) a tick when it matches; a small <strong>&ne;</strong> marker sits beside a grade or the CGPA that differs &mdash; hover over it for the document&rsquo;s grade or PNGK; no tick means no results read yet, or a subject not on the document, and <strong>not calculated</strong> beside the CGPA means fewer than Pengajian Am + three grades were entered, so the figure shown is the one she typed. A marker is a prompt to read the document yourself; it does not change the verdict on its own. After she submits, the system also asks her (in her Action Centre, while the case is Completed) to <strong>add her remaining STPM subjects</strong> when she entered fewer than Pengajian Am + three, and to <strong>confirm her co-curriculum score</strong> when the one on file could not be worked out cleanly; each opens her STPM results page and closes by itself once she saves there. An STPM CGPA counts as matching the document only within 0.01 (since 28 October 2026); Matriculation, Asasi and Diploma keep 0.05, as their prints may round to one decimal.
        A Matriculation academic transcript and a polytechnic Diploma academic transcript are checked too (since 29 October 2026): a clear one counts as genuine, and anything the check is unsure of stays <strong>not checked</strong> &mdash; it is never called fake. By the owner&rsquo;s ruling, only the <strong>final</strong> result counts: for Matriculation and a Diploma, the final academic transcript (a <strong>provisional</strong> transcript that prints its completion status and final CGPA counts as final). A <strong>semester result slip</strong> (a final &ldquo;Lulus dan Tamat&rdquo; slip included), a screenshot of the <strong>polytechnic student portal</strong>, or a transcript that shows the programme still in progress does not count: the card reads as if the final results are not yet on file &mdash; Academic is at most <strong>Probable</strong>, the card says the final transcript is still owed, her Documents page asks her for her final academic transcript, and once she has submitted the system asks her for it too (when her programme asks for higher results). Only what the page itself shows decides this: a transcript whose status line is missing from the page or cannot be read stays <strong>not checked</strong> and nobody is asked to upload it again. A <strong>Matriculation offer letter</strong> uploaded here is not a results document and is flagged as such. Asasi and other Diploma results (UiTM, private colleges) are <strong>not checked</strong> yet &mdash; read the document yourself. When the document looks like a different kind of results, or an SPM slip, the card
        says so and the student was shown a note; none of these stops her application. Since 27 October 2026 a higher result uploaded as her
        <strong> SPM slip</strong> is recognised too: the card says it is a higher result, not an SPM slip, nothing is compared with her SPM
        grades and she is never told to change them; where her page shows the higher-results card she is offered a one-tap move into it.</>,
    },
    {
      q: <>The Academic card says a grade <strong>could not be checked</strong>, or a ± difference needs <strong>checking by eye</strong>. Why is it not a tick or a red mark?</>,
      a: <>Since 13 November 2026 the SPM and STPM checks follow the same rules. When the read of her slip
        <strong> missed rows</strong> (for STPM: Pengajian Am was not read, or a row was not recognised), the card
        names the subjects it could not check, gives no tick, and the case stays at most <strong>Probable</strong>
        &mdash; read those grades on the slip yourself. When the SPM slip prints more subjects than the read caught,
        the card says so and gives no Subjects tick, even when every subject she entered was found. On an STPM slip
        the system read exactly (not by AI), a subject she entered that the slip does not print is a
        <strong> red</strong> difference, as it is for SPM; on an AI read it is named as not checked (amber), because
        the read may simply have skipped that row. When her STPM grade and the slip differ only
        by the <strong>+ or &minus;</strong> (A against A&minus;, B+ against B), the card shows it in amber and asks you to
        check it by eye, because the read can be wrong about a small sign; it stays red when the system read the
        slip&rsquo;s text exactly rather than by AI. A different letter is always red. A higher result she put
        in the SPM slip card no longer holds a clean Academic card back from <strong>Certain</strong> when her
        higher-results card is clean. And a course counts as a <strong>degree</strong> by the same test everywhere:
        if its name says it is a degree, she is asked for her higher results before she submits, even when an old
        Form Six pathway is saved with it. Three keep the earlier rule, with no new ask before submit: a PISMP pathway, a preparatory
        programme (&ldquo;Persediaan&rdquo;) and the &ldquo;American Degree Programme&rdquo; (spelt either way). A saved
        catalogue course decides by the course, not by its name. The award and the
        funding estimate treat every course as they did before. One change by the owner&rsquo;s ruling of
        14 November 2026: a <strong>PISMP</strong> student (the IPG teacher-training degree &mdash; a PISMP,
        &ldquo;Perguruan&rdquo; or &ldquo;Bachelor of Teaching&rdquo; programme, or an Institut Pendidikan Guru,
        IPG, IPGM or IPGK) who holds <strong>only SPM</strong> is never owed higher results, before or after she
        submits, so her Academic card is not held back for them. A PISMP student who has entered her STPM or
        Matriculation results is checked on them as before. An &ldquo;Ijazah Sarjana Muda Pendidikan&rdquo; at a
        university (such as UPSI) is not PISMP, even if a PISMP pathway is saved with it.</>,
    },
    {
      q: <>The Academic card says the student <strong>only has SPM results</strong>, or <strong>moved</strong> a slip between the results cards. What happened?</>,
      a: <>Before submitting, she either chose &ldquo;Continue with SPM results only&rdquo; &mdash; the STPM,
        Matriculation, Asasi or Diploma results she had entered were removed, her SPM results were kept, and
        she is now assessed on SPM &mdash; or moved an SPM slip she had put in the higher-results card into the
        SPM slot. The note gives the date (and, for the first, which results went and their CGPA). She may
        have been shortlisted on the results she removed: the shortlist was <strong>not</strong> run again, so
        judge the change yourself and ask at interview if it is unclear. Once an application is submitted
        these actions are closed &mdash; request any document you need instead. A higher result moved OUT of the SPM card (by her, or by the HalaTuju team on 26 October 2026) is noted the same way, naming the card it came from (the SPM card or the semester result).</>,
    },
    {
      q: <>Why did STPM students move up the list when I sort by <strong>merit</strong>?</>,
      a: <>The merit score is now <strong>out of 100 for every student</strong>. An SPM student&rsquo;s is
        worked out from her SPM grades and co-curriculum, exactly as before. An STPM student&rsquo;s used to be
        her CGPA as it stands (for example 3.70), so every STPM student sorted below every SPM student; it is
        now her overall CGPA ÷ 4 × 100 (3.70 shows as 92.5), the same conversion the course guide uses. Her
        CGPA itself has not changed: it has its own <strong>CGPA</strong> slot on the Academic card. A dash means there are no
        results to score yet &mdash; it is not a zero, and it always sorts last.</>,
    },
    {
      q: <>Where do I see what the student told us about their <strong>family</strong>?</>,
      a: <>In <strong>Family &amp; finances</strong>, under <strong>About your family</strong>: each family member
        the student listed, their occupation, who earns, any monthly income they declared, and why and since
        when someone is not working. These are the student&rsquo;s own answers, not checked facts. The
        <strong> Parent contact</strong> line above them is only the person we call &mdash; it is not the whole
        family. The small tick beside that name appears only when the name matches a parent&rsquo;s or
        guardian&rsquo;s IC the student uploaded; no tick means it does not match, or no such IC has been read.</>,
    },
    {
      q: <>What does the small blue <strong>tick</strong> beside a value mean?</>,
      a: <>That the value is backed by a document they uploaded. The <strong>school</strong> is ticked from their
        school-leaving certificate <strong>or their SPM results slip</strong> (the school where they sat SPM; the
        certificate is used first when both match); the slip&rsquo;s school is a tick only, never a chip in the
        Documents drawer. Their <strong>SPM grades</strong> are ticked from their SPM results slip (one tick after the
        subjects); their <strong>programme</strong>, <strong>institution</strong> and <strong>reporting date</strong> from
        their own offer letter &mdash; including when we filled them in from that letter for them. No tick means
        no such document has been read yet, or it shows something different; it is never a sign of a problem on
        its own. The school is always shown in capitals, as the documents print it. When they named no
        institution, the card shows the one on their offer letter.</>,
    },
    {
      q: <>I pressed <strong>Re-run</strong> on an old copy and it became the live one. Why?</>,
      a: <>Re-run on a copy under <strong>Old / Replaced</strong> reads it again and then compares it with the live
        copy for the same person and the same request, using the same rule as a new upload. If the old copy now
        reads better, it takes the live copy&rsquo;s place; if not, nothing changes. No other document moves.
        It does not compare offer letters, salary slips (an upload may file a salary slip as an EPF statement
        once it reads it), bank statements, income support documents or other documents, nor a copy the system
        marked as a sample: for those, ask the student to upload again, as before. It never brings back a copy older than the live one or an STR in
        a stranger&rsquo;s name, and does nothing once the case is decided. It also leaves a copy where it is when
        the copy names a different family member from the one it is filed under (say, an EPF statement filed
        under the father that reads the mother&rsquo;s name): check whose document it is.</>,
    },
    {
      q: <>What is the <strong>place-of-birth</strong> line beside the NRIC?</>,
      a: <>The state the student was born in (for example <em>Born: Perak</em>), read from the place-of-birth
        code in her IC number (the two digits in the middle). A gift can accept only students born in certain
        states; one born elsewhere, born outside Malaysia, with &ldquo;place of birth unknown&rdquo; (code 82), or
        whose IC number cannot be read does not pass that rule. The rule is checked again every time the case
        opens: if the IC number was changed after she applied and no longer meets it, a red <em>state</em> chip
        shows beside her status, and QC can accept the case only with a recorded reason. Where you are in doubt, request her birth
        certificate.</>,
    },
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
        on by default — you can <strong>opt out anytime</strong> on your Profile. Your <strong>home address is
        never shown to anyone</strong>, including the programme lead.</>,
    },
    {
      q: <>I need a break. How do I stop being given new students?</>,
      a: <>On <strong>My profile</strong>, in the <strong>Taking part</strong> card, tick <strong>Pause new
        cases</strong>. Nobody new will be assigned to you until you untick it. You don&rsquo;t need permission
        and nobody is judging — this is unpaid work and life happens.</>,
    },
    {
      q: <>If I pause, do I lose my account or the students I already have?</>,
      a: <>No. Pausing is <strong>not</strong> leaving: you keep your account, you can still sign in, and
        <strong> any interview already yours stays yours</strong> — please finish those, or tell the programme
        lead if you can&rsquo;t. Only <em>new</em> assignments stop.</>,
    },
    {
      q: <>Can somebody pause me without asking?</>,
      a: <>Your organisation admin can, and it is meant kindly — usually when someone has gone quiet and cases are
        waiting. It takes nothing away from you, and the same switch brings you back whenever you want.</>,
    },
    {
      q: <>What is the &ldquo;Student profile (draft)&rdquo;?</>,
      a: <>A short summary written automatically from the student&rsquo;s own application. A helpful starting point
        — always check it against the uploaded documents before relying on it.</>,
    },
    {
      q: <>How do I judge the Income check? It&rsquo;s the hardest one.</>,
      a: <>Two routes. <strong>STR route:</strong> the proof is an <em>approved</em> MySTR record — a
        <strong> SALINAN application-record is not proof</strong>, and nor is a page whose status only says
        &ldquo;Permohonan Diterima&rdquo; or &ldquo;Dalam Proses&rdquo; (incl. &ldquo;Dalam Proses Kelulusan&rdquo;;
        anyone can apply: the Status chip is red and the salary documents are judged instead; such a page
        never replaces an approved, rejected or amber STR already on file, and an approved STR whose name or IC
        number matches a family member&rsquo;s IC card is kept even against a rejection or an unread page uploaded
        for another family member; any other
        approved STR (someone outside the family, a parent whose IC is not uploaded yet, or a match found only
        through the birth certificate) holds no such place,
        so the usual order decides: a dated page first, then the newest), nor an application details page that lists the
        applicant&rsquo;s age and address with no status (red &ldquo;Not an STR document&rdquo;); if the status isn&rsquo;t clearly
        &ldquo;Lulus&rdquo;, ask for the MySTR Semakan Status / Dashboard, or the approval letter.
        <strong> Salary route:</strong> payslips / EPF, judged against the gift&rsquo;s own income cut-off, which has
        two tests: household income at most the gift&rsquo;s limit, and income per person at most its per-person
        limit. Usually passing either one is enough; a gift set to &ldquo;all of these&rdquo; needs both.
        Exactly on a limit counts as a pass. A household close to the cut-off
        (less than one person&rsquo;s share of the gift&rsquo;s limit to spare) shows amber, because one
        undeclared earner could tip it over. A gift with only one of the two limits is judged on that one.
        When it&rsquo;s genuinely borderline, that&rsquo;s what the interview is for — don&rsquo;t force a verdict on weak
        evidence.</>,
    },
    {
      q: <>What do the <strong>Problem</strong>, <strong>Check</strong> and <strong>Unread</strong> pills on a document mean, and what are the ticks and crosses?</>,
      a: <><strong>Problem</strong> (red) means at least one check on the document failed. <strong>Check</strong>
        (amber) means nothing failed but something needs your eye. <strong>Verified</strong> means every check is
        green, and <strong>Unread</strong> means nothing could be checked yet. A chip shows a tick (green),
        an exclamation mark (amber) or a cross (red); a grey chip has no symbol and means not checked yet, or
        nothing to compare. A plain value is the value shown with no colour. The drawer shows when the document was read (the year only when it is not
        this year), and the <strong>Checks</strong> panel beside an opened document lists every check with the
        full read and upload times. The reading is a starting point: a person decides.</>,
    },
    {
      q: <>What do the chips on a water or electricity bill mean, and where are the names and addresses?</>,
      a: <>A bill shows <strong>Type</strong>, <strong>Name</strong>, <strong>Address</strong> and
        <strong> Date</strong>, then the amount as a plain value. A wrong or incomplete type turns the other
        chips red. <strong>Name</strong> is green when the holder is the student or a family member, grey when
        the bill shows no name, and red when it is in an unrelated person&rsquo;s name.
        <strong> Address</strong> is green on a match, red on a mismatch and amber when it could not be
        checked. <strong>Date</strong> is green up to 3 months, amber from 3 to 6 months or when no date shows,
        and red over 6 months. Amber and red chips carry a one-line reason. Names and addresses are not in the
        drawer: open the bill and the <strong>Checks</strong> panel shows the bill beside the application, the
        date against the rule, and the amount, <strong>Reasonable</strong>, <strong>Outstanding</strong> and
        period as plain values, with the notes when only one of the two bills was given.</>,
    },
    {
      q: <>A row on an STR, payslip or EPF statement says <strong>Not read</strong>. And when does a parent&rsquo;s IC say <strong>Wrong card</strong>?</>,
      a: <><strong>Not read</strong> (grey) means we could not read one side of that check: either this document
        gave us nothing usable for that row, or the parent&rsquo;s IC it is checked against did not &mdash; a blank,
        or a stray mark such as a colon or a form label in place of a name. Nothing was compared, so there is no
        tick, and it never turns another document amber or red. If the family&rsquo;s IC numbers already link the
        documents (the birth certificate, the parent&rsquo;s IC and the income proof), the case is unaffected; read the
        name on the page yourself if you want to be sure. When a parent&rsquo;s IC and an income document really
        disagree, the red shows on the <strong>income document</strong>, not on the IC. The IC shows
        <strong> Wrong card</strong> only when its own number is far from the family member&rsquo;s number on the
        birth certificate, or its own details clearly clash with the birth certificate &mdash; usually another family
        member&rsquo;s card uploaded in that slot. This changes only what the chips show: the case&rsquo;s checks and
        verdict are worked out exactly as before.</>,
    },
    {
      q: <>How do I ask the student a question?</>,
      a: <>Use <strong>Raise a query</strong> or <strong>Request a document</strong>. They get an email; their
        reply shows in the <strong>Outstanding</strong> box. While the student is still completing their
        documents, a note takes the place of both: what they still owe is listed under <strong>Blockers</strong>,
        and they are already being asked for it. On an optional document (an EPF statement, a utility bill, a
        school-leaving certificate) the student may tap <strong>I don&rsquo;t have this</strong>: the ask closes
        and the reason shows in <strong>Outstanding</strong>.</>,
    },
    {
      q: <>What does &ldquo;Save verdict &amp; generate final profile&rdquo; do?</>,
      a: <>It records your decision and creates the final, polished profile — and sends the case on for
        <strong> QC</strong>. The student becomes visible to sponsors only once QC accepts it.</>,
    },
    {
      q: <>I approved, but it says &ldquo;NOT sent to QC — still missing&rdquo;. What is checked?</>,
      a: <>Your verdict is saved; the case just cannot go to QC yet. Once the student has submitted and the case
        is at interview, only what the student can still fix in the Action Centre is checked: the
        <strong> documents</strong>, the <strong>consent form</strong> and the <strong>guardian&rsquo;s
        documents</strong>. The line names which one is missing. The interest quiz, the story, the address, the
        family details and the funding answers are not checked again then, because the student can no longer
        change them. Before the interview stage (a case not submitted yet, or one still waiting for its
        interview) everything is still checked in full.</>,
    },
    {
      q: <>What&rsquo;s the difference between rating Pass/Fail and approving?</>,
      a: <>The <strong>Pass/Fail</strong> on each fact records whether <em>that fact is right for the student</em>.
        <strong> Approve / Decline</strong> is your actual recommendation. They&rsquo;re separate: you can Pass all
        four facts and still <strong>Decline</strong> — for instance, income verified but above the gift&rsquo;s income cut-off.
        A Pass or Fail tap records the student&rsquo;s fact; it does not rate the AI. You are assessing
        the student: mark <strong>Pass</strong> if this fact is true for them, and <strong>Fail</strong> if it is
        not true or not proven. Every Fail asks <strong>Why?</strong>, with
        <em> Other</em> already chosen; change it if a better reason fits. If you Approve
        while a fact is on Fail, you see a warning, but you can still go ahead. QC then takes a second look at
        those facts (a Fail on a green fact, or a Fail you still approved) and may give their own
        <strong> Pass</strong> or <strong>Fail</strong>; it is optional. Your decisions are counted as QC accepted or QC sent back; leads see
        those counts, to support reviewers, not to rank them. You do not see the AI prediction card yourself.</>,
    },
    {
      q: <>What does each of the four facts ask me to prove?</>,
      a: <><strong>Identity</strong>: the student is who they say they are. <strong>Results</strong>: the results
        are real. <strong>Pathway</strong>: a real offer for a course this programme funds (a public IPTA or ILKA,
        the right start year, not already funded, not abroad). <strong>Income</strong>: the family is within the
        gift&rsquo;s own income cut-off (household income at most the gift&rsquo;s limit, or, above that, income
        per person at most its per-person limit).</>,
    },
    {
      q: <>Which reasons can I give when I <strong>Fail</strong> a fact?</>,
      a: <>Five, all about the student, never the AI: <em>Proof is missing/unclear</em>, <em>Document looks
        false/altered</em>, <em>Document(s) show something different</em>, <em>Interview revealed something
        different</em>, and <em>Other</em>. Every Fail takes one; <em>Other</em> is chosen for you until
        you pick another.</>,
    },
    {
      q: <>Why is <strong>Approve</strong> greyed with &ldquo;Record the reporting date&rdquo;?</>,
      a: <>A recommendation needs the date the student reports to her course. When the reporting-date box shows
        and no date is saved, enter it in that box (the <strong>Still to do</strong> line takes you there). Decline
        needs no date. If the offer letter&rsquo;s date can be read and is already saved, the box does not show and
        nothing is asked. A letter whose date cannot be read (only a month and year, say) still shows the box.</>,
    },
    {
      q: <>Can QC accept my recommendation while a fact is red?</>,
      a: <>Not without a reason. While a fact is still red or shows <em>Rule not met</em>, QC&rsquo;s Accept is
        blocked; QC can resolve it, reopen it to you, or record a reason for going ahead, which is kept on the
        case.</>,
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
      q: <>When is the student asked to pick her course?</>,
      a: <>Only when her offer letter does not match <strong>one</strong> course in our list (owner&rsquo;s ruling,
        18 November 2026). When the letter names exactly one course, nothing is asked: if she had not chosen a
        course, the letter&rsquo;s course is recorded for her; if she named up to three top choices while waiting
        for offers and the letter is for another course, that is fine too. She is asked &ldquo;is this your final
        pathway?&rdquo; only when she picked one course herself and the letter is for a different one. A course
        name with options in brackets (&ldquo;Sains Kemasyarakatan [Ekonomi / Sains Politik / &hellip;]&rdquo;)
        matches a letter naming the course alone or with one of those options. For an STPM or diploma student
        with no offer letter yet, the Pathway card shows the degree she named as context.</>,
    },
    {
      q: <>A card is red. How do I tell <strong>&ldquo;Can&rsquo;t verify&rdquo;</strong> from <strong>&ldquo;Rule not met&rdquo;</strong>?</>,
      a: <>Read the word under the card name. <strong>Can&rsquo;t verify</strong> means proof is missing or
        unreadable: ask for it or read the document yourself. <strong>Rule not met</strong> means a gift rule is
        broken (income above the gift&rsquo;s income cut-off, a fully funded or overseas programme, a course starting outside the
        allowed years, an offer from a private college or university (IPTS), or an offer that is not official). A card with a broken rule is always red, even when its
        status is Review. The legend under the cards explains both.</>,
    },
    {
      q: <>The Pathway card is red with <strong>&ldquo;Fully funded or overseas programme&rdquo;</strong>. Why?</>,
      a: <>Her chosen programme is the <strong>American Degree Program</strong> under MARA, which is fully funded,
        or a preparation programme for study abroad (&ldquo;Program Persediaan &hellip; Luar Negara&rdquo;, run by
        MARA, JPA or another sponsor). This gift supports neither (owner&rsquo;s ruling, 14 November 2026). It works like income above the
        gift&rsquo;s income cut-off: the case is flagged and the usual recommendation is to decline, but it is not declined for you
        and the amount is unchanged. Confirm at interview &mdash; if she is in fact on a different programme,
        say so in your conclusion. The &ldquo;American Degree Transfer Program&rdquo; and an ordinary
        &ldquo;Degree Programme&rdquo; are not affected.</>,
    },
    {
      q: <>The Pathway card is red with <strong>&ldquo;Offer from a private college or university (IPTS)&rdquo;</strong>. Why?</>,
      a: <>HalaTuju supports public courses only, so an offer letter from a private college or university (an
        IPTS) breaks the rule for every gift (owner&rsquo;s ruling, 18 November 2026). That includes a public
        university&rsquo;s private wing, such as UTM SPACE, a Pendidikan Berterusan centre, UM&rsquo;s Saluran
        Terbuka (SATU), UMS PPPL or a Sdn Bhd operator, and named private bodies such as KPTM, UniKL and GMI. We
        flag it when the letter names one of these, or when our document check called the letter an IPTS offer
        and the institution on it is not a public one we know. It works like the other broken rules: the case is
        flagged and the usual recommendation is to decline, but it is not declined for you, the amount is
        unchanged, and the student is not told or asked anything new. If the letter is in fact from a public
        institution, say so in your conclusion: a wrong flag helps us improve the check.</>,
    },
    {
      q: <>The Pathway card is red with <strong>&ldquo;Course started in &hellip;&rdquo;</strong>. Why?</>,
      a: <>Some gifts accept only students whose course started in certain years (for example 2025 and
        2026). The start year is read from her offer letter only, never from a date typed on the application:
        first the letter&rsquo;s reporting date; if it has none, a single year on the intake line; if it shows
        a session, a plain year straight after an intake word counts only when it is one of the
        session&rsquo;s two years (&ldquo;Ambilan 2023 Sesi 2025/2026&rdquo; is left for you to check: 2023 may
        name a group of school leavers, not her intake); otherwise the session&rsquo;s first year (&ldquo;2024/25&rdquo; means 2024), or its second year
        when it says Sesi 2, Sesi II, Semester 2, Semester II or Ambilan 2. A month or date beside the
        session is never ignored. It counts only after an admission phrase (Tarikh Kemasukan, Tarikh
        Mendaftar, Tarikh Pendaftaran, Lapor Diri, Ambilan, Pengambilan, Kemasukan, Intake, Admission, Date
        of Registration, Date of Admission; an admission number such as &ldquo;No. Kemasukan&rdquo; is not
        one): a full date inside the session gives its year (&ldquo;Tarikh Kemasukan:
        10/03/2025&rdquo; means 2025), and a month with no year, on a line with such a phrase and no event
        or deadline word (cuti, exam, ujian, yuran, tutup, bertarikh, dikemaskini, hingga, tamat, until and
        the like), gives the second year for
        January to April and the first for May to December (&ldquo;Ambilan Sesi 2024-25 Mac&rdquo; means 2025).
        Words such as mulai, bermula, commencing or Semester start nothing. Any other month or date on that
        line (&ldquo;Sesi 2024/2025 bermula Februari&rdquo;, a closing or letter date, a date with no year or
        a two-digit year such as &ldquo;16 Feb 25&rdquo;) makes it unclear. A plainly misspelt month
        (&ldquo;Febuary&rdquo;, &ldquo;Febuari&rdquo;, &ldquo;Agust&rdquo;) counts as that month. An unclear date is left for
        you to check. So is a reporting date with no full year (&ldquo;16 Februari&rdquo;). An exam year (SPM, STPM, SKM,
        MUET and the like, also &ldquo;SPMs&rdquo; or &ldquo;SPMleavers&rdquo;) is never taken as the start year. It is left for you to check when the letter names a later semester or
        year (Year 2, Semester 3, final year, Upper Six, &ldquo;Part 4&rdquo;), even in the programme name;
        says readmission or credit transfer; is a confirmation letter that does not name her intake (Year 1,
        Lower Six, or an intake month and year: &ldquo;Semester 1&rdquo; is only her current semester); has
        several years, or only an exam year, and no reporting date; or has a misprinted year
        (&ldquo;2O25&rdquo;). Nothing is shown until the letter has been read. Hers
        is outside the gift&rsquo;s years, so the case is flagged like income above the gift&rsquo;s income cut-off: the usual
        recommendation is to decline, but it is not declined for you and the amount is unchanged. Confirm at
        interview. She sees a short line on her offer letter card naming the gift&rsquo;s years; it tells her a
        reviewer still decides. If the line says instead that the start year <strong>could not be read</strong>, nothing is
        flagged: check the year on the letter yourself.</>,
    },
    {
      q: <>Why was the student asked for a <strong>recent confirmation letter</strong>?</>,
      a: <>Her confirmation-of-studies letter (not an offer letter) is older than your organisation&rsquo;s window (6 months unless
        your organisation admin changed it under Organisation settings) and her course should already have
        started, so the system asked her for her offer letter or a recent confirmation-of-studies letter. It is only a request: it never blocks the case, never fails a check, never changes the
        verdict or the amount, and the case does not wait for it &mdash; it can be assigned to a reviewer while
        this request is still open (other open requests still hold the case until her answer window ends).
        It is not asked when the letter&rsquo;s date cannot be read, while the reporting date on the letter is
        still to come (or cannot be read and may still be to come), or when a recent confirmation letter is already
        on file (from any institution). It is never asked when she has an offer letter on file: a confirmation letter only stands in for a missing offer letter.
        Her upload of an offer letter or a recent confirmation letter closes it; an old confirmation letter sent again leaves it open.
        To close it for good without a letter, use Waive, not Resolve: Resolve lets the next sync re-open it
        and email the student again.</>,
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
        not a script: ask your own too, and jot <strong>one line</strong> per point before you submit. Every
        point needs an answer — <strong>Resolved</strong>, a short note (even &ldquo;See conclusion&rdquo;), or
        <strong> Delete</strong> — or the submit is refused and Approve and Decline stay greyed out. Press either greyed button and the <strong>Still to do</strong> list names what is missing and links to it.</>,
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
        confirmation, plus reminders the day before and an hour before. The Guide&rsquo;s <strong>Scheduling the
        interview</strong> steps show each screen.</>,
    },
    {
      q: <>What if the student needs a different time, or doesn&rsquo;t book?</>,
      a: <>They can <strong>reschedule or cancel</strong> up to a few hours before, and you&rsquo;ll see the
        change. If they cancel, just propose fresh times.</>,
    },
    {
      q: <>The student stops responding, or tells me they no longer want the scholarship. What do I do?</>,
      a: <>Write it in your <strong>interview findings</strong>, such as &ldquo;Did not attend twice&rdquo;.
        Answer or delete each agenda item, and mark the four facts Pass or Fail. Then select
        <strong> Decline</strong> and submit. The decline goes to <strong>Quality
        check</strong> like any other. Nobody can decline a case at this stage without QC, and it cannot be
        closed instead: Close works before an award only at Submitted and Recommended.</>,
    },
    {
      q: <>What is <strong>Org admin and reviewer notes</strong> on a student&rsquo;s page?</>,
      a: <>A conversation between you and your organisation admin about this student: the points they would like
        you to explore, and your replies (<strong>Reply</strong>, then <strong>Send reply</strong>). You can write
        until you record your recommendation.
        A <strong>New note</strong> mark by the student&rsquo;s name means your org admin has written since you
        last opened the page. The student and sponsors never see the notes, and they are not used in the
        AI-written profile.</>,
    },
]
