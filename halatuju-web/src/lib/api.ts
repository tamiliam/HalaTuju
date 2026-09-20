/**
 * API client for HalaTuju Django backend.
 *
 * ⚠ THIS FILE IS A BARREL AND HOLDS NO CODE (code health H13). Every name below is declared
 * in `src/lib/api/`, one module per domain, and re-exported from here so that **every import
 * of `@/lib/api` anywhere in the app keeps working unchanged**. Nothing was renamed, reworded
 * or reshaped in the split — the bodies were cut by line range from this file's own bytes.
 *
 * WHERE TO ADD A NEW CALL: in the module that owns its domain, then one line here. Do not put
 * code back in this file — it is 4-figure lines' worth of history that the oversize ledger in
 * `code-standards.json` now holds at the barrel's size, and the ledger only ratchets down.
 *
 * ⚠ `apiRequest` and `ApiOptions` stay PRIVATE to the folder (`./api/client`) — they are not
 * re-exported here, because they were not exported before. `api/client.ts` is NOT the same
 * helper as `admin-api/client.ts`: this one raises `nric-required` and carries DRF field
 * errors, and the two are deliberately kept apart.
 */
// The student: who they are, claiming an NRIC, verifying a phone or an e-mail.
export {
  claimNric, sendClaimCode, confirmClaimCode, sendVerificationEmail, sendPhoneVerification,
  checkPhoneVerification, getProfile, updateProfile, syncProfile,
} from './api/profile'
export type { StudentProfile, SyncProfileData } from './api/profile'

// The course catalogue, the search, and a student's saved list.
export {
  searchCourses, checkEligibility, getCourses, getCourse, getInstitutions, getSavedCourses,
  saveCourse, unsaveCourse, updateSavedCourseStatus,
} from './api/courses'
export type {
  EligibleCourse, Course, Institution, MascoOccupation, CourseRequirements, InsightsStreamItem,
  InsightsFieldItem, InsightsLevelItem, Insights, SearchCourse, AliranOption, SearchFilters,
  SearchParams, SavedCourseWithStatus,
} from './api/courses'

// The interest quiz, the ranked results, the reports, and applying elsewhere.
export {
  getQuizQuestions, submitQuiz, getRankedResults, generateReport, getReport, getReports,
  getOutcomes, updateOutcome, deleteOutcome,
} from './api/guidance'
export type {
  QuizQuestion, QuizAnswer, QuizResult, RankedCourse, RankingResult, GenerateReportResponse,
  ReportDetail, ReportListItem, OutcomeStatus, AdmissionOutcome,
} from './api/guidance'

// The sponsor's own portal — account, terms, pool, wallet, students, impact.
export {
  getSponsorTerms, getSponsorTermsQuiz, acceptSponsorTerms, getSponsorMe,
  patchSponsorNotifications, registerSponsor, getSponsorReferrals, createSponsorReferral,
  getSponsorPool, getSponsorPoolDetail, getMyStudentDetail, getSponsorWallet, fundStudent,
  getSponsorImpact, getSponsorActivity, getSponsorCommunity, getSponsorStatement,
  getSponsorTrust, getSponsorStandingGift, putSponsorStandingGift, getStudentsWaitingCount,
} from './api/sponsor'
export type {
  SponsorAccount, SponsorTermsDocument, SponsorTermsCheckpoint, SponsorReferral, SponsorPoolCard,
  SponsorPoolDetail, SponsorSponsorship, SponsorSpending, SponsorMyStudentDetail, SponsorWallet,
  SponsorImpact, SponsorActivityEvent, SponsorCommunity, SponsorStatement, TrustTrustee,
  TrustFigure, SponsorTrust, SponsorStandingGift,
} from './api/sponsor'

// A student already on the programme: results, 18+ consent, graduation.
export {
  getSemesterResults, addSemesterResult, getPromotionalConsent, setPromotionalConsent,
  getGraduationMessages, submitGraduationMessage, getSponsorGraduationMessages,
} from './api/inProgramme'
export type {
  SemesterResult, PromotionalConsentState, GraduationMessage, GraduationRelayMessage,
} from './api/inProgramme'

// The STPM/Form-6 arm: eligibility, ranking, its own quiz and its own search.
export {
  checkStpmEligibility, rankStpmCourses, getStpmQuizQuestions, resolveStpmQuizQ3Q4,
  submitStpmQuiz, searchStpmCourses, getStpmCourseDetail,
} from './api/stpm'
export type {
  StpmEligibleCourse, StpmEligibilityRequest, StpmEligibilityResponse, StpmRankedCourse,
  StpmRankingRequest, StpmResultFraming, StpmRankingResponse, StpmQuizQuestion,
  StpmQuizQuestionsResponse, StpmQuizResolveResponse, StpmQuizSubmitResponse, StpmSearchParams,
  StpmSearchFilters, StpmSearchResponse, SubjectGroupDisplay, StpmRequirements,
  StpmInstitutionDetail, StpmCourseDetail,
} from './api/stpm'

// Stateless, public sums — merit, CGPA, pathways — and the field taxonomy.
export {
  fetchFieldTaxonomy, calculateMerit, calculateCgpa, calculatePathways,
} from './api/calculations'
export type { FieldTaxonomyEntry, MeritResult, CgpaResult, PathwayResult } from './api/calculations'

// The bursary application itself, and the intake it is made against.
export {
  submitScholarshipApplication, getMyScholarshipApplications, getScholarshipIntake,
  getScholarshipApplication, updateScholarshipDetails, switchIncomeRoute,
  confirmScholarshipApplication,
} from './api/application'
export type {
  FundingNeed, ApplicationCompleteness, ApplicationRequirements, ScholarshipApplication,
  IntakeChoice, ApplyCopyBlock,
} from './api/application'

// Interview scheduling, from the student's side.
export {
  getInterview, bookInterviewSlot, cancelInterview, requestInterviewAlternatives,
  sendInterviewMessage,
} from './api/interview'
export type { InterviewSlot, InterviewMessage, InterviewSchedule } from './api/interview'

// Uploads, every per-document check the reader returns, referees and consent.
export {
  signUploadDocument, uploadFileToSignedUrl, recordDocument, listDocuments, deleteDocument,
  getDocumentHelp, getIncomeHelp, listReferees, addReferee, getConsentStatus, recordConsent,
} from './api/documents'
export type {
  ApplicantDocument, BcCheck, GuardianshipCheck, SupportDocCheck, StrCheck, IncomeIcCheck,
  IncomeProofCheck, UtilityCheck, SlipCheckStatus, AcademicCheck, SemesterCheck,
  SchoolLeavingCheck, PathwayCheck, Referee, ConsentStatus, DocumentLimits, GradeDiff,
  DocumentHelp,
} from './api/documents'

// The Student Action Centre — what we asked for and what came back.
export { getResolutionItems, resolveResolutionItem } from './api/resolution'
export type { ResolutionItem } from './api/resolution'

// Payout account, the comprehension quiz, and the guarantor's phone PIN.
export {
  getBankAccount, confirmBankAccount, getComprehensionQuiz, recordComprehensionPass,
  sendGuarantorPin, checkGuarantorPin,
} from './api/bank'
export type { BankAccount, ComprehensionCheckpoint, ComprehensionQuizData } from './api/bank'

// The offer, the bursary agreement, and onboarding once it is accepted.
export { getStudentAward, respondToAward, getBursaryAgreement, submitOnboarding } from './api/award'
export type { StudentAward, BursaryPreview, BursaryAgreement } from './api/award'
