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
      'Keep candidates you source yourself in one place. Score them against your open roles and move the best ones forward. You will see this page in the example.',
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
      'Open your jobs to edit, publish or close a listing. Each job has a View Applicants button. Next, a short look at that page and at the Talent Pool, using an example job.',
    side: 'top',
    align: 'start',
    nextLabel: 'See an example job',
    // Moves on to the example job page instead of ending the tour.
    handoff: true,
  },
]

// ─── Employer, part 2: an example job and the Talent Pool, with made-up people ─
// The example page is one page that can show two screens, the job and the Talent Pool.
// `view` is the whole state the page should be in while a step is on screen, so going
// Back always lands on a screen that makes sense.

export const EXAMPLE_VIEW_DEFAULT = {
  page: 'job', // job | pool
  tab: 'applicants', // job: applicants | pipeline | ai-matches | interviews
  reasoning: false, // job, applicants: the first applicant's score reasons are open
  dialog: false, // job, interviews: the "Send AI interview invite?" dialog is open
  drawer: false, // pool: the "Add to Talent Pool" drawer is open
  poolJob: '', // pool: the job the pool is viewed against ('' is the plain pipeline)
  listed: [], // ids of the people on the job's interview list
}

const view = (changes) => ({ ...EXAMPLE_VIEW_DEFAULT, ...changes })

export const EXAMPLE_JOB_STEPS = [
  {
    target: 'example-banner',
    title: 'An example job',
    description:
      'This is an example job with made-up candidates, so you can see how it works. Nothing here is real, nothing is sent and no credits are used.',
    side: 'bottom',
    align: 'start',
    view: view({}),
  },
  {
    target: 'example-applicants',
    title: 'Applicants',
    description:
      'Everyone who applies to your job appears here, with where they live, their experience and when they applied. Use Move to take each person through the stages, from Reviewing to Shortlisted to Hired.',
    side: 'top',
    align: 'start',
    view: view({}),
  },
  {
    target: 'example-score',
    title: 'AI score',
    description:
      'Elevare reads each CV and scores how well the person fits this job. Press the score to see the reasons, with strengths and gaps. It shows how closely their experience matches the role. It is not a pass or fail.',
    side: 'top',
    align: 'start',
    view: view({ reasoning: true }),
  },
  {
    target: 'example-interview-button',
    title: 'Add people to the interview list',
    description:
      'Press Interview list on anyone you want to interview. They move onto this job’s interview list, which you will see in a moment. Amaka has been added here as an example. The same button is on the Talent Pipeline tab.',
    side: 'bottom',
    align: 'end',
    view: view({ listed: ['a1'] }),
  },
  {
    target: 'example-upload',
    title: 'Upload CVs and score them',
    description:
      'Have CVs of your own, from an agency or an email? Press Upload CVs. It opens the Talent Pool, which is where CVs are uploaded.',
    side: 'bottom',
    align: 'end',
    view: view({ tab: 'pipeline', listed: ['a1'] }),
  },
  {
    target: 'example-pool-add',
    title: 'The talent pool',
    description:
      'Every CV you source yourself lives here, whether it came from an agency, a referral or your email. Press Add CV to upload some.',
    side: 'bottom',
    align: 'end',
    view: view({ page: 'pool', listed: ['a1'] }),
  },
  {
    target: 'example-pool-drop',
    title: 'Upload up to 20 CVs at once',
    description:
      'Drop PDF files here or browse for them. Each CV is read, and the person’s details are filled in for you.',
    side: 'left',
    align: 'start',
    view: view({ page: 'pool', drawer: true, listed: ['a1'] }),
  },
  {
    target: 'example-pool-attach',
    title: 'Choose the job to score against',
    description:
      'Attach the CVs to a job and the AI scores each one automatically once it has been read. Leave it empty to only add them to your pool.',
    side: 'left',
    align: 'start',
    view: view({ page: 'pool', drawer: true, poolJob: 'sales', listed: ['a1'] }),
  },
  {
    target: 'example-pool-job',
    title: 'Rank your pool against a job',
    description:
      'Choose a job here to see everyone in your pool ranked against it, best match first. Press Score all to score the people who have no score for that job yet.',
    side: 'bottom',
    align: 'start',
    view: view({ page: 'pool', poolJob: 'sales', listed: ['a1'] }),
  },
  {
    target: 'example-pipeline-rows',
    title: 'Scores arrive as CVs are read',
    description:
      'Back on the job, the Talent Pipeline tab shows the CVs scored against it. A CV that is still being read has no score yet, and shows its score as soon as it is done. The Interview list button is here too.',
    side: 'top',
    align: 'start',
    view: view({ tab: 'pipeline', listed: ['a1', 'p1'] }),
  },
  {
    target: 'example-interview-list',
    title: 'Interview list',
    description:
      'The people you added are collected here, from Applicants, Talent Pipeline or AI Talent Matches. Press the button again on a person to take them off.',
    side: 'top',
    align: 'start',
    view: view({ tab: 'interviews', listed: ['a1', 'p1'] }),
  },
  {
    target: 'example-send-interviews',
    title: 'Send AI interviews',
    description:
      'Tell the AI what to cover once for the whole job. Then send each person an interview link, or send to everyone on the list at once. They open the link and take a video interview with the AI.',
    side: 'bottom',
    align: 'end',
    view: view({ tab: 'interviews', listed: ['a1', 'p1'] }),
  },
  {
    target: 'example-cost',
    title: 'What an interview costs',
    // The cost sentence is replaced by the real one when the account is charged.
    description:
      'Each AI interview uses credits, taken when you first send it. You see the cost and your balance before you send. Your balance and every credit used or refunded are under Billing.',
    side: 'top',
    align: 'start',
    view: view({ tab: 'interviews', dialog: true, listed: ['a1', 'p1'] }),
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
