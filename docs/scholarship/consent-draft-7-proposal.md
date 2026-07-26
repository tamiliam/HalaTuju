# Sponsor-sharing consent — proposed `2026-draft-7`

**Status:** IMPLEMENTED on branch `feat/consent-draft-7` (2026-07-26) — **NOT merged, NOT pushed.**
Awaiting lawyer review and the matching contract clause. The wording below is what is in the branch.

**Owner decisions taken during implementation (2026-07-26):**
- **Spending is stated broadly** — "how the bursary was spent", no category limit. The mechanism is
  still being designed, and a later NARROWING needs no re-consent where a broadening would.
- **ONE displayed version.** Per-version archived bodies were built (18 strings, recovered from git
  history for draft-3/5/6) and then REMOVED. Both the form and the "What you agreed to" panel render
  the current wording, so an earlier consenter sees today's slightly broader text. Accepted
  knowingly; questions handled by hand. TD-166 is marked ACCEPTED, not resolved.
- **No version gate, no re-prompt, no per-student behaviour.** `pool.has_active_share_consent` stays
  version-blind, so any new disclosure reaches every consenter once it ships. That makes each new
  disclosure an owner decision at feature level — noted in §4 below.

**Why:** the current consent (`2026-draft-6`) describes a one-off disclosure *for selection*
("so they can consider me"), but the sponsor relationship continues after that. Two things are
already or soon shown that its closed list does not cover:

1. **Academic progress — already live.** A sponsor of a funded student sees a band derived from the
   student's CGPA (`on_track` / `semester_completed` / `needs_attention` at CGPA ≤ 2.0 / `graduated`)
   plus semesters supported. "Course" and "study plans" arguably do not stretch to how well they are
   doing.
2. **Bursary spending — planned.** `docs/plans/2026-07-18-bursary-spend-reporting-brief.md`. Its own
   governance gate stops the sponsor panel until this consent (and the agreement) permit it.

---

## 1. Current wording (`2026-draft-6`, live)

**EN adult** — `scholarship.consent.text`:

> I, the named applicant (**{student_name}**, NRIC **{student_nric}**), consent to the
> **{programmeName} Programme** sharing an **anonymised summary** of my application with potential
> sponsors, so they can consider me for financial assistance.
>
> Sponsors are **not** shown my name, NRIC, photograph, address or contact details — nor my
> parents' — and **my documents are never shared with them**. They see only my state, school,
> course, study plans and financial need.
>
> I understand I can withdraw this consent at any time.

`textMinor` is the same three paragraphs in the parent's voice.

## 2. Proposed wording (`2026-draft-7`)

Owner-drafted structure (heading + two phase bullets), with the enumerated never-list retained from
draft-6 — a closed list is checkable where "identifying personal information" is a category the
reader must interpret, and it is the enumeration that extends the protection **to the parents**
(32 of 83 active consents were given by a guardian).

**Spending is stated broadly ("how the bursary was spent") by owner decision 2026-07-26**, because
the sharing mechanism is still being designed. This is the cheaper direction: a later NARROWING (to
category aggregates only) needs no re-consent, where starting narrow and broadening would send us
back to all 83. The specific reassurance — never individual purchases or shops — belongs in the UI
help text, which can be precise without binding the consent.

**As implemented, the bullets read exactly:**
`• Prior to selection: My state, school, course of study, plans, and financial need.`
`• During sponsorship: My academic progress, and how the bursary was spent.`

### EN — adult (`scholarship.consent.text`)

> I, **{student_name}** (NRIC: **{student_nric}**), consent to the **{programmeName} Programme**
> sharing an **anonymised summary** of my application with prospective sponsors to evaluate me for
> financial support.
>
> Sponsors never see my name, NRIC, photograph, address or contact details — nor my parents' — and
> never see my documents.
>
> **Information Shared with Sponsors:**
> • Prior to selection: My state, school, course of study, plans, and financial need.
> • During sponsorship: My academic progress, and how the bursary was spent.
>
> I understand that I may withdraw this consent at any time.

### EN — minor (`scholarship.consent.textMinor`)

> I confirm that I am the parent or guardian of **{student_name}** (NRIC: **{student_nric}**), who
> is under 18 years old.
>
> I consent to the **{programmeName} Programme** sharing an **anonymised summary** of
> {his_or_her} application with prospective sponsors to evaluate {him_or_her} for financial support.
>
> Sponsors never see {his_or_her} name, NRIC, photograph, address or contact details — nor ours —
> and never see {his_or_her} documents.
>
> **Information Shared with Sponsors:**
> • Prior to selection: State, school, course of study, plans, and financial need.
> • During sponsorship: Academic progress, and how the bursary was spent.
>
> I understand that I may cancel this consent at any time.

*(The bullets drop the possessive pronoun deliberately: `{his_or_her}` has no capitalised variant,
and a sentence-initial placeholder would render lower-case in all three languages.)*

### MS — adult

> Saya, **{student_name}** (NRIC: **{student_nric}**), bersetuju supaya **Program {programmeName}**
> berkongsi **ringkasan tanpa nama** mengenai permohonan saya dengan bakal penaja untuk menilai saya
> bagi bantuan kewangan.
>
> Penaja tidak sekali-kali melihat nama, NRIC, gambar, alamat atau butiran perhubungan saya —
> mahupun ibu bapa saya — dan tidak sekali-kali melihat dokumen saya.
>
> **Maklumat yang Dikongsi dengan Penaja:**
> • Sebelum pemilihan: Negeri, sekolah, kursus pengajian, rancangan dan keperluan kewangan saya.
> • Semasa penajaan: Kemajuan akademik saya, dan cara biasiswa itu dibelanjakan.
>
> Saya faham bahawa saya boleh menarik balik persetujuan ini pada bila-bila masa.

### MS — minor

> Saya mengesahkan bahawa saya ialah ibu bapa atau penjaga kepada **{student_name}**
> (NRIC: **{student_nric}**), yang berumur bawah 18 tahun.
>
> Saya bersetuju supaya **Program {programmeName}** berkongsi **ringkasan tanpa nama** mengenai
> permohonan {his_or_her} dengan bakal penaja untuk menilai {him_or_her} bagi bantuan kewangan.
>
> Penaja tidak sekali-kali melihat nama, NRIC, gambar, alamat atau butiran perhubungan
> {his_or_her} — mahupun kami — dan tidak sekali-kali melihat dokumen {his_or_her}.
>
> **Maklumat yang Dikongsi dengan Penaja:**
> • Sebelum pemilihan: Negeri, sekolah, kursus pengajian, rancangan dan keperluan kewangan.
> • Semasa penajaan: Kemajuan akademik, dan cara biasiswa itu dibelanjakan.
>
> Saya faham bahawa saya boleh membatalkan persetujuan ini pada bila-bila masa.

### TA — adult *(first draft — owner review required)*

> நான், **{student_name}** (NRIC: **{student_nric}**), நிதி உதவிக்கு என்னை மதிப்பிடும் பொருட்டு,
> எனது விண்ணப்பத்தின் **அடையாளம் நீக்கப்பட்ட சுருக்கத்தை** சாத்தியமான ஆதரவாளர்களுடன்
> **{programmeName} திட்டம்** பகிர்ந்துகொள்ள சம்மதிக்கிறேன்.
>
> எனது பெயர், NRIC, புகைப்படம், முகவரி அல்லது தொடர்பு விவரங்கள் — எனது பெற்றோருடையவையும் —
> ஆதரவாளர்கள் ஒருபோதும் காண்பதில்லை; எனது ஆவணங்களையும் ஒருபோதும் காண்பதில்லை.
>
> **ஆதரவாளர்களுடன் பகிரப்படும் தகவல்:**
> • தேர்வுக்கு முன்: எனது மாநிலம், பள்ளி, படிப்பு, திட்டங்கள் மற்றும் நிதித் தேவை.
> • ஆதரவு வழங்கப்படும்போது: எனது கல்வி முன்னேற்றம், மேலும் உதவித்தொகை எவ்வாறு செலவிடப்பட்டது.
>
> எந்த நேரத்திலும் இந்தச் சம்மதத்தைத் திரும்பப் பெறலாம் என்பதை நான் அறிவேன்.

### TA — minor *(first draft — owner review required)*

> நான் **{student_name}**-இன் (NRIC: **{student_nric}**) பெற்றோர் அல்லது பாதுகாவலர் என்பதை
> உறுதிப்படுத்துகிறேன்; அவர் 18 வயதுக்குக் கீழ்.
>
> நிதி உதவிக்கு {him_or_her} மதிப்பிடும் பொருட்டு, {his_or_her} விண்ணப்பத்தின்
> **அடையாளம் நீக்கப்பட்ட சுருக்கத்தை** சாத்தியமான ஆதரவாளர்களுடன் **{programmeName} திட்டம்**
> பகிர்ந்துகொள்ள அனுமதி அளிக்கிறேன்.
>
> {his_or_her} பெயர், NRIC, புகைப்படம், முகவரி அல்லது தொடர்பு விவரங்கள் — எங்களுடையவையும் —
> ஆதரவாளர்கள் ஒருபோதும் காண்பதில்லை; {his_or_her} ஆவணங்களையும் ஒருபோதும் காண்பதில்லை.
>
> **ஆதரவாளர்களுடன் பகிரப்படும் தகவல்:**
> • தேர்வுக்கு முன்: மாநிலம், பள்ளி, படிப்பு, திட்டங்கள் மற்றும் நிதித் தேவை.
> • ஆதரவு வழங்கப்படும்போது: கல்வி முன்னேற்றம், மேலும் உதவித்தொகை எவ்வாறு செலவிடப்பட்டது.
>
> இந்த அனுமதியை எந்த நேரத்திலும் ரத்து செய்யலாம் என்பதை நான் புரிந்துகொள்கிறேன்.

Established vocabulary is reused from draft-6 so this reads as a revision, not a re-translation:
`ringkasan tanpa nama` / `bakal penaja` / `butiran perhubungan` / `persetujuan`;
`அடையாளம் நீக்கப்பட்ட சுருக்கம்` / `ஆதரவாளர்கள்` / `தொடர்பு விவரங்கள்` / `சம்மதம்`.

---

## 3. Renderer constraint

`ScholarshipConsent.renderRich` understands **only** `**bold**` — no markdown lists — but it
preserves newlines. The bullets above therefore use a literal `•` character, which renders correctly.
A `- ` would render as a literal hyphen.

## 4. What must travel with the change (one release)

This is a **WIDENING**, which reverses the draft-6 precedent (that one narrowed, so no re-consent was
needed). Nothing here should ship piecemeal.

1. **Lawyer review.** The consent is the legal artefact and this adds ongoing financial visibility.
2. **The contract clause.** As it stands, `2026 BPB Student Agreement Final 240726` obliges the
   student to evidence use of funds **to the Donor** (= the Foundation; `counterparty_name` is
   currently Suresh Thirugnanam), and its Confidentiality clause bars onward disclosure absent
   written agreement. There is no clause permitting reporting to a sponsor. Both documents change
   together or neither does.
3. **Bump `CONSENT_VERSION` → `2026-draft-7`** (`services.py`).
4. **Re-consent — owner's operational call, NOT enforced in code.** Active `share_with_sponsors`
   consents: **83** — draft-3: 19, draft-5: 61, draft-6: 3. **49 are already sponsor-visible**
   (`recommended`+). **32 were given by a guardian**, so those need the parent again, not the student.
   Because visibility is version-blind, nothing breaks if re-consent never happens — and nothing
   protects those 80 either. Decide per new disclosure whether to hold it back until re-consent.
5. ~~Resolve TD-166~~ — **built, then removed by owner decision.** One displayed version; TD-166 is
   marked ACCEPTED. `consentText.test.ts` fails if an `archive` block reappears, so reversing this is
   a decision, not a quiet edit.
6. **UI help text** carrying the reassurance the legal text now omits — that sponsors see spending
   grouped, never individual purchases or shops.

## 5. Open question for the owner

Whether spending should instead be a **separate, voluntary consent** (`spend_reporting`), on the
`promotional_use` pattern — declinable without affecting the bursary. Considered and set aside on
2026-07-26 in favour of the broad single consent; recorded here because it remains the option that
best preserves a student's ability to take the money without accepting financial visibility.
