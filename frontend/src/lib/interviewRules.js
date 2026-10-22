// The rules a candidate is shown and accepts before an AI interview (docs/14_AI_INTERVIEW_RULES.md,
// section 1). They live here, as data, so the screen and any record of what a candidate accepted
// come from one place.
//
// A rule that depends on a feature that is not built yet carries `needs`, and is shown only when
// that feature is switched on below. A candidate must never be told something is watched when it
// is not. Change INTERVIEW_RULES_VERSION whenever the wording of a visible rule changes, so a
// record of "what they accepted" can say which wording.

export const INTERVIEW_RULES_VERSION = '1'

// Flip a flag to true in the same change that builds the feature, and its rules appear.
export const MONITORING = {
  tabSwitch: false, // the page being hidden, or the window losing focus, is noted
  faceChecks: false, // no face, or more than one face, is noted
  gaze: false, // looking away for a long time is noted
}

export const RULE_GROUPS = [
  {
    title: 'Before you start',
    rules: [
      {
        id: 'one-device',
        text: 'Use one device and one browser for the whole interview. A laptop or desktop is best. Use a recent version of Chrome, Edge or Safari.',
      },
      {
        id: 'quiet-and-light',
        text: 'Choose a quiet place with good light. Face the light, with no bright window behind you.',
      },
      {
        id: 'headphones',
        text: "Use earphones or headphones. Without them the interviewer's voice can echo into your microphone and spoil the recording.",
      },
      {
        id: 'connection',
        text: 'Check your connection. The interview is live, so a stable internet connection matters. Wi-Fi is better than mobile data.',
      },
      {
        id: 'close-everything',
        text: 'Close other tabs and apps, and turn on Do Not Disturb, so nothing pops up and pulls you away.',
      },
    ],
  },
  {
    title: 'During the interview',
    rules: [
      {
        id: 'alone',
        text: 'You must be the person who was invited, and you must be alone. No one else may be in the room, speak to you, or help you with answers.',
      },
      {
        id: 'camera-on',
        text: 'Keep your camera on for the whole interview. Your face must be fully visible, with the camera at about eye level. Do not cover or turn off the camera.',
      },
      {
        id: 'stay-on-page',
        needs: 'tabSwitch',
        text: 'Stay on the interview page. Do not switch to another tab, window or app. Each time you leave the page is noted and shown to the employer, with the time and how long you were away.',
      },
      {
        id: 'face-visible',
        needs: 'faceChecks',
        text: 'Your face must stay in view. Times when no face is seen, or when more than one face is seen, are noted and shown to the employer.',
      },
      {
        id: 'look-at-screen',
        needs: 'gaze',
        text: 'Look at the screen while you answer. Short glances away are normal. Looking away for a long time is noted and shown to the employer.',
      },
      {
        id: 'own-words',
        text: 'Answer in your own words, from your own knowledge and experience. Do not use notes, a script, a phone, a second screen, a chatbot or any AI assistant, and do not have anyone whisper or message you answers.',
      },
      {
        id: 'speak-aloud',
        text: 'Speak your answers out loud. Do not read a prepared text.',
      },
      {
        id: 'no-sharing',
        text: 'Do not record, photograph, copy or share the interview, the questions or the recording. The link is yours alone. Do not pass it to anyone.',
      },
      {
        id: 'do-not-leave',
        text: 'Do not leave or reload the page. That ends your connection to the AI interviewer. If something goes wrong you get one restart. A second restart locks you out of completing it.',
      },
      {
        id: 'it-ends',
        text: 'The interview ends by itself when the interviewer has covered the topics, or when the time limit is reached. You can also end it yourself with the End interview button.',
      },
    ],
  },
  {
    title: 'If something goes wrong',
    rules: [
      {
        id: 'dropped',
        text: 'A dropped connection or a closed tab: open the same link again. You get one restart.',
      },
      {
        id: 'cannot-meet-a-rule',
        text: 'If you cannot meet a rule for a genuine reason (a disability, no working camera, no quiet place), tell the employer who invited you before you start, so another way can be arranged.',
      },
    ],
  },
  {
    title: 'What you agree to',
    rules: [
      {
        id: 'ai-interviewer',
        text: 'You will be interviewed by an AI interviewer, not a person. It asks questions and follows up on what you say.',
      },
      {
        id: 'recorded-and-reviewed',
        text: 'Your camera and microphone record the whole session. The employer who invited you reviews the recording and an AI assessment of it.',
      },
      {
        id: 'kept-for-a-while',
        text: 'The recording is kept for a limited time and is only shown to the employer through links that expire.',
      },
      {
        id: 'employer-decides',
        text: 'The AI assessment helps the employer. Nothing is decided automatically: the employer makes the decision.',
      },
    ],
  },
]

/** The groups to show now: only rules whose feature (if any) is switched on, and no empty group. */
export function visibleRuleGroups(monitoring = MONITORING) {
  return RULE_GROUPS.map((group) => ({
    ...group,
    rules: group.rules.filter((rule) => !rule.needs || monitoring[rule.needs]),
  })).filter((group) => group.rules.length > 0)
}

/** The same groups with each rule given its number, counting on from group to group (1, 2, 3 ...),
 *  so a rule can be referred to by its number. */
export function numberedRuleGroups(monitoring = MONITORING) {
  let next = 1
  return visibleRuleGroups(monitoring).map((group) => ({
    ...group,
    rules: group.rules.map((rule) => ({ ...rule, number: next++ })),
  }))
}
