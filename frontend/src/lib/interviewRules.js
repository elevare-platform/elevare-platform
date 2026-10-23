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

// The rules of the STRICT interview (text questions, answered aloud to the camera, full screen).
// A separate list from RULE_GROUPS above because most of those describe the live voice
// interview (headphones, the interviewer's voice, one restart), which would be untrue here.
// Same convention: a rule that describes monitoring carries `needs` and waits for its flag. Only
// what the screen really does today is stated: it asks for full screen and switches off
// right-click, copy and paste, but it does NOT yet notice a candidate leaving the page, so that
// rule stays hidden until `tabSwitch` is switched on (phase 3).
export const STRICT_RULES_VERSION = 'S1'

export const STRICT_RULE_GROUPS = [
  {
    title: 'Before you start',
    rules: [
      {
        id: 'laptop-and-browser',
        text: 'Use a laptop or desktop computer with a working camera and microphone, and the latest Chrome or Edge. This interview cannot be taken on a phone or a tablet.',
      },
      {
        id: 'one-screen',
        text: 'Use one screen only. If a second monitor is connected, disconnect it before you start. The interview cannot start while a second screen is detected.',
      },
      {
        id: 'quiet-and-light',
        text: 'Choose a quiet place with good light. Face the light, with no bright window behind you.',
      },
      {
        id: 'connection',
        text: 'Check your connection. Your answers are sent as you go, so a stable internet connection matters. Wi-Fi is better than mobile data.',
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
        text: 'Keep your camera on for the whole interview, with your face fully visible and the camera at about eye level. Do not cover or turn off the camera.',
      },
      {
        id: 'questions-on-screen',
        text: 'Each question appears at the top of the screen, with the time you have to answer it. Read it, then answer out loud, looking at the camera. You can press Next when you have finished, and the next question opens when the time is up.',
      },
      {
        id: 'follow-up',
        text: 'After an answer the AI may ask one short follow-up question if it needs a little more detail. A follow-up has its own, shorter time.',
      },
      {
        id: 'full-screen',
        text: 'The interview runs in full screen. While it runs, right-click, copy, paste and most keyboard shortcuts are switched off. You cannot pause it.',
      },
      {
        id: 'stay-on-page',
        needs: 'tabSwitch',
        text: 'Stay on the interview page. Leaving full screen, switching to another tab, window or app is noted and shown to the employer, with the time and how long you were away. After repeated or long absences the interview ends.',
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
        id: 'it-ends',
        text: 'The interview has a time limit for each question and an overall time limit, both shown on screen. It ends by itself when the questions are done or the time is up.',
      },
    ],
  },
  {
    title: 'If something goes wrong',
    rules: [
      {
        id: 'dropped',
        text: 'If your page reloads or your connection drops, open the same link again. You return to the question you were on. The time that passed is not given back.',
      },
      {
        id: 'cannot-meet-a-rule',
        text: 'If you cannot meet a rule for a genuine reason (a disability, no laptop, no working camera, no quiet place), tell the employer who invited you before you start, so another way can be arranged.',
      },
    ],
  },
  {
    title: 'What you agree to',
    rules: [
      {
        id: 'ai-interviewer',
        text: 'This interview is run by an AI, not a person. It chooses whether to ask a follow-up, and an automated service turns what you say into text.',
      },
      {
        id: 'recorded-and-reviewed',
        text: 'Your camera and microphone record the whole session. The employer who invited you reviews the recording, the text of your answers and an AI assessment of them.',
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
export function visibleRuleGroups(monitoring = MONITORING, groups = RULE_GROUPS) {
  return groups
    .map((group) => ({
      ...group,
      rules: group.rules.filter((rule) => !rule.needs || monitoring[rule.needs]),
    }))
    .filter((group) => group.rules.length > 0)
}

/** The same groups with each rule given its number, counting on from group to group (1, 2, 3 ...),
 *  so a rule can be referred to by its number. */
export function numberedRuleGroups(monitoring = MONITORING, groups = RULE_GROUPS) {
  let next = 1
  return visibleRuleGroups(monitoring, groups).map((group) => ({
    ...group,
    rules: group.rules.map((rule) => ({ ...rule, number: next++ })),
  }))
}
