// The rules a candidate is shown and accepts before an AI interview (docs/14_AI_INTERVIEW_RULES.md,
// section 1). They live here, as data, so the screen and any record of what a candidate accepted
// come from one place.
//
// A rule that depends on a feature that is not built yet carries `needs`, and is shown only when
// that feature is switched on below. A candidate must never be told something is watched when it
// is not. Change INTERVIEW_RULES_VERSION whenever the wording of a visible rule changes, so a
// record of "what they accepted" can say which wording.

// Version 2: the word "AI" is gone from the wording (an "automated interviewer" and an "automated
// assessment" say the same thing); the candidate is still told plainly that it is not a person.
export const INTERVIEW_RULES_VERSION = '2'

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
        text: 'Answer in your own words, from your own knowledge and experience. Do not use notes, a script, a phone, a second screen, a chatbot or any other assistant tool, and do not have anyone whisper or message you answers.',
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
        text: 'Do not leave or reload the page. That ends your connection to the interviewer. If something goes wrong you get one restart. A second restart locks you out of completing it.',
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
        text: 'You will be interviewed by an automated interviewer, not a person. It asks questions and follows up on what you say.',
      },
      {
        id: 'recorded-and-reviewed',
        text: 'Your camera and microphone record the whole session. The employer who invited you reviews the recording and an automated assessment of it.',
      },
      {
        id: 'kept-for-a-while',
        text: 'The recording is kept for a limited time and is only shown to the employer through links that expire.',
      },
      {
        id: 'employer-decides',
        text: 'The assessment helps the employer. Nothing is decided automatically: the employer makes the decision.',
      },
    ],
  },
]

// The rules of the STRICT interview (text questions, answered aloud to the camera, full screen).
// A separate list from RULE_GROUPS above because most of those describe the live voice
// interview (headphones, the interviewer's voice, one restart), which would be untrue here.
// Same convention: a rule that describes monitoring carries `needs` and waits for its flag. Only
// what the screen really does is stated. Version S2 (phase 3): it notices a candidate leaving
// the screen, warns, ends the interview after repeated or long absences, notes the keys that
// try to leave, and has a stop button. Version S3: a warning dims the screen and must be
// confirmed, and every shortcut is noted with its full combination. Version S4: the 60 seconds
// away in total is a rule of its own, highlighted, and the screen shows the time used. Version
// S5: the same rules in about half the words (24 rules became 11), nothing dropped. Version S6:
// up to two follow-up questions on an answer (the Colton Group framework; the server's setting
// `strict_max_follow_ups`, change both together). The numbers in the text (4 leaves, 60 seconds) are the
// server's (settings `strict_max_leaves` and `strict_max_away_seconds`); change both together.
// Version S7: what the AI does after an answer is the employer's choice for the job (no follow-ups,
// up to two neutral ones, or only the employer's own prepared probes), and the rule says which
// (`strictRuleGroups` below; the server's `follow_up_mode`).
// Version S8: the word "AI" is gone from the wording; the candidate is still told plainly that the
// answers are transcribed and assessed by an automated system and that a person makes every decision.
// Change STRICT_RULES_VERSION whenever the wording of a visible rule changes.
export const STRICT_RULES_VERSION = 'S8'

// The end of the "questions-on-screen" rule, by what the AI may do after an answer.
const FOLLOW_UP_RULE_TEXT = {
  STANDARD:
    'Up to two short follow-up questions may be asked on an answer, to the same standard for every candidate.',
  PROBES_ONLY:
    'A short follow-up may be asked from a list the employer prepared for the question, the same list for every candidate. None is made up.',
  NONE: 'Only the questions on screen are asked, with no follow-up questions.',
}

// The strict interview's own monitoring switches. Separate from MONITORING above, which belongs
// to the live interview (whose rules must never claim anything it does not do).
export const STRICT_MONITORING = {
  tabSwitch: true, // leaving the screen is noted, warned about, and can end the interview
  faceChecks: false, // phase 4, not built
  gaze: false, // phase 4, not built
}

export const STRICT_RULE_GROUPS = [
  {
    title: 'Before you start',
    rules: [
      {
        id: 'laptop-and-browser',
        text: 'Use a laptop or desktop with a working camera and microphone, the latest Chrome or Edge, and one screen only (disconnect any second monitor). It cannot be taken on a phone or a tablet.',
      },
      {
        id: 'quiet-place',
        text: 'Sit somewhere quiet and well lit, on a stable connection (Wi-Fi is better than mobile data). Close other tabs and apps and turn on Do Not Disturb.',
      },
    ],
  },
  {
    title: 'During the interview',
    rules: [
      {
        id: 'own-words',
        text: 'Be the person invited, alone, with your camera on and your face in view the whole time. Answer out loud, in your own words. Do not read a prepared text, use notes, a phone, a chatbot or any other assistant tool, or have anyone help you. Do not record or share the interview or the link.',
      },
      {
        id: 'questions-on-screen',
        text: `Each question appears on screen with its time. Answer out loud, looking at the camera. Press Next when you finish; the next one opens when the time is up. ${FOLLOW_UP_RULE_TEXT.STANDARD}`,
      },
      {
        id: 'stay-on-page',
        needs: 'tabSwitch',
        text: 'The interview runs in full screen: right-click, copy, paste and most shortcuts are switched off, and you cannot pause it. Stay on the screen. Leaving it (to another tab, window or app, or out of full screen) is noted and shown to the employer. The first three times you get a warning: the screen dims and you must confirm it. The fourth time, or being away for more than 60 seconds in total, ends the interview.',
      },
      {
        id: 'time-away',
        needs: 'tabSwitch',
        emphasis: true,
        text: 'You have 60 seconds away from the screen in total, for the whole interview. Every time you leave adds to the same total. When it goes past 60 seconds, the interview ends as soon as you are back, even if that is your first time leaving. The screen shows how much you have used.',
      },
      {
        id: 'keys-noted',
        needs: 'tabSwitch',
        text: 'Shortcuts (such as Ctrl+T, Alt+Tab, Ctrl+Shift+I), Esc and F11 or F12 are also noted and shown to the employer, with the full combination. They do not end the interview.',
      },
      {
        id: 'stop-button',
        needs: 'tabSwitch',
        text: 'If you need to stop, press I need to stop and confirm. The employer is told and can let you carry on later. Stopping is your choice and is not a mark against you.',
      },
    ],
  },
  {
    title: 'If something goes wrong',
    rules: [
      {
        id: 'if-it-ends',
        needs: 'tabSwitch',
        text: 'If your page reloads or your connection drops, open the same link to return to your question; the time that passed is not given back. If the interview ends, your answers and recording are still sent to the employer. If you think it should not have ended, contact the employer who invited you.',
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
        id: 'employer-decides',
        text: 'Your answers are transcribed and assessed by an automated system; a person makes every decision. Your camera and microphone record the whole session, and the recording is kept for a limited time. The employer who invited you reviews the recording, your answers and the assessment. The only thing decided automatically is ending the interview as described above, and the notes about leaving the screen are for review, not proof of anything.',
      },
    ],
  },
]

/** The strict interview's rules for what this job's AI may do after an answer: the same rules, with
 *  the follow-up sentence of the "questions-on-screen" rule saying NONE, STANDARD or PROBES_ONLY.
 *  An unknown mode is the standard (how every interview behaved before the choice existed). */
export function strictRuleGroups(followUpMode = 'STANDARD') {
  const sentence = FOLLOW_UP_RULE_TEXT[followUpMode] ?? FOLLOW_UP_RULE_TEXT.STANDARD
  return STRICT_RULE_GROUPS.map((group) => ({
    ...group,
    rules: group.rules.map((rule) =>
      rule.id === 'questions-on-screen'
        ? { ...rule, text: rule.text.replace(FOLLOW_UP_RULE_TEXT.STANDARD, sentence) }
        : rule
    ),
  }))
}

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
