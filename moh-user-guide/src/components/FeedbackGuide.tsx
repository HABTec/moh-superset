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
import React from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, HelpCircle, Inbox, Layers, Mail, MessageSquare, Send, Users, XCircle } from 'lucide-react';
import { Callout } from './Callout';
import { ScreenshotPlaceholder } from './ScreenshotPlaceholder';
import {
  FEEDBACK_AREA_NUMBERS,
  FEEDBACK_DAILY_ROUTINE,
  FEEDBACK_DEADLINES,
  FEEDBACK_EMAILS,
  FEEDBACK_EXAMPLES,
  FEEDBACK_FAQ,
  FEEDBACK_FLOW,
  FEEDBACK_MORE_ACTIONS,
  FEEDBACK_PARTS,
  FEEDBACK_PROBLEMS,
  FEEDBACK_QUICK_START,
  FEEDBACK_RESPONSES,
  FEEDBACK_ROLES,
  FEEDBACK_SHOTS,
  FEEDBACK_STATUSES,
  FEEDBACK_TABS,
  FEEDBACK_WORDS,
} from '../data/feedbackGuideData';

interface Props {
  /** Which of the five feedback pages match the page search. */
  visible: Record<string, boolean>;
  onNavigate: (id: string) => void;
}

const Heading: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="mb-4">
    <span className="text-xs font-bold uppercase tracking-wider text-blue-900 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
      Giving Feedback
    </span>
    <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mt-2">{title}</h2>
    <p className="text-base text-slate-600 mt-2 leading-relaxed">{children}</p>
  </div>
);

const SubHeading: React.FC<{ icon: React.ElementType; children: React.ReactNode }> = ({ icon: Icon, children }) => (
  <h3 className="mt-8 mb-2 text-lg font-bold text-slate-900 flex items-center gap-2">
    <Icon className="w-4 h-4 text-blue-800" aria-hidden="true" />
    <span>{children}</span>
  </h3>
);

const Steps: React.FC<{ items: string[] }> = ({ items }) => (
  <ol className="list-none space-y-2 text-sm text-slate-700 my-3">
    {items.map((step, idx) => (
      <li key={step} className="flex items-start gap-3">
        <span className="w-5 h-5 rounded-full bg-slate-900 text-white font-mono text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
          {idx + 1}
        </span>
        <span className="flex-1 pt-0.5">{step}</span>
      </li>
    ))}
  </ol>
);

/** A simple table: the first column is bold, as in the other reference tables. */
const Table: React.FC<{ head: string[]; rows: React.ReactNode[][] }> = ({ head, rows }) => (
  <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
    <table className="w-full text-sm text-left">
      <thead className="bg-slate-100 text-slate-900">
        <tr>
          {head.map((h) => (
            <th key={h} scope="col" className="px-3 py-2.5 font-semibold">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100 text-slate-700 align-top">
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j} className={`px-3 py-2.5 leading-relaxed ${j === 0 ? 'font-semibold text-slate-900' : ''}`}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export const FeedbackGuide: React.FC<Props> = ({ visible, onNavigate }) => (
  <>
    {visible['feedback-overview'] && (
      <section id="feedback-overview" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
        <Heading title="How feedback works">
          Use Feedback to report a problem, wrong data, a question, or a suggestion, and follow it until it is solved. Every message goes to a real office, gets a reference number such as FB-125, and stays visible to you from start to finish.
        </Heading>

        <div className="my-5 p-4 rounded-xl bg-blue-50/50 border border-blue-100">
          <div className="flex items-start gap-2.5">
            <HelpCircle className="w-4 h-4 text-blue-800 shrink-0 mt-1" aria-hidden="true" />
            <div className="text-sm text-slate-800 leading-relaxed space-y-1.5">
              <p><strong className="text-blue-950">The question it answers:</strong> Who can fix what I found, and how do I know when it is fixed?</p>
              <p><strong className="text-blue-950">When to use it:</strong> When a number looks wrong, a chart does not work, you have a question about the portal, or you have an idea to improve it.</p>
            </div>
          </div>
        </div>

        <SubHeading icon={Users}>Start here: find the parts for you</SubHeading>
        <p className="text-sm text-slate-700">You do not need to read everything. Find the row that describes you.</p>
        <Table
          head={['If you are', 'You will mostly', 'Read']}
          rows={FEEDBACK_ROLES.map((r) => [
            r.who,
            r.task,
            <span key="read" className="flex flex-wrap gap-x-3 gap-y-1">
              {r.read.map((link) => (
                <button key={link.label} type="button" onClick={() => onNavigate(link.id)} className="text-blue-900 font-semibold hover:underline cursor-pointer text-left">
                  {link.label}
                </button>
              ))}
            </span>,
          ])}
        />

        <SubHeading icon={Send}>Quick start: send feedback in 5 steps</SubHeading>
        <Steps items={FEEDBACK_QUICK_START} />
        <Callout type="tip" title="You cannot break anything">
          Nothing is sent until you press a button such as Send feedback or Send reply, so it is safe to look around.
        </Callout>

        <SubHeading icon={ArrowRight}>The feedback loop</SubHeading>
        <ol className="my-4 grid grid-cols-1 sm:grid-cols-4 gap-2 list-none pl-0">
          {FEEDBACK_FLOW.map((f, idx) => (
            <li key={f.step} className="p-3 rounded-xl border border-slate-200 bg-white text-sm">
              <span className="font-mono text-xs font-bold text-blue-900">Step {idx + 1}</span>
              <span className="block font-semibold text-slate-900 mt-0.5">{f.step}</span>
              <span className="block text-slate-600 mt-0.5">{f.detail}</span>
            </li>
          ))}
        </ol>
        <p className="text-sm text-slate-700 leading-relaxed">
          Nothing is finished until the person who raised it is satisfied, or it has been closed with a reason.
        </p>

        <SubHeading icon={Users}>Who does what</SubHeading>
        <Table head={['Your part', 'What it means', 'What you can do']} rows={FEEDBACK_PARTS.map((p) => [p.part, p.meaning, p.canDo])} />

        <SubHeading icon={Layers}>What is on each tab</SubHeading>
        <p className="text-sm text-slate-700">Click Feedback in the top menu. A small red number on a tab shows how many items are waiting for you.</p>
        <dl className="my-3 rounded-xl border border-slate-200 bg-white divide-y divide-slate-100 text-sm">
          {FEEDBACK_TABS.map((tab) => (
            <div key={tab.name} className="p-3 sm:grid sm:grid-cols-[11rem_1fr] sm:gap-3">
              <dt className="font-semibold text-slate-900">{tab.name}</dt>
              <dd className="text-slate-700 leading-relaxed">{tab.description}</dd>
            </div>
          ))}
        </dl>

        <SubHeading icon={Users}>Who can read a piece of feedback</SubHeading>
        <ul className="space-y-1.5 text-sm text-slate-700 list-disc pl-5">
          <li>The person who sent it.</li>
          <li>Receivers at the office responsible for it, and at offices that held it earlier.</li>
          <li>People added to it by name.</li>
        </ul>
        <p className="mt-2 text-sm text-slate-700">Other users, including colleagues in the sender&apos;s own office, cannot see it. Internal notes are seen only by receivers.</p>

        <SubHeading icon={HelpCircle}>Words used here</SubHeading>
        <Table head={['Word', 'What it means']} rows={FEEDBACK_WORDS.map((w) => [w.word, w.meaning])} />

        <Callout type="note" title="If Feedback opens a Google Form">
          The new feedback pages have not been switched on for your portal yet. Ask your dashboard administrator.
        </Callout>
      </section>
    )}

    {visible['feedback-send'] && (
      <section id="feedback-send" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
        <Heading title="Sending feedback">
          Open the Send feedback tab and fill in the form. Your name and office are added for you. If you were on a dashboard when you opened the form, the system records which one, so the receiver knows what you were looking at.
        </Heading>

        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.form} />
        <p className="text-sm text-slate-700">A green message confirms your reference number and tells you when you should hear back.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.sent} />

        <SubHeading icon={Inbox}>Who receives it</SubHeading>
        <p className="text-sm text-slate-700 leading-relaxed">
          Feedback sent to your upper level goes to the nearest office above you that has someone on the portal who can receive it. If the zone above your woreda has nobody on the portal yet, for example, it goes on to the region. You do not need to know who that is.
        </p>

        <SubHeading icon={MessageSquare}>Writing feedback that gets solved quickly</SubHeading>
        <p className="text-sm text-slate-700">The office can only fix what it can find. A clear message saves days of questions back and forth.</p>
        <div className="my-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/60 text-sm">
            <h4 className="font-bold text-rose-900 flex items-center gap-2"><XCircle className="w-4 h-4" aria-hidden="true" />Hard to act on</h4>
            <ul className="mt-2 space-y-1 text-slate-800">{FEEDBACK_EXAMPLES.unclear.map((e) => <li key={e}>{e}</li>)}</ul>
          </div>
          <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/60 text-sm">
            <h4 className="font-bold text-emerald-900 flex items-center gap-2"><CheckCircle2 className="w-4 h-4" aria-hidden="true" />Easy to act on</h4>
            <ul className="mt-2 space-y-1 text-slate-800">{FEEDBACK_EXAMPLES.clear.map((e) => <li key={e}>{e}</li>)}</ul>
          </div>
        </div>
        <p className="text-sm text-slate-700">A good message answers four questions:</p>
        <Steps items={FEEDBACK_EXAMPLES.questions} />
        <Callout type="tip" title="One problem in each message">
          Two problems in one message are harder to track, and one may be forgotten. You can write in Amharic or English, as long as the office can read it.
        </Callout>

        <SubHeading icon={ArrowRight}>Sending to an office below you</SubHeading>
        <p className="text-sm text-slate-700 leading-relaxed">
          If you work at a higher level, you can also choose A unit below me. Type at least two letters of the office&apos;s name and click it in the list. This box only finds offices. To name a person, use Add a person.
        </p>

        <SubHeading icon={Users}>Adding a person</SubHeading>
        <p className="text-sm text-slate-700">If you know exactly who should see it, add them. They can read and reply, but they do not become responsible for it.</p>
        <Steps
          items={[
            'Click Add a person (optional).',
            'Type their complete email address, their username, or their first and last name, then click Find.',
            'Check that the name and office shown are the right ones.',
            'Click Select.',
          ]}
        />
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.person} />
        <Callout type="note" title="Part of a name finds nobody">
          This protects staff details. If you see No exact match, check the spelling, including the end of the email address such as .com. You can add up to 5 people.
        </Callout>
      </section>
    )}

    {visible['feedback-follow'] && (
      <section id="feedback-follow" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
        <Heading title="Following your feedback">
          Open My feedback to see everything you sent. You also get an email when the office answers or asks you something.
        </Heading>

        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.mine} />

        <SubHeading icon={Layers}>What each label means</SubHeading>
        <Table
          head={['You see', 'What it means', 'What to do']}
          rows={FEEDBACK_STATUSES.map((s) => [
            <span key="label" className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold whitespace-nowrap ${s.needsYou ? 'bg-rose-100 text-rose-800' : 'bg-blue-100 text-blue-900'}`}>{s.label}</span>,
            s.meaning,
            s.todo,
          ])}
        />

        <SubHeading icon={MessageSquare}>Replying to a question</SubHeading>
        <p className="text-sm text-slate-700">The blue message tells you the office needs something from you. Write your answer and click Send reply.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.reply} />

        <SubHeading icon={MessageSquare}>Adding more information</SubHeading>
        <p className="text-sm text-slate-700">While the office is working on it, you can add details at any time. Open the item, write under Add more information, and click Send.</p>

        <SubHeading icon={CheckCircle2}>Saying whether it is solved</SubHeading>
        <p className="text-sm text-slate-700">When the office answers, read the answer and choose Yes, this solved it or No, not solved. Your answer tells the office whether its work is finished.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.confirm} />

        <SubHeading icon={ArrowRight}>Reopening closed feedback</SubHeading>
        <p className="text-sm text-slate-700">If the problem comes back within 30 days of closing, open the item, click Still a problem? Reopen this feedback, write why, and click Reopen.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.reopen} />

        <SubHeading icon={Users}>If someone added you</SubHeading>
        <p className="text-sm text-slate-700">Feedback you were named on appears under My feedback, Added to me. Adding you does not make you responsible. The office it was sent to still answers it.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.added} />
      </section>
    )}

    {visible['feedback-receive'] && (
      <section id="feedback-receive" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
        <Heading title="Answering feedback">
          For users whose office receives feedback: woreda, zone, and region focal persons, HMIS officers, and Federal MoH staff. Managers will find the Area numbers and deadlines here.
        </Heading>

        <Callout type="note" title="Who can see this part">
          The Waiting on me and Area numbers tabs appear only if your account can receive feedback for an office.
        </Callout>

        <SubHeading icon={Inbox}>Waiting on me</SubHeading>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.waiting} />

        <SubHeading icon={MessageSquare}>Responding</SubHeading>
        <p className="text-sm text-slate-700">Click the reference number to open an item. Read the message and the conversation, choose what to do, write your message, and click the button.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.respond} />
        <Table head={['Choice', 'When to use it', 'What happens']} rows={FEEDBACK_RESPONSES.map((r) => [r.choice, r.when, r.result])} />

        <SubHeading icon={Layers}>More actions</SubHeading>
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4 items-start">
          <ScreenshotPlaceholder data={FEEDBACK_SHOTS.more} className="md:my-4" />
          <Table head={['Action', 'What it does']} rows={FEEDBACK_MORE_ACTIONS.map((a) => [a.action, a.detail])} />
        </div>
        <p className="text-sm text-slate-700">To reach an office at the same level as yours, send it up first.</p>

        <SubHeading icon={Clock}>Deadlines</SubHeading>
        <Table head={['Priority', 'Example', 'First response', 'Finish by']} rows={FEEDBACK_DEADLINES.map((d) => [d.priority, d.example, d.first, d.finish])} />
        <p className="text-sm text-slate-700">All feedback starts as Normal. The clock stops while the item is waiting for the sender.</p>

        <SubHeading icon={CheckCircle2}>A simple daily routine</SubHeading>
        <Steps items={FEEDBACK_DAILY_ROUTINE} />

        <SubHeading icon={MessageSquare}>Writing a good answer</SubHeading>
        <ul className="space-y-1.5 text-sm text-slate-700 list-disc pl-5">
          <li>Say what you found and what you did, in plain words. For example: &quot;The March figure was entered twice. We corrected it on 12 March, and the dashboard now shows 62%.&quot;</li>
          <li>Say if the sender needs to do anything, and when the change will be visible.</li>
          <li>When you decline, give a reason the sender can understand and, if you can, say where they should go instead.</li>
        </ul>

        <SubHeading icon={XCircle}>Hiding a message or screenshot</SubHeading>
        <p className="text-sm text-slate-700">If a message or screenshot should not be seen, click Hide next to it and confirm. It is hidden from everyone, and the history records that it was hidden. It stays stored, so ask your administrator if it must be deleted completely.</p>

        <SubHeading icon={Layers}>Area numbers</SubHeading>
        <p className="text-sm text-slate-700">Counts for your office and the offices below it, for the last 30, 90, or 365 days. It shows numbers only, never the messages.</p>
        <ScreenshotPlaceholder data={FEEDBACK_SHOTS.stats} />
        <Table head={['Number', 'Meaning']} rows={FEEDBACK_AREA_NUMBERS.map((n) => [n.name, n.meaning])} />
        <Callout type="tip" title="Using the numbers in review meetings">
          Look at Overdue now and Where items are waiting first. A falling First response on time share often means an office has nobody active on the portal. Many items of the same kind from one area can show a training need or a data problem worth fixing at the source.
        </Callout>
      </section>
    )}

    {visible['feedback-help'] && (
      <section id="feedback-help" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
        <Heading title="Feedback questions">
          Emails you will receive, messages you may see, and common questions.
        </Heading>

        <SubHeading icon={Mail}>Emails you will receive</SubHeading>
        <p className="text-sm text-slate-700">Emails are short and contain a link. The conversation stays on the portal, so sign in to read and reply. Replies sent to the email are not read.</p>
        <Table head={['What happened', 'Who gets an email']} rows={FEEDBACK_EMAILS.map((e) => [e.event, e.to])} />

        <SubHeading icon={AlertTriangle}>Messages you may see</SubHeading>
        <Table head={['What you see', 'What it means', 'What to do']} rows={FEEDBACK_PROBLEMS.map((p) => [p.message, p.meaning, p.todo])} />

        <SubHeading icon={HelpCircle}>Common questions</SubHeading>
        <div className="my-3 space-y-3">
          {FEEDBACK_FAQ.map((f) => (
            <div key={f.q} className="p-4 rounded-xl border border-slate-200 bg-white text-sm">
              <h4 className="font-bold text-slate-900">{f.q}</h4>
              <p className="mt-1 text-slate-700">{f.a}</p>
            </div>
          ))}
        </div>

        <SubHeading icon={Users}>On a phone, or with larger text</SubHeading>
        <ul className="space-y-1.5 text-sm text-slate-700 list-disc pl-5">
          <li>The feedback pages work on phones without any extra app.</li>
          <li>Press Ctrl and + to zoom in, or spread two fingers on a phone screen.</li>
          <li>Open Accessibility in the top bar of the portal and turn on High contrast. The feedback pages follow the same choice, and so does Dark mode.</li>
          <li>Press Tab to move between boxes and buttons, and Enter to press a button.</li>
          <li>When the internet is slow, click Send feedback only once and wait. If the page says it expired, check My feedback before sending again.</li>
        </ul>
      </section>
    )}
  </>
);
