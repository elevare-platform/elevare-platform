// The guided tours. Each step points at an element that carries a matching data-tour
// attribute. A step whose element is not on the page (the profile banner once the
// profile is complete) is left out of the tours that skip missing elements.

export const tourSelector = (target) => `[data-tour="${target}"]`

// ─── Employer, part 1: the dashboard ──────────────────────────────────────────

export const EMPLOYER_STEPS = [
  {
    target: 'profile-banner',
    title: 'Finish your company profile',
    description:
      'Your company profile needs to be complete before you can post a job. It only takes a few minutes.',
    side: 'bottom',
    align: 'start',
  },
  {
    target: 'post-job',
    title: 'Post a job',
    description:
      'Start here. Write the job and publish it when you are ready. Your company profile needs to be complete and your company verified before a job can go live.',
    side: 'bottom',
    align: 'end',
  },
  {
    target: 'tab-talent-pipeline',
    title: 'Talent pool',
    description:
      'Keep candidates you source yourself in one place. Score them against your open roles and move the best ones forward.',
    side: 'right',
    align: 'start',
  },
  {
    target: 'tab-ai-recommendations',
    title: 'Candidate search',
    description:
      'Search candidates in plain words, or filter by skills, experience and location. Results are ranked and say why each person matches.',
    side: 'right',
    align: 'start',
  },
  {
    target: 'tab-cv-parser',
    title: 'Read CVs',
    description:
      'Upload CVs and Elevare reads them and fills in the candidate details, so you do not type them in.',
    side: 'right',
    align: 'start',
  },
  {
    target: 'tab-billing',
    title: 'Credits and billing',
    description:
      'See your plan, your credits, and every credit used or refunded. Introductions and interviews use credits.',
    side: 'right',
    align: 'start',
  },
  {
    target: 'manage-jobs',
    title: 'Manage your jobs',
    description:
      'Open your jobs to edit, publish or close a listing. Each job has a View Applicants button. Next, a short look at that page using an example job.',
    side: 'top',
    align: 'start',
    nextLabel: 'See an example job',
    // Moves on to the example job page instead of ending the tour.
    handoff: true,
  },
]

// ─── Employer, part 2: an example job with made-up candidates ─────────────────
// `view` says what the example page should show while the step is on screen.

export const EXAMPLE_JOB_STEPS = [
  {
    target: 'example-banner',
    title: 'An example job',
    description:
      'This is an example job with made-up candidates, so you can see how it works. Nothing here is real, nothing is sent and no credits are used.',
    side: 'bottom',
    align: 'start',
    view: { tab: 'applicants', reasoning: false, dialog: false },
  },
  {
    target: 'example-applicants',
    title: 'Applicants',
    description:
      'Everyone who applies to your job appears here, with where they live, their experience and when they applied. Use Move to take each person through the stages, from Reviewing to Shortlisted to Hired.',
    side: 'top',
    align: 'start',
    view: { tab: 'applicants', reasoning: false, dialog: false },
  },
  {
    target: 'example-score',
    title: 'AI score',
    description:
      'Elevare reads each CV and scores how well the person fits this job. Press the score to see the reasons, with strengths and gaps. It shows how closely their experience matches the role. It is not a pass or fail.',
    side: 'top',
    align: 'start',
    view: { tab: 'applicants', reasoning: true, dialog: false },
  },
  {
    target: 'example-upload',
    title: 'Upload CVs and score them',
    description:
      'Have CVs of your own, from an agency or an email? Upload them from the Talent Pool. Each CV is read and scored against this job, and the results appear on this tab.',
    side: 'bottom',
    align: 'end',
    view: { tab: 'pipeline', reasoning: false, dialog: false },
  },
  {
    target: 'example-pipeline-rows',
    title: 'Scores arrive as CVs are read',
    description:
      'A CV that is still being read has no score yet. It shows its score here as soon as it is done. Press a name to see the full profile.',
    side: 'top',
    align: 'start',
    view: { tab: 'pipeline', reasoning: false, dialog: false },
  },
  {
    target: 'example-interview-list',
    title: 'Interview list',
    description:
      'Add the people you want to interview from Applicants, Talent Pipeline or AI Talent Matches, using the calendar button. They collect here.',
    side: 'top',
    align: 'start',
    view: { tab: 'interviews', reasoning: false, dialog: false },
  },
  {
    target: 'example-send-interviews',
    title: 'Send AI interviews',
    description:
      'Tell the AI what to cover once for the whole job. Then send each person an interview link, or send to everyone on the list at once. They open the link and take a video interview with the AI.',
    side: 'bottom',
    align: 'end',
    view: { tab: 'interviews', reasoning: false, dialog: false },
  },
  {
    target: 'example-cost',
    title: 'What an interview costs',
    // The cost sentence is replaced by the real one when the account is charged.
    description:
      'Each AI interview uses credits, taken when you first send it. You see the cost and your balance before you send. Your balance and every credit used or refunded are under Billing.',
    side: 'top',
    align: 'start',
    view: { tab: 'interviews', reasoning: false, dialog: true },
  },
]

// ─── Candidate dashboard ──────────────────────────────────────────────────────

export const CANDIDATE_STEPS = [
  {
    target: 'candidate-profile',
    title: 'Your profile',
    description:
      'You need a complete profile before you can apply for jobs. It is complete when five things are done: About you, Skills, Years of experience, Location, and an uploaded CV. Each one is worth 20%.',
    side: 'left',
    align: 'start',
  },
  {
    target: 'candidate-documents',
    title: 'Upload your CV here',
    description:
      'Your CV is uploaded from My Documents, not from the profile page, and this is the step people miss. It must be a PDF of 5MB or less. If your CV is a Word file, save it as a PDF first.',
    side: 'left',
    align: 'start',
  },
  {
    target: 'candidate-matches',
    title: 'Jobs picked for you',
    description:
      'Once your profile is complete, jobs that match it appear here. Press View to read a job and apply.',
    side: 'top',
    align: 'start',
  },
  {
    target: 'candidate-applications',
    title: 'Your applications',
    description:
      'After you apply, follow each application here. You can see when an employer starts reviewing you, shortlists you or invites you to interview. You can withdraw while it is still Submitted or Reviewing.',
    side: 'top',
    align: 'start',
  },
  {
    target: 'candidate-tour-button',
    title: 'Need this again?',
    description: 'Press Take a tour whenever you want to see these steps again.',
    side: 'bottom',
    align: 'end',
  },
]
