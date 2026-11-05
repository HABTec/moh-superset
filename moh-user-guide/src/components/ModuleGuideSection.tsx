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
import { ModuleSection } from '../types/guide';
import { ScreenshotPlaceholder } from './ScreenshotPlaceholder';
import { Callout } from './Callout';
import { AlertTriangle, BarChart2, HelpCircle, Layers, Sliders } from 'lucide-react';

interface Props {
  module: ModuleSection;
}

export const ModuleGuideSection: React.FC<Props> = ({ module }) => {
  return (
    <article
      id={module.id}
      aria-labelledby={`heading-${module.id}`}
      className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24 first:pt-0"
    >
      <div className="mb-4">
        <span className="font-mono text-xs font-bold text-blue-900 bg-blue-100/70 border border-blue-200 px-2 py-0.5 rounded">
          Section {module.badgeNumber}
        </span>
        <h3 id={`heading-${module.id}`} className="mt-2 text-2xl font-bold text-slate-900 tracking-tight">
          {module.name}
        </h3>
        <p className="text-base text-slate-600 mt-1 leading-relaxed">{module.shortSummary}</p>
      </div>

      <div className="my-5 p-4 rounded-xl bg-blue-50/50 border border-blue-100">
        <div className="flex items-start gap-2.5">
          <HelpCircle className="w-4 h-4 text-blue-800 shrink-0 mt-1" aria-hidden="true" />
          <div className="text-sm text-slate-800 leading-relaxed space-y-1.5">
            <p><strong className="text-blue-950">The question it answers:</strong> {module.purpose}</p>
            <p><strong className="text-blue-950">When to use it:</strong> {module.whenToUse}</p>
          </div>
        </div>
      </div>

      {module.accessNote && (
        <Callout type="note" title="Who can see this section">
          {module.accessNote}
        </Callout>
      )}

      <div className="my-6">
        <h4 className="text-base font-bold text-slate-900 mb-2">How to open it</h4>
        <ol className="list-none space-y-2 text-sm text-slate-700">
          {module.howToOpen.map((step, idx) => (
            <li key={idx} className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full bg-slate-900 text-white font-mono text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                {idx + 1}
              </span>
              <span className="flex-1 pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      <ScreenshotPlaceholder data={module.screenshot} />

      <div className="my-6">
        <h4 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
          <Layers className="w-4 h-4 text-blue-800" aria-hidden="true" />
          <span>What is on each tab</span>
        </h4>
        <dl className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100 text-sm">
          {module.tabs.map((tab) => (
            <div key={tab.name} className="p-3 sm:grid sm:grid-cols-[11rem_1fr] sm:gap-3">
              <dt className="font-semibold text-slate-900">{tab.name}</dt>
              <dd className="text-slate-700 leading-relaxed">{tab.description}</dd>
            </div>
          ))}
        </dl>
      </div>

      {module.extraScreenshots?.map((shot) => (
        <ScreenshotPlaceholder key={shot.id} data={shot} />
      ))}

      <div className="my-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl border border-slate-200 bg-white">
          <h4 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-800" aria-hidden="true" />
            <span>Filters you can use</span>
          </h4>
          <ul className="space-y-1.5 text-sm text-slate-700 list-disc pl-4">
            {module.filters.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 bg-white">
          <h4 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-blue-800" aria-hidden="true" />
            <span>How to read it</span>
          </h4>
          <ul className="space-y-1.5 text-sm text-slate-700 list-disc pl-4">
            {module.howToRead.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>

      <div className="my-6">
        <h4 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-700" aria-hidden="true" />
          <span>If something looks wrong</span>
        </h4>
        <ul className="space-y-2 text-sm text-slate-700 bg-amber-50/40 p-3.5 rounded-xl border border-amber-200/70 list-disc pl-7">
          {module.ifSomethingLooksWrong.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </div>
    </article>
  );
};
