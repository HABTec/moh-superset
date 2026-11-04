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
import { NAV_ITEMS } from '../data/guideData';
import { NavItem } from '../types/guide';
import {
  Menu, X, BookOpen, ChevronRight, ChevronLeft, ChevronDown,
  Database, HelpCircle, Layers, Shield, Eye, SunMoon,
  Filter, BarChart2, LayoutDashboard, CheckCircle2,
  Calendar, GitCompare, Activity, Sparkles, AlertTriangle,
  LogIn, PanelLeftClose, PanelLeftOpen
} from 'lucide-react';

const NAV_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  'welcome': BookOpen,
  'login-navigation': LogIn,
  'filters': Filter,
  'reading-charts': BarChart2,
  'module-summary': LayoutDashboard,
  'module-data-quality': CheckCircle2,
  'module-routine-indicators': Calendar,
  'module-monthly-quarterly': Calendar,
  'module-multi-source': Database,
  'module-triangulation': GitCompare,
  'module-health-intelligence': Activity,
  'module-ai-assistant': Sparkles,
  'data-sources': Layers,
  'troubleshooting': AlertTriangle,
  'support': HelpCircle,
};

interface Props {
  activeId: string;
  onNavigate: (id: string) => void;
  onOpenAccessibility?: () => void;
  isHighContrast?: boolean;
  readingProgress: number;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const SidebarNav: React.FC<Props> = ({
  activeId,
  onNavigate,
  onOpenAccessibility,
  isHighContrast = false,
  readingProgress,
  isCollapsed,
  onToggleCollapse,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const categories = [
    'GETTING STARTED',
    'USING THE DASHBOARD',
    'COMPARING AND EXPLORING DATA',
    'REFERENCE'
  ] as const;

  // Category folding state (Accordion state)
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem('moh_expanded_categories');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {
      // ignore
    }
    return {
      'GETTING STARTED': true,
      'USING THE DASHBOARD': true,
      'COMPARING AND EXPLORING DATA': true,
      'REFERENCE': true,
    };
  });

  const toggleCategory = (cat: string) => {
    setExpandedCategories((prev) => {
      const next = { ...prev, [cat]: !prev[cat] };
      try {
        localStorage.setItem('moh_expanded_categories', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Auto-expand category on scroll: when active section changes to a collapsed category, unfold it automatically
  useEffect(() => {
    const activeItem = NAV_ITEMS.find((item) => item.id === activeId);
    if (activeItem && activeItem.category) {
      setExpandedCategories((prev) => {
        if (!prev[activeItem.category]) {
          const next = { ...prev, [activeItem.category]: true };
          try {
            localStorage.setItem('moh_expanded_categories', JSON.stringify(next));
          } catch {
            // ignore
          }
          return next;
        }
        return prev;
      });
    }
  }, [activeId]);

  const handleLinkClick = (id: string) => {
    onNavigate(id);
    setMobileMenuOpen(false);
  };

  return (
    <>
      {/* Mobile Sticky Navigation Banner */}
      <div className="no-print lg:hidden sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 px-4 py-2.5 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-toc-panel"
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors cursor-pointer border border-slate-200"
        >
          {mobileMenuOpen ? <X className="w-4 h-4 text-slate-600" /> : <Menu className="w-4 h-4 text-slate-600" />}
          <span>Table of Contents</span>
          <span className="text-[11px] text-slate-500 font-mono">({Math.round(readingProgress)}%)</span>
        </button>
      </div>

      {/* Mobile Drawer with Accordion Folding */}
      {mobileMenuOpen && (
        <div
          id="mobile-toc-panel"
          className="no-print lg:hidden fixed inset-x-0 top-[53px] bottom-0 z-40 bg-slate-900/40 backdrop-blur-xs flex flex-col"
        >
          <div className="bg-white max-h-[80vh] overflow-y-auto p-4 border-b border-slate-200 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Guide Navigation
              </span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
                aria-label="Close menu"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {categories.map((cat) => {
              const items = NAV_ITEMS.filter((item) => item.category === cat);
              const isOpen = expandedCategories[cat] !== false;

              return (
                <div key={cat} className="space-y-1 border-b border-slate-100 pb-2.5 last:border-none">
                  {/* Category disclosure header */}
                  <button
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    aria-expanded={isOpen}
                    className="w-full flex items-center justify-between px-2 py-1 text-[11px] font-bold tracking-wider text-slate-600 hover:text-slate-900 uppercase cursor-pointer"
                  >
                    <span className="flex items-center gap-1.5">
                      <span>{cat}</span>
                      <span className="text-[10px] text-slate-400 font-mono">({items.length})</span>
                    </span>
                    <ChevronDown
                      className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-blue-900' : ''
                      }`}
                    />
                  </button>

                  {/* Category Items */}
                  {isOpen && (
                    <ul className="space-y-0.5 pt-1 pl-1">
                      {items.map((item) => {
                        const IconComponent = NAV_ICONS[item.id] || BookOpen;
                        return (
                          <li key={item.id}>
                            <button
                              type="button"
                              onClick={() => handleLinkClick(item.id)}
                              className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center justify-between cursor-pointer ${
                                activeId === item.id
                                  ? 'bg-blue-900 text-white font-semibold'
                                  : 'text-slate-700 hover:bg-slate-100'
                              }`}
                            >
                              <span className="flex items-center gap-2 truncate">
                                <IconComponent className="w-3.5 h-3.5 shrink-0" />
                                <span className="truncate">{item.title}</span>
                              </span>
                              {activeId === item.id && (
                                <ChevronRight className="w-3.5 h-3.5 text-blue-200 shrink-0" />
                              )}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Desktop Persistent Left Sidebar (Collapsible Rail ↔ Full Width with Accordion Category Folding) */}
      <aside
        aria-label="User Guide Navigation"
        className={`hidden lg:block shrink-0 sticky top-[73px] self-start max-h-[calc(100vh-80px)] overflow-y-auto py-5 transition-all duration-300 ease-in-out ${
          isCollapsed ? 'w-16 px-1.5' : 'w-72 pr-3 pl-1'
        }`}
      >
        {/* Top Header / Toggle Rail */}
        <div className={`flex items-center mb-4 ${isCollapsed ? 'justify-center' : 'justify-between px-1'}`}>
          {!isCollapsed ? (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Contents
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  [14 Topics]
                </span>
              </div>
              <button
                type="button"
                onClick={onToggleCollapse}
                className="p-1.5 text-slate-500 hover:text-slate-900 hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
                title="Collapse sidebar to icon rail (Shortcut: [)"
                aria-label="Collapse sidebar to icon rail"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="p-2 text-slate-600 hover:text-blue-900 hover:bg-blue-50 border border-slate-200 rounded-xl transition-all cursor-pointer shadow-2xs focus-visible:outline-2 focus-visible:outline-blue-700"
              title="Expand sidebar (Shortcut: [)"
              aria-label="Expand sidebar"
            >
              <PanelLeftOpen className="w-4 h-4 text-blue-800" />
            </button>
          )}
        </div>

        {/* Reading progress bar */}
        {!isCollapsed ? (
          <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl">
            <div className="flex items-center justify-between text-xs text-slate-600 mb-1.5">
              <span className="font-semibold text-slate-800">Reading Progress</span>
              <span className="font-mono text-blue-900 font-bold tabular-nums">
                {Math.round(readingProgress)}%
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-blue-900 h-full transition-all duration-300"
                style={{ width: `${readingProgress}%` }}
                role="progressbar"
                aria-valuenow={Math.round(readingProgress)}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
          </div>
        ) : (
          <div
            className="mb-4 mx-auto w-10 flex flex-col items-center py-1.5 bg-slate-100 rounded-lg border border-slate-200"
            title={`Reading progress: ${Math.round(readingProgress)}%`}
          >
            <span className="text-[10px] font-mono font-bold text-blue-900 tabular-nums">
              {Math.round(readingProgress)}%
            </span>
            <div className="w-6 bg-slate-200 rounded-full h-1 mt-1 overflow-hidden">
              <div
                className="bg-blue-900 h-full"
                style={{ width: `${readingProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Navigation Categories and Links (Accordion Structure) */}
        <nav className="space-y-3">
          {categories.map((cat) => {
            const items = NAV_ITEMS.filter((item) => item.category === cat);
            const isOpen = expandedCategories[cat] !== false;
            const hasActiveChild = items.some((item) => item.id === activeId);

            return (
              <div key={cat} className="space-y-1">
                {/* Accordion Category Header (Desktop Expanded) */}
                {!isCollapsed && (
                  <button
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    aria-expanded={isOpen}
                    aria-controls={`category-group-${cat.toLowerCase().replace(/\s+/g, '-')}`}
                    className={`w-full flex items-center justify-between text-left px-2 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-colors cursor-pointer group ${
                      hasActiveChild
                        ? 'text-blue-900 bg-blue-50/60 font-extrabold'
                        : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100/70'
                    }`}
                  >
                    <span className="flex items-center gap-1.5 truncate">
                      <span className="truncate">{cat}</span>
                      <span className="text-[10px] font-mono font-normal text-slate-400">
                        ({items.length})
                      </span>
                    </span>
                    <ChevronDown
                      className={`w-3.5 h-3.5 shrink-0 transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-blue-900' : 'text-slate-400 group-hover:text-slate-700'
                      }`}
                    />
                  </button>
                )}

                {/* Divider in Collapsed Mode */}
                {isCollapsed && (
                  <div className="w-full border-t border-slate-200 my-2" aria-hidden="true" />
                )}

                {/* Items List (Collapsible in Expanded Mode, or always shown as icons in Mini-Rail Mode) */}
                {(!isCollapsed ? isOpen : true) && (
                  <ul
                    id={`category-group-${cat.toLowerCase().replace(/\s+/g, '-')}`}
                    className="space-y-0.5 animate-in fade-in duration-150"
                  >
                    {items.map((item) => {
                      const isActive = activeId === item.id;
                      const IconComponent = NAV_ICONS[item.id] || BookOpen;

                      return (
                        <li key={item.id} className="relative group">
                          <a
                            href={`#${item.id}`}
                            onClick={(e) => {
                              e.preventDefault();
                              handleLinkClick(item.id);
                            }}
                            className={`w-full text-left rounded-xl transition-all flex items-center cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700 ${
                              isCollapsed
                                ? 'justify-center p-2.5 hover:bg-slate-200/70'
                                : 'px-3 py-2 text-xs font-medium justify-between hover:bg-slate-100/80'
                            } ${
                              isActive
                                ? 'bg-blue-900 text-white font-semibold shadow-xs hover:bg-blue-900'
                                : 'text-slate-700 hover:text-blue-950'
                            }`}
                            aria-current={isActive ? 'location' : undefined}
                            title={isCollapsed ? item.title : undefined}
                          >
                            <div className={`flex items-center gap-2.5 min-w-0 ${isCollapsed ? 'justify-center' : ''}`}>
                              <IconComponent className={`shrink-0 ${
                                isCollapsed ? 'w-5 h-5' : 'w-4 h-4'
                              } ${
                                isActive ? 'text-white' : 'text-slate-500 group-hover:text-blue-900'
                              }`} />
                              {!isCollapsed && (
                                <span className="truncate">{item.title}</span>
                              )}
                            </div>

                            {!isCollapsed && isActive && (
                              <ChevronRight className="w-3.5 h-3.5 text-blue-200 shrink-0 ml-1" />
                            )}
                          </a>

                          {/* Hover Tooltip in Collapsed Mode */}
                          {isCollapsed && (
                            <div className="absolute left-full ml-2.5 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center z-50 pointer-events-none">
                              <div className="bg-slate-900 text-white text-xs px-2.5 py-1.5 rounded-lg shadow-lg whitespace-nowrap border border-slate-700">
                                <span className="font-semibold block">{item.title}</span>
                                <span className="text-[10px] text-slate-400 block">{item.category}</span>
                              </div>
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })}
        </nav>

        {/* Quick Tools Box in Sidebar */}
        <div className="mt-6 pt-4 border-t border-slate-200 space-y-2">

          {/* Accessibility Tool */}
          {onOpenAccessibility && (
            <button
              type="button"
              onClick={onOpenAccessibility}
              className={`w-full rounded-xl border text-xs font-semibold flex items-center transition-colors cursor-pointer group relative ${
                isCollapsed ? 'justify-center p-2.5' : 'px-3 py-2 gap-2'
              } ${
                isHighContrast
                  ? 'border-amber-400 bg-amber-950/40 text-amber-200 font-bold ring-1 ring-amber-400'
                  : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
              }`}
              title={isCollapsed ? "Accessibility & Contrast Settings" : undefined}
            >
              <Eye className={`${isCollapsed ? 'w-5 h-5' : 'w-4 h-4'} ${isHighContrast ? 'text-amber-300' : 'text-blue-800'} shrink-0`} />
              {!isCollapsed && (
                <>
                  <div className="text-left flex-1 min-w-0">
                    <span className="block truncate">Accessibility & Contrast</span>
                    <span className={`block text-[10px] font-normal truncate ${isHighContrast ? 'text-amber-300 font-semibold' : 'text-slate-500'}`}>
                      {isHighContrast ? 'High Contrast: Active' : 'Text size and contrast'}
                    </span>
                  </div>
                  <ChevronRight className={`w-3.5 h-3.5 shrink-0 ${isHighContrast ? 'text-amber-300' : 'text-slate-400'}`} />
                </>
              )}

              {isCollapsed && (
                <div className="absolute left-full ml-2.5 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center z-50 pointer-events-none">
                  <div className="bg-slate-900 text-white text-xs px-2.5 py-1.5 rounded-lg shadow-lg whitespace-nowrap border border-slate-700">
                    <span className="font-semibold block">Accessibility & Contrast</span>
                    <span className="text-[10px] text-slate-400 block">
                      {isHighContrast ? 'High Contrast: Active' : 'Options & View'}
                    </span>
                  </div>
                </div>
              )}
            </button>
          )}
        </div>
      </aside>
    </>
  );
};
