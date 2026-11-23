/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { ScreenshotData } from '../types/guide';

/** Text and pictures for the "Giving Feedback" part of the guide. */

export const FEEDBACK_SECTION_IDS = [
  'feedback-overview',
  'feedback-send',
  'feedback-follow',
  'feedback-receive',
  'feedback-help',
] as const;

export const FEEDBACK_ROLES = [
  {
    who: 'Staff at a health post, health centre, or PHCU',
    task: 'Report a problem, wrong data, or a question, and check the answer.',
    read: [
      { id: 'feedback-send', label: 'Sending feedback' },
      { id: 'feedback-follow', label: 'Following your feedback' },
    ],
  },
  {
    who: 'A focal person or HMIS officer at a woreda, zone, or region',
    task: 'Answer feedback from offices below you, and send feedback to the level above.',
    read: [
      { id: 'feedback-send', label: 'Sending feedback' },
      { id: 'feedback-receive', label: 'Answering feedback' },
    ],
  },
  {
    who: 'Staff of a Federal MoH directorate or programme',
    task: 'Answer feedback that reaches the Ministry, and pass items to the right region.',
    read: [{ id: 'feedback-receive', label: 'Answering feedback' }],
  },
  {
    who: 'A manager or supervisor',
    task: 'Check that feedback in your area is answered on time.',
    read: [{ id: 'feedback-receive', label: 'Area numbers and deadlines' }],
  },
  {
    who: 'Someone who was added to a piece of feedback',
    task: 'Read it, and help if you can.',
    read: [{ id: 'feedback-follow', label: 'If someone added you' }],
  },
];

export const FEEDBACK_QUICK_START = [
  'Sign in and click Feedback in the top menu.',
  'Leave Send to as it is. Your upper level is already chosen, and that is right for most feedback.',
  'Choose the kind of feedback: Problem, Wrong data, Question, or Suggestion.',
  'Write what is wrong and where you saw it: the dashboard, the chart, the area, and the month. Add a screenshot if you can.',
  'Click Send feedback, and write down the reference number, such as FB-125.',
];

export const FEEDBACK_FLOW = [
  { step: 'You send feedback', detail: 'It gets a reference number, such as FB-125.' },
  { step: 'It reaches the right office', detail: 'Normally the office one level above you.' },
  { step: 'The office answers', detail: 'Or asks you a question first.' },
  { step: 'You say whether it is solved', detail: 'If not, the office keeps working on it.' },
];

export const FEEDBACK_PARTS = [
  {
    part: 'Sender',
    meaning: 'You wrote the feedback.',
    canDo: 'Read it, add information, reply to questions, say whether it is solved, reopen it, and add people.',
  },
  {
    part: 'Receiver',
    meaning: 'You work at the office responsible for it.',
    canDo: 'Answer, ask questions, assign, set priority, pass it on, write internal notes, hide content, and add people.',
  },
  {
    part: 'Added person',
    meaning: 'Someone named you on the feedback.',
    canDo: 'Read the conversation and comment, or remove yourself with Not for me. You are not responsible for it.',
  },
];

export const FEEDBACK_TABS = [
  { name: 'Send feedback', description: 'Write new feedback. Everyone has this tab.' },
  { name: 'My feedback', description: 'Feedback you sent, and feedback you were added to. Everyone has this tab.' },
  { name: 'Waiting on me', description: 'Feedback your office must deal with. Only for users whose office receives feedback.' },
  { name: 'Area numbers', description: 'Counts for your office and the offices below it. Only for users whose office receives feedback.' },
];

export const FEEDBACK_WORDS = [
  { word: 'Reference number', meaning: 'The number of each piece of feedback, such as FB-125. Use it when you talk about it.' },
  { word: 'Upper level', meaning: 'The office directly above yours, for example the zone above a woreda.' },
  { word: 'Receiver', meaning: 'A person at the office responsible for the feedback, who must answer it.' },
  { word: 'Working day', meaning: 'Monday to Friday. Weekends do not count towards deadlines.' },
  { word: 'Overdue', meaning: 'Past its deadline and not yet finished.' },
  { word: 'Pass it on', meaning: 'Send the feedback to a different office that is better placed to handle it.' },
  { word: 'Internal note', meaning: 'A note only receivers can read. The sender never sees it.' },
];

export const FEEDBACK_STATUSES = [
  { label: 'Please reply', needsYou: true, meaning: 'The office has asked you a question.', todo: 'Open it and reply.' },
  { label: 'Did this solve it?', needsYou: true, meaning: 'The office has answered.', todo: 'Open it and say whether it is solved.' },
  { label: 'New', needsYou: false, meaning: 'It has arrived and is waiting to be looked at.', todo: 'Nothing.' },
  { label: 'In review', needsYou: false, meaning: 'The office is working on it.', todo: 'Nothing.' },
  { label: 'Assigned', needsYou: false, meaning: 'A named person is working on it.', todo: 'Nothing.' },
  { label: 'Closed', needsYou: false, meaning: 'It is finished.', todo: 'You can reopen it within 30 days.' },
  { label: 'Declined', needsYou: false, meaning: 'The office could not take it, and gave a reason.', todo: 'Read the reason. You can reopen it within 30 days.' },
];

export const FEEDBACK_EXAMPLES = {
  unclear: ['"The data is wrong."', '"Dashboard not working!!"'],
  clear: [
    '"On the Maternal Health tab, ANC 4+ coverage for our woreda in March shows 240%. Our register shows about 60%."',
    '"The Malaria tab shows a blank page since Monday. Other tabs open normally."',
  ],
  questions: [
    'What is wrong, or what do you want to know?',
    'Where did you see it: which dashboard, tab, chart, or report?',
    'Which area, and which month or year?',
    'What did you expect to see instead?',
  ],
};

export const FEEDBACK_RESPONSES = [
  { choice: 'Send an answer', when: 'You have the solution.', result: 'The sender is asked whether it solved the problem.' },
  { choice: 'Send a message', when: 'You want to update or tell the sender something.', result: 'The status does not change.' },
  { choice: 'Ask for information', when: 'You need something from the sender.', result: 'The status becomes Needs info, and the deadline pauses.' },
  { choice: 'Internal note', when: 'A note for your own office.', result: 'Only receivers can see it.' },
  { choice: 'Decline', when: 'It cannot be handled. A reason is required.', result: 'The feedback is closed, and the sender sees the reason.' },
];

export const FEEDBACK_MORE_ACTIONS = [
  { action: 'Mark as in review', detail: 'Shows colleagues that someone is looking at it.' },
  { action: 'Assign to someone', detail: 'Gives it to a colleague in your office.' },
  { action: 'Change priority', detail: 'High, Normal, or Low. This changes the deadlines.' },
  { action: 'Not for your unit? Pass it on', detail: 'Sends it to the level above or to an office below you. A reason is required. The new office becomes responsible, and your office can still read it.' },
];

export const FEEDBACK_DEADLINES = [
  { priority: 'High', example: 'Dashboard down, or wrong figures in a report in use', first: '2 working days', finish: '5 working days' },
  { priority: 'Normal', example: 'One chart wrong, or a how-to question', first: '5 working days', finish: '14 working days' },
  { priority: 'Low', example: 'A suggestion', first: '5 working days', finish: 'No deadline' },
];

export const FEEDBACK_DAILY_ROUTINE = [
  'Open Waiting on me once a day, or when the morning summary email arrives.',
  'Deal with Overdue items first, then the ones with the closest date.',
  'Click Mark as in review on anything you start, so colleagues do not work on it twice.',
  'If something is unclear, use Ask for information early. The deadline pauses while you wait.',
  'If it belongs elsewhere, pass it on with a short reason, rather than leaving it to become overdue.',
];

export const FEEDBACK_AREA_NUMBERS = [
  { name: 'Received', meaning: 'Feedback sent from or to your area in the period.' },
  { name: 'Typical first response', meaning: 'How long a first response usually takes.' },
  { name: 'First response on time', meaning: 'The share of first responses made by the deadline.' },
  { name: 'Overdue now', meaning: 'Items still being handled that are past a deadline.' },
  { name: 'Where items are waiting', meaning: 'Open and overdue items for each office, and how old the oldest is.' },
];

export const FEEDBACK_EMAILS = [
  { event: 'Feedback was sent', to: 'The sender.' },
  { event: 'Someone was added', to: 'The person added.' },
  { event: 'Feedback was assigned', to: 'The person it was assigned to.' },
  { event: 'A receiver asked, answered, wrote a message, or declined', to: 'The sender.' },
  { event: 'Feedback was passed on', to: 'The sender, the new office, and the person it was assigned to.' },
  { event: 'The sender replied, added information, said not solved, or reopened', to: 'The assigned person, or the office if nobody is assigned.' },
  { event: 'New or overdue items', to: 'Each receiver, in one summary email on weekdays at 08:00.' },
];

export const FEEDBACK_PROBLEMS = [
  { message: 'No units found below yours', meaning: 'The office box only searches office names.', todo: 'Type an office name. To name a person, use Add a person.' },
  { message: 'No exact match', meaning: 'The person search needs the complete details.', todo: 'Type the full email, username, or first and last name.' },
  { message: 'Search for a unit and choose one before sending', meaning: 'You chose A unit below me but did not click an office.', todo: 'Click an office in the list, or choose your upper level.' },
  { message: 'Only PNG or JPEG images can be attached', meaning: 'The file is not a PNG or JPEG picture.', todo: 'Save the picture as PNG or JPEG.' },
  { message: 'Each screenshot must be under 5 MB', meaning: 'The picture is too large.', todo: 'Use a smaller picture.' },
  { message: 'This page expired', meaning: 'The page was open for a long time.', todo: 'Reload the page and try again. Check My feedback first to see whether it was already sent.' },
  { message: 'This item has changed', meaning: 'Someone else acted on it first.', todo: 'Read the item again before acting.' },
  { message: 'You have sent a lot of feedback in the last hour', meaning: 'The limit is 10 items an hour.', todo: 'Try again later.' },
  { message: 'No active user can receive feedback for that unit', meaning: 'Nobody at that office can receive feedback.', todo: 'Choose another office, or send to your upper level.' },
  { message: 'Waiting for an office', meaning: 'The system could not choose an office when you sent it.', todo: 'Nothing. It stays saved, and you can read it under My feedback.' },
];

export const FEEDBACK_FAQ = [
  { q: 'Can my colleagues see what I sent?', a: 'No, unless they work at the office that received it or you added them.' },
  { q: 'What if the answer does not help?', a: 'Click No, not solved and say why. The office will continue to work on it.' },
  { q: 'What if I sent it to the wrong office?', a: 'The office can pass it on to the right place.' },
  { q: 'Can I delete feedback I sent?', a: 'No. If it was sent by mistake, add a message saying so. The office can then close it.' },
  { q: 'Can I write in Amharic?', a: 'Yes. Write in the language you work in, as long as the office can read it.' },
  { q: 'I do not get any emails.', a: 'Look in your spam folder, and check My feedback or Waiting on me. Most emails arrive within about 5 minutes.' },
];

const shot = (
  id: string,
  file: string,
  title: string,
  altText: string,
  displaySize: ScreenshotData['displaySize'],
  annotations?: ScreenshotData['annotations'],
): ScreenshotData => ({
  id,
  imagePath: `images/guide/${file}`,
  title,
  altText,
  displaySize,
  annotations,
});

// The numbers are already drawn on these pictures, so the markers have no position
export const FEEDBACK_SHOTS = {
  form: shot('sc-feedback-form', 'feedback-form.png', 'Feedback, Send feedback', 'The Send feedback form with numbered parts, and a panel showing your name and office.', 'large', [
    { number: 1, title: 'Send to', description: 'Where it goes. Your upper level is chosen for you, and is right for most feedback.' },
    { number: 2, title: 'Kind of feedback', description: 'Problem, Wrong data, Question, or Suggestion.' },
    { number: 3, title: 'Your message', description: 'What is wrong and where you saw it. At least 10 and at most 2,000 characters.' },
    { number: 4, title: 'Screenshot', description: 'Optional. Up to 3 PNG or JPEG pictures, 5 MB each.' },
    { number: 5, title: 'Add a person', description: 'Optional. Name someone who should also see it.' },
    { number: 6, title: 'Send feedback', description: 'Sends it and shows your reference number.' },
  ]),
  sent: shot('sc-feedback-sent', 'feedback-sent.png', 'Feedback, the confirmation after sending', 'A green message with the reference number, the expected reply date, and a link to My feedback.', 'medium'),
  person: shot('sc-feedback-person', 'feedback-person-result.png', 'Feedback, adding a person', 'A person found by their full email address, with their office and a Select button.', 'small'),
  mine: shot('sc-feedback-mine', 'feedback-mine.png', 'Feedback, My feedback', 'The My feedback list, with items that need you first and red labels.', 'large', [
    { number: 1, title: 'Needs you', description: 'Feedback waiting for your reply or confirmation comes first, with a red label.' },
    { number: 2, title: 'Count', description: 'How many items are waiting for you.' },
    { number: 3, title: 'Search and filter', description: 'Find an item by words, a name, its FB number, or its status.' },
  ]),
  reply: shot('sc-feedback-reply', 'feedback-reply.png', 'Feedback, a question waiting for your reply', 'An item with a blue message asking for your reply and a reply box.', 'narrow', [
    { number: 1, title: 'The question', description: 'The office needs something from you.' },
    { number: 2, title: 'Your reply', description: 'Write your answer and click Send reply.' },
  ]),
  confirm: shot('sc-feedback-confirm', 'feedback-confirm.png', 'Feedback, saying whether it is solved', 'An answered item with Yes, this solved it and No, not solved buttons.', 'narrow', [
    { number: 1, title: 'The answer', description: 'Read what the office did.' },
    { number: 2, title: 'Yes, this solved it', description: 'The feedback is closed.' },
    { number: 3, title: 'No, not solved', description: 'Write why first. The feedback goes back to the office.' },
  ]),
  reopen: shot('sc-feedback-reopen', 'feedback-reopen.png', 'Feedback, reopening closed feedback', 'A reason box and a Reopen button.', 'small'),
  added: shot('sc-feedback-added', 'feedback-added-item.png', 'Feedback, an item you were added to', 'A feedback item with a comment box and a Not for me button.', 'large', [
    { number: 1, title: 'Add a comment', description: 'Help with what you know.' },
    { number: 2, title: 'Not for me', description: 'Removes it from your list if it does not concern you.' },
  ]),
  waiting: shot('sc-feedback-waiting', 'feedback-waiting.png', 'Feedback, Waiting on me', 'The list of feedback for your office, with deadlines and overdue labels.', 'large', [
    { number: 1, title: 'Needs action', description: 'New items, items in review, and items assigned to you. The closest deadline comes first. All for my unit shows everything your office holds.' },
    { number: 2, title: 'Search and status', description: 'Find an item by words, a name, or its FB number.' },
    { number: 3, title: 'Overdue', description: 'Items past their deadline.' },
  ]),
  respond: shot('sc-feedback-respond', 'feedback-respond.png', 'Feedback, choosing what to do', 'Five choices for responding, a message box, and a button.', 'small'),
  more: shot('sc-feedback-more', 'feedback-more.png', 'Feedback, More actions', 'Mark as in review, assign, change priority, and pass it on.', 'narrow'),
  stats: shot('sc-feedback-stats', 'feedback-stats.png', 'Feedback, Area numbers', 'Counts for received, response time, on-time share, and overdue items, with a table of offices.', 'large'),
};
