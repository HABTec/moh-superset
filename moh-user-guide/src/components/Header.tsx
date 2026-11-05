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
import { ArrowLeft, Printer, Search, Calendar, HelpCircle, Eye, SunMoon } from 'lucide-react';

interface HeaderProps {
  onPrint: () => void;
  onOpenSearch: () => void;
  onOpenSupport: () => void;
  onOpenAccessibility: () => void;
  isHighContrast: boolean;
  onToggleHighContrast: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onPrint,
  onOpenSearch,
  onOpenSupport,
  onOpenAccessibility,
  isHighContrast,
  onToggleHighContrast,
}) => {
  return (
    <>
      <header className="print-header lg:sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-2xs">
        {/* Top Institutional Bar */}
        <div className="bg-slate-900 text-slate-200 px-4 py-1.5 text-[11px] flex flex-wrap items-center justify-between gap-2 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" aria-hidden="true" />
            <span className="font-semibold text-white tracking-wide">FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA</span>
            <span className="text-slate-500">·</span>
            <span className="text-slate-300">MINISTRY OF HEALTH (MoH)</span>
          </div>

          <div className="flex items-center gap-4 text-slate-300">
            <div className="flex items-center gap-1.5 text-slate-400">
              <Calendar className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
              <span>Last updated: 3 November 2026</span>
            </div>
            <button
              onClick={onOpenSupport}
              type="button"
              className="no-print text-slate-300 hover:text-white transition-colors flex items-center gap-1 cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-400"
            >
              <HelpCircle className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Getting help</span>
            </button>
          </div>
        </div>

        {/* Main Header Container */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          {/* Left: logo and titles */}
          <div className="flex items-center gap-3.5 min-w-0">
            <img
              src={`${import.meta.env.BASE_URL}images/guide/moh-logo.png`}
              alt="Ministry of Health, Ethiopia"
              className="h-9 sm:h-11 w-auto shrink-0"
            />

            {/* Title & Subtitle */}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight truncate">
                  User Guide
                </h1>
              </div>
              <p className="text-xs sm:text-sm text-slate-600 truncate">
                MOH Performance Monitoring Dashboard
              </p>
            </div>
          </div>

          {/* Right Action Controls */}
          <div className="no-print flex items-center gap-2 shrink-0">
            {/* Quick Search trigger button */}
            <button
              type="button"
              onClick={onOpenSearch}
              className="hidden lg:flex items-center gap-2 px-3 py-1.5 text-xs text-slate-500 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
              aria-label="Search the guide"
            >
              <Search className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
              <span>Search guide…</span>
              <kbd className="font-mono text-[10px] bg-white border border-slate-300 px-1.5 py-0.5 rounded text-slate-500">
                /
              </kbd>
            </button>

            {/* Quick 1-Click High Contrast Toggle */}
            <button
              type="button"
              onClick={onToggleHighContrast}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700 ${
                isHighContrast
                  ? 'bg-amber-400 text-black font-extrabold ring-2 ring-white border-2 border-amber-300 shadow-md'
                  : 'bg-white hover:bg-slate-100 text-slate-700 border border-slate-300'
              }`}
              title="Turn high contrast on or off"
              aria-pressed={isHighContrast}
            >
              <SunMoon className={`w-3.5 h-3.5 ${isHighContrast ? 'text-black font-extrabold' : 'text-slate-600'}`} aria-hidden="true" />
              <span className="hidden md:inline font-bold">
                {isHighContrast ? 'High Contrast: ON' : 'High Contrast'}
              </span>
              <span className="md:hidden font-bold">Contrast</span>
            </button>

            {/* Full Accessibility Menu Trigger */}
            <button
              type="button"
              onClick={onOpenAccessibility}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
              title="Open Accessibility Settings (Text Size, Spacing, Links)"
              aria-label="Open Accessibility Settings"
            >
              <Eye className="w-3.5 h-3.5 text-blue-800" aria-hidden="true" />
              <span className="hidden sm:inline">Accessibility</span>
            </button>

            {/* Print action */}
            <button
              type="button"
              onClick={onPrint}
              className="p-1.5 sm:px-3 sm:py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
              title="Print or Save User Manual as PDF"
              aria-label="Print guide"
            >
              <Printer className="w-4 h-4 text-slate-600" aria-hidden="true" />
              <span className="hidden sm:inline">Print</span>
            </button>

            {/* "Back to Portal" Button */}
            <a
              href="/"
              className="px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-900 hover:bg-blue-800 rounded-lg transition-colors flex items-center gap-1.5 shadow-2xs cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Back to Portal</span>
            </a>
          </div>
        </div>
      </header>
    </>
  );
};
