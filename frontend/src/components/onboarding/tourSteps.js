// The first-login tour of the employer dashboard. Each step points at an element that
// carries a matching data-tour attribute on DashboardPage. A step whose element is not
// on the page (the profile banner once the profile is complete) is left out.

export const TOUR_STEPS = [
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
    target: 'recent-jobs',
    title: 'Your jobs and applicants',
    description:
      'Open a job to see who applied. Each applicant gets an AI score for the role, and the interview list for that job is on the same page.',
    side: 'top',
    align: 'start',
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
    title: 'Read and score CVs',
    description:
      'Upload CVs and Elevare reads them and fills in the candidate details. Scores against a job show on that job and in the talent pool.',
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
]

export const tourSelector = (target) => `[data-tour="${target}"]`
