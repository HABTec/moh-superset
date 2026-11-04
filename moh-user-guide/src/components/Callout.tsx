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
import { Info, AlertCircle, Lightbulb, AlertTriangle } from 'lucide-react';

interface CalloutProps {
  type: 'tip' | 'important' | 'note' | 'caution';
  title?: string;
  children: React.ReactNode;
}

export const Callout: React.FC<CalloutProps> = ({ type, title, children }) => {
  const configs = {
    tip: {
      label: 'Tip',
      icon: Lightbulb,
      containerBg: 'bg-emerald-50/70 border-emerald-200/80 text-emerald-950',
      iconColor: 'text-emerald-700',
      badgeBg: 'bg-emerald-100/90 text-emerald-800'
    },
    important: {
      label: 'Important',
      icon: AlertCircle,
      containerBg: 'bg-amber-50/80 border-amber-200/90 text-amber-950',
      iconColor: 'text-amber-700',
      badgeBg: 'bg-amber-100 text-amber-900'
    },
    note: {
      label: 'Note',
      icon: Info,
      containerBg: 'bg-blue-50/70 border-blue-200/80 text-blue-950',
      iconColor: 'text-blue-700',
      badgeBg: 'bg-blue-100 text-blue-900'
    },
    caution: {
      label: 'Caution',
      icon: AlertTriangle,
      containerBg: 'bg-rose-50/70 border-rose-200/80 text-rose-950',
      iconColor: 'text-rose-700',
      badgeBg: 'bg-rose-100 text-rose-900'
    }
  };

  const current = configs[type];
  const Icon = current.icon;

  return (
    <div
      role="region"
      aria-label={`${current.label}: ${title || 'Information'}`}
      className={`my-4 p-4 rounded-xl border ${current.containerBg} transition-colors`}
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">
          <Icon className={`w-5 h-5 ${current.iconColor}`} aria-hidden="true" />
        </div>
        <div className="flex-1 text-sm leading-relaxed">
          <div className="flex items-center gap-2 mb-1.5 font-semibold">
            <span className={`px-2 py-0.5 text-xs font-bold uppercase tracking-wider rounded ${current.badgeBg}`}>
              {current.label}
            </span>
            {title && <span className="text-slate-900">{title}</span>}
          </div>
          <div className="text-slate-800">{children}</div>
        </div>
      </div>
    </div>
  );
};
