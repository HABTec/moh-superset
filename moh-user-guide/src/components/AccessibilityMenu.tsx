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
import { AccessibilitySettings } from '../types/accessibility';
import {
  X, Eye, SunMoon, Type, Space, Link as LinkIcon,
  RotateCcw, Sparkles, Check, Focus, ZapOff, CheckCircle2
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  settings: AccessibilitySettings;
  onUpdateSettings: (updater: (prev: AccessibilitySettings) => AccessibilitySettings) => void;
  onResetSettings: () => void;
}

export const AccessibilityMenu: React.FC<Props> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  onResetSettings
}) => {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="accessibility-menu-title"
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-800 text-white flex items-center justify-center">
              <Eye className="w-4 h-4" aria-hidden="true" />
            </div>
            <div>
              <h3 id="accessibility-menu-title" className="text-base font-bold">
                Accessibility Preferences
              </h3>
              <p className="text-xs text-slate-300">
                Change how this guide looks
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
            aria-label="Close accessibility menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5 text-sm text-slate-800 max-h-[75vh] overflow-y-auto">
          {/* 1. HIGH CONTRAST VIEW (FEATURED) */}
          <div className="p-4 rounded-xl border-2 border-blue-900/20 bg-blue-50/50 hover:bg-blue-50/80 transition-all">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <SunMoon className="w-5 h-5 text-blue-900 mt-0.5 shrink-0" aria-hidden="true" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900">High Contrast View</span>
                  </div>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                    Maximizes visual legibility with stark contrast ratios, solid dark canvas, crisp text, and high-visibility borders.
                  </p>
                </div>
              </div>

              {/* Toggle Switch */}
              <button
                type="button"
                role="switch"
                aria-checked={settings.highContrast}
                onClick={() =>
                  onUpdateSettings((prev) => ({
                    ...prev,
                    highContrast: !prev.highContrast
                  }))
                }
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-800 focus:ring-offset-2 ${
                  settings.highContrast ? 'bg-blue-900' : 'bg-slate-300'
                }`}
                aria-label="Toggle High Contrast View"
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                    settings.highContrast ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
            {settings.highContrast && (
              <div className="mt-3 pt-2.5 border-t border-blue-200/80 text-xs text-blue-950 flex items-center gap-1.5 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                <span>High Contrast View is currently ACTIVE across all modules.</span>
              </div>
            )}
          </div>

          {/* 2. FONT SIZE SCALING */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-semibold text-slate-900 text-xs uppercase tracking-wider">
              <Type className="w-4 h-4 text-slate-600" />
              <span>Text Size Scaling</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'standard', label: 'Standard (100%)', sample: 'Aa' },
                { id: 'large', label: 'Large (115%)', sample: 'Aa+' },
                { id: 'xlarge', label: 'Extra Large (130%)', sample: 'Aa++' }
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() =>
                    onUpdateSettings((prev) => ({
                      ...prev,
                      fontSize: opt.id as any
                    }))
                  }
                  className={`p-2.5 rounded-xl border text-center transition-all cursor-pointer ${
                    settings.fontSize === opt.id
                      ? 'border-blue-900 bg-blue-50/80 font-bold text-blue-950 shadow-xs ring-1 ring-blue-800'
                      : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                  }`}
                  aria-pressed={settings.fontSize === opt.id}
                >
                  <span className="block font-bold text-sm mb-0.5">{opt.sample}</span>
                  <span className="text-[11px] block">{opt.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 3. RELAXED TEXT SPACING */}
          <div className="p-3.5 rounded-xl border border-slate-200 bg-white flex items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <Space className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-slate-900 block text-xs">
                  Relaxed Text Spacing
                </span>
                <span className="text-xs text-slate-500">
                  Increases line height, letter spacing, and word spacing for improved reading flow.
                </span>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.textSpacing}
              onClick={() =>
                onUpdateSettings((prev) => ({
                  ...prev,
                  textSpacing: !prev.textSpacing
                }))
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-800 ${
                settings.textSpacing ? 'bg-blue-900' : 'bg-slate-300'
              }`}
              aria-label="Toggle Relaxed Text Spacing"
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                  settings.textSpacing ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* 4. UNDERLINE ALL LINKS */}
          <div className="p-3.5 rounded-xl border border-slate-200 bg-white flex items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <LinkIcon className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-slate-900 block text-xs">
                  Underline In-Page Links
                </span>
                <span className="text-xs text-slate-500">
                  Adds permanent underline styling so links never rely on color alone.
                </span>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.underlineLinks}
              onClick={() =>
                onUpdateSettings((prev) => ({
                  ...prev,
                  underlineLinks: !prev.underlineLinks
                }))
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-800 ${
                settings.underlineLinks ? 'bg-blue-900' : 'bg-slate-300'
              }`}
              aria-label="Toggle Underline In-Page Links"
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                  settings.underlineLinks ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* 5. ENHANCED FOCUS RINGS */}
          <div className="p-3.5 rounded-xl border border-slate-200 bg-white flex items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <Focus className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-slate-900 block text-xs">
                  Enhanced Focus Indicators
                </span>
                <span className="text-xs text-slate-500">
                  Displays bold, high-visibility focus borders for keyboard tab navigation.
                </span>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.enhancedFocus}
              onClick={() =>
                onUpdateSettings((prev) => ({
                  ...prev,
                  enhancedFocus: !prev.enhancedFocus
                }))
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-800 ${
                settings.enhancedFocus ? 'bg-blue-900' : 'bg-slate-300'
              }`}
              aria-label="Toggle Enhanced Focus Indicators"
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                  settings.enhancedFocus ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* 6. REDUCED MOTION */}
          <div className="p-3.5 rounded-xl border border-slate-200 bg-white flex items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <ZapOff className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold text-slate-900 block text-xs">
                  Reduced Motion
                </span>
                <span className="text-xs text-slate-500">
                  Disables smooth scroll jumps and animations for users sensitive to vestibular motion.
                </span>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.reducedMotion}
              onClick={() =>
                onUpdateSettings((prev) => ({
                  ...prev,
                  reducedMotion: !prev.reducedMotion
                }))
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-800 ${
                settings.reducedMotion ? 'bg-blue-900' : 'bg-slate-300'
              }`}
              aria-label="Toggle Reduced Motion"
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                  settings.reducedMotion ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-100 border-t border-slate-200 flex items-center justify-between text-xs">
          <button
            type="button"
            onClick={onResetSettings}
            className="flex items-center gap-1.5 text-slate-600 hover:text-slate-900 font-medium cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset to Defaults</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 text-white rounded-lg font-semibold hover:bg-slate-800 transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
