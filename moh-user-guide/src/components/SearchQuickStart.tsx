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
import React, { useState, useEffect, useRef } from 'react';
import {
  Search, X, Sparkles, Filter, Database, CheckCircle2,
  Compass, ArrowRight, CornerDownLeft, FileText, Layers,
  AlertTriangle, BookOpen, ExternalLink, HelpCircle
} from 'lucide-react';
import {
  NAV_ITEMS,
  MODULES_DATA,
  FILTER_OPTIONS,
  DATA_SOURCES,
  TROUBLESHOOTING_ITEMS
} from '../data/guideData';

export interface SearchDropdownResult {
  id: string;
  title: string;
  subtitle: string;
  category: 'Section' | 'Module' | 'Filter' | 'Data Source' | 'Troubleshooting';
  anchorId: string;
}

interface Props {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSelectQuickLink: (anchorId: string) => void;
  onFilterPageByQuery?: (q: string) => void;
  isPageFiltered?: boolean;
  onClearPageFilter?: () => void;
  searchInputRef: React.RefObject<HTMLInputElement | null>;
}

export const SearchQuickStart: React.FC<Props> = ({
  searchQuery,
  onSearchChange,
  onSelectQuickLink,
  onFilterPageByQuery,
  isPageFiltered = false,
  onClearPageFilter,
  searchInputRef
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownListRef = useRef<HTMLUListElement>(null);

  const query = searchQuery.trim().toLowerCase();

  // Compute categorized search hits across all dashboard domains
  const results: SearchDropdownResult[] = React.useMemo(() => {
    if (!query) return [];

    const matches: SearchDropdownResult[] = [];

    // 1. Core Modules
    MODULES_DATA.forEach((mod) => {
      if (
        mod.name.toLowerCase().includes(query) ||
        mod.purpose.toLowerCase().includes(query) ||
        mod.shortSummary.toLowerCase().includes(query) ||
        mod.tabs.some((tab) => `${tab.name} ${tab.description}`.toLowerCase().includes(query))
      ) {
        matches.push({
          id: `mod-${mod.id}`,
          title: mod.name,
          subtitle: mod.purpose,
          category: 'Module',
          anchorId: mod.id,
        });
      }
    });

    // 2. Guide Sections
    NAV_ITEMS.forEach((nav) => {
      if (nav.title.toLowerCase().includes(query) && !matches.some(m => m.anchorId === nav.id)) {
        matches.push({
          id: `nav-${nav.id}`,
          title: nav.title,
          subtitle: `${nav.category} `,
          category: 'Section',
          anchorId: nav.id,
        });
      }
    });

    // 3. Filters (22 Dimensions)
    FILTER_OPTIONS.forEach((f) => {
      if (
        f.name.toLowerCase().includes(query) ||
        f.description.toLowerCase().includes(query) ||
        f.category.toLowerCase().includes(query)
      ) {
        matches.push({
          id: `filter-${f.id}`,
          title: f.name,
          subtitle: `${f.category} Filter • ${f.isDependent ? `Depends on ${f.dependentOn}` : 'No other filter needed first'}`,
          category: 'Filter',
          anchorId: 'filters',
        });
      }
    });

    // 4. Data Sources
    DATA_SOURCES.forEach((ds) => {
      if (
        ds.code.toLowerCase().includes(query) ||
        ds.fullName.toLowerCase().includes(query) ||
        ds.description.toLowerCase().includes(query)
      ) {
        matches.push({
          id: `ds-${ds.code}`,
          title: `${ds.code} — ${ds.fullName}`,
          subtitle: ds.description,
          category: 'Data Source',
          anchorId: 'data-sources',
        });
      }
    });

    // 6. Troubleshooting
    TROUBLESHOOTING_ITEMS.forEach((t, idx) => {
      if (
        t.issue.toLowerCase().includes(query) ||
        t.actions.some((a) => a.toLowerCase().includes(query))
      ) {
        matches.push({
          id: `tb-${idx}`,
          title: t.issue,
          subtitle: t.actions[0],
          category: 'Troubleshooting',
          anchorId: 'troubleshooting',
        });
      }
    });

    // Deduplicate and cap to 9 high-relevance items
    const seen = new Set<string>();
    return matches.filter(m => {
      if (seen.has(m.id)) return false;
      seen.add(m.id);
      return true;
    }).slice(0, 9);
  }, [query]);

  // Reset selected item when query changes
  useEffect(() => {
    setSelectedIndex(-1);
    if (query.length > 0) {
      setIsDropdownOpen(true);
    }
  }, [query]);

  // Click outside listener to dismiss dropdown
  useEffect(() => {
    const handlePointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  // Handle selection of a dropdown result
  const handleSelectResult = (result: SearchDropdownResult) => {
    setIsDropdownOpen(false);
    {
      onSelectQuickLink(result.anchorId);
      // Trigger smooth flash highlight on target element
      const el = document.getElementById(result.anchorId);
      if (el) {
        el.classList.add('ring-2', 'ring-blue-600', 'bg-blue-50/50', 'transition-all');
        setTimeout(() => {
          el.classList.remove('ring-2', 'ring-blue-600', 'bg-blue-50/50');
        }, 2000);
      }
    }
  };

  // Keyboard navigation inside dropdown
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isDropdownOpen || results.length === 0) {
      if (e.key === 'ArrowDown' && query.length > 0) {
        setIsDropdownOpen(true);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + results.length) % results.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        handleSelectResult(results[selectedIndex]);
      } else if (results.length > 0) {
        handleSelectResult(results[0]);
      } else if (onFilterPageByQuery) {
        onFilterPageByQuery(query);
        setIsDropdownOpen(false);
      }
    } else if (e.key === 'Escape') {
      setIsDropdownOpen(false);
    }
  };

  const getCategoryBadge = (cat: SearchDropdownResult['category']) => {
    switch (cat) {
      case 'Module':
        return 'bg-blue-100 text-blue-900 border-blue-200';
      case 'Filter':
        return 'bg-purple-100 text-purple-900 border-purple-200';
      case 'Data Source':
        return 'bg-amber-100 text-amber-900 border-amber-200';
      case 'Troubleshooting':
        return 'bg-rose-100 text-rose-900 border-rose-200';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  return (
    <section
      aria-label="Search and Quick Start"
      className="my-6 p-5 sm:p-6 bg-gradient-to-br from-blue-900/5 via-slate-50 to-indigo-900/5 rounded-2xl border border-blue-900/10 shadow-xs relative"
    >
      <div className="max-w-3xl">
        <h2 className="text-sm font-bold uppercase tracking-wider text-blue-900 mb-1.5 flex items-center gap-2">
          <span>Search this guide</span>
        </h2>
        <p className="text-xs sm:text-sm text-slate-600 mb-4 leading-relaxed">
          Type a section, filter, data source, or problem.
        </p>

        {/* Search Container with Floating Dropdown */}
        <div ref={containerRef} className="relative">
          <div className="relative flex items-center">
            <div className="absolute left-3.5 pointer-events-none text-slate-400">
              <Search className="w-4 h-4 text-slate-500" aria-hidden="true" />
            </div>
            <input
              ref={searchInputRef}
              type="search"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              onFocus={() => {
                if (query.length > 0) setIsDropdownOpen(true);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search the guide… (e.g. DHIS2, Timeliness, AI Assistant, Filters, Internal Consistency)"
              className="w-full pl-10 pr-10 py-3 text-sm bg-white border border-slate-300 rounded-xl shadow-xs placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-800 focus:border-blue-800 transition-all text-slate-900"
              aria-label="Search the user guide"
              aria-expanded={isDropdownOpen}
              aria-controls="search-dropdown-menu"
              role="combobox"
              aria-autocomplete="list"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  onSearchChange('');
                  setIsDropdownOpen(false);
                }}
                className="absolute right-3 p-1 text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                aria-label="Clear search query"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* FLOATING DROPDOWN BOX */}
          {isDropdownOpen && query.length > 0 && (
            <div
              id="search-dropdown-menu"
              role="listbox"
              className="absolute left-0 right-0 top-full mt-2 z-50 bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden animate-in fade-in duration-150"
            >
              {/* Dropdown Header with Keyboard Hint */}
              <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                <span className="font-semibold text-slate-700">
                  {results.length > 0
                    ? `Top ${results.length} Search Result${results.length === 1 ? '' : 's'}`
                    : 'No Results'}
                </span>
                <span className="hidden sm:inline-flex items-center gap-1 font-mono text-[10px] text-slate-400">
                  <span>Use</span>
                  <kbd className="px-1 py-0.5 bg-white border border-slate-200 rounded text-slate-600">↑</kbd>
                  <kbd className="px-1 py-0.5 bg-white border border-slate-200 rounded text-slate-600">↓</kbd>
                  <span>to navigate</span>
                  <span className="mx-1">·</span>
                  <kbd className="px-1 py-0.5 bg-white border border-slate-200 rounded text-slate-600">Enter</kbd>
                  <span>to select</span>
                </span>
              </div>

              {/* Results List */}
              {results.length > 0 ? (
                <ul ref={dropdownListRef} className="max-h-[380px] overflow-y-auto divide-y divide-slate-100 p-1.5">
                  {results.map((res, index) => {
                    const isSelected = index === selectedIndex;
                    return (
                      <li
                        key={res.id}
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => handleSelectResult(res)}
                        onMouseEnter={() => setSelectedIndex(index)}
                        className={`p-3 rounded-xl cursor-pointer transition-all flex items-start justify-between gap-3 ${
                          isSelected
                            ? 'bg-blue-50/90 border border-blue-200 ring-1 ring-blue-300'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded border ${getCategoryBadge(res.category)}`}>
                              {res.category}
                            </span>
                            <span className="font-bold text-xs text-slate-900 truncate">
                              {res.title}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 line-clamp-1 leading-snug">
                            {res.subtitle}
                          </p>
                        </div>

                        <div className="shrink-0 flex items-center gap-1.5 pt-0.5 text-blue-900">
                          {isSelected && (
                            <CornerDownLeft className="w-4 h-4 text-blue-800" aria-hidden="true" />
                          )}
                          <ArrowRight className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="p-6 text-center text-xs text-slate-500">
                  <HelpCircle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="font-semibold text-slate-700">No topics found matching "{searchQuery}"</p>
                  <p className="text-slate-400 mt-1">
                    Try searching for <button type="button" onClick={() => onSearchChange('DHIS2')} className="text-blue-800 underline">DHIS2</button>, <button type="button" onClick={() => onSearchChange('Filters')} className="text-blue-800 underline">Filters</button>, <button type="button" onClick={() => onSearchChange('Timeliness')} className="text-blue-800 underline">Timeliness</button>, or <button type="button" onClick={() => onSearchChange('Amharic')} className="text-blue-800 underline">Amharic</button>.
                  </p>
                </div>
              )}

              {/* Optional Footer: Filter full document view */}
              {onFilterPageByQuery && results.length > 0 && (
                <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
                  <span>Looking for full in-page isolation?</span>
                  <button
                    type="button"
                    onClick={() => {
                      onFilterPageByQuery(query);
                      setIsDropdownOpen(false);
                    }}
                    className="font-semibold text-blue-900 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>Filter entire document for "{searchQuery}"</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* If page is currently in full-filter mode, show notice and reset button */}
        {isPageFiltered && (
          <div className="mt-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-xl text-xs flex items-center justify-between text-blue-950">
            <span>
              Document is filtered for: <strong className="font-semibold text-blue-900">"{searchQuery}"</strong>
            </span>
            {onClearPageFilter && (
              <button
                type="button"
                onClick={onClearPageFilter}
                className="font-semibold underline hover:text-blue-700 cursor-pointer"
              >
                Show all sections
              </button>
            )}
          </div>
        )}

        {/* Quick Links Row */}
        <div className="mt-4 pt-3.5 border-t border-slate-200/80">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-700 mr-1">
              Quick links:
            </span>

            {/* Quick link 1: Find an indicator */}
            <button
              type="button"
              onClick={() => onSelectQuickLink('module-routine-indicators')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-blue-50 border border-slate-300 hover:border-blue-300 text-blue-900 shadow-2xs transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              <Database className="w-3.5 h-3.5 text-blue-700" aria-hidden="true" />
              <span>Find an indicator</span>
            </button>

            {/* Quick link 2: Apply filters */}
            <button
              type="button"
              onClick={() => onSelectQuickLink('filters')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-blue-50 border border-slate-300 hover:border-blue-300 text-slate-800 shadow-2xs transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              <Filter className="w-3.5 h-3.5 text-slate-600" aria-hidden="true" />
              <span>Apply filters</span>
            </button>

            {/* Quick link 3: Check data quality */}
            <button
              type="button"
              onClick={() => onSelectQuickLink('module-data-quality')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-blue-50 border border-slate-300 hover:border-blue-300 text-slate-800 shadow-2xs transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" aria-hidden="true" />
              <span>Check data quality</span>
            </button>

            {/* Quick link 4: Use the AI Assistant */}
            <button
              type="button"
              onClick={() => onSelectQuickLink('module-ai-assistant')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-blue-50 border border-slate-300 hover:border-blue-300 text-indigo-900 shadow-2xs transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" aria-hidden="true" />
              <span>Use the AI Assistant</span>
            </button>
          </div>

          {/* First-time user link */}
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-600">
            <Compass className="w-3.5 h-3.5 text-blue-700 shrink-0" aria-hidden="true" />
            <span>
              First-time user?{' '}
              <button
                type="button"
                onClick={() => onSelectQuickLink('login-navigation')}
                className="text-blue-900 font-semibold underline underline-offset-2 hover:text-blue-700 inline-flex items-center gap-0.5 cursor-pointer"
              >
                <span>Read login and basic navigation instructions</span>
                <ArrowRight className="w-3 h-3" aria-hidden="true" />
              </button>
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
