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
import React, { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';

interface Props {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  forceState?: boolean | null; // controlled by parent "Expand all" / "Collapse all"
}

export const ExpandableDetail: React.FC<Props> = ({
  id,
  title,
  subtitle,
  children,
  defaultOpen = false,
  forceState = null
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  useEffect(() => {
    if (forceState !== null) {
      setIsOpen(forceState);
    }
  }, [forceState]);

  const contentId = `expandable-content-${id}`;
  const headerId = `expandable-header-${id}`;

  return (
    <div className="my-4 border border-slate-200 rounded-xl bg-slate-50/50 overflow-hidden transition-all">
      <button
        id={headerId}
        type="button"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen(!isOpen)}
        className="no-print w-full px-4 py-3.5 flex items-center justify-between text-left hover:bg-slate-100/70 transition-colors focus-visible:outline-2 focus-visible:outline-blue-700 cursor-pointer"
      >
        <div className="flex-1 pr-3">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 bg-slate-200/70 px-1.5 py-0.5 rounded">
              Advanced Detail
            </span>
            <span className="text-sm font-semibold text-slate-900">{title}</span>
          </div>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
        <ChevronDown
          className={`w-4 h-4 text-slate-500 shrink-0 transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-blue-700' : ''
          }`}
          aria-hidden="true"
        />
      </button>

      <div
        id={contentId}
        role="region"
        aria-labelledby={headerId}
        className={`${isOpen ? '' : 'hidden'} print-expandable-content px-4 py-3.5 bg-white border-t border-slate-200 text-sm text-slate-700 leading-relaxed space-y-2`}
      >
        {children}
      </div>
    </div>
  );
};
