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
import { flushSync } from 'react-dom';
import { Header } from './components/Header';
import { SidebarNav } from './components/SidebarNav';
import { SearchQuickStart } from './components/SearchQuickStart';
import { Callout } from './components/Callout';
import { ScreenshotPlaceholder } from './components/ScreenshotPlaceholder';
import { SupportModal } from './components/SupportModal';
import { AccessibilityMenu } from './components/AccessibilityMenu';
import { BackToTop } from './components/BackToTop';
import { ModuleGuideSection } from './components/ModuleGuideSection';
import { AccessibilitySettings, DEFAULT_ACCESSIBILITY_SETTINGS } from './types/accessibility';
import {
  DATA_SOURCES,
  FILTER_OPTIONS,
  MODULES_DATA,
  CHART_INTERPRETATION_RULES,
  TROUBLESHOOTING_ITEMS,
  NAV_ITEMS
} from './data/guideData';
import { AlertTriangle, Filter, HelpCircle, MessageSquare } from 'lucide-react';

const SectionHeading: React.FC<{ group: string; title: string; children: React.ReactNode }> = ({ group, title, children }) => (
  <div className="mb-4">
    <span className="text-xs font-bold uppercase tracking-wider text-blue-900 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
      {group}
    </span>
    <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mt-2">{title}</h2>
    <p className="text-base text-slate-600 mt-2 leading-relaxed">{children}</p>
  </div>
);

const Stat: React.FC<{ value: string; label: string }> = ({ value, label }) => (
  <div className="p-3.5 rounded-xl border border-slate-200 bg-white">
    <span className="block text-xl font-bold font-mono text-blue-900 tabular-nums">{value}</span>
    <span className="text-sm text-slate-600">{label}</span>
  </div>
);

export default function App() {
  const [activeNavId, setActiveNavId] = useState<string>('welcome');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [pageFilterQuery, setPageFilterQuery] = useState<string>('');
  const [isSupportModalOpen, setIsSupportModalOpen] = useState<boolean>(false);
  const [isAccessibilityModalOpen, setIsAccessibilityModalOpen] = useState<boolean>(false);
  const [readingProgress, setReadingProgress] = useState<number>(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const printRestoreRef = useRef<{ pageFilterQuery: string } | null>(null);
  const pageFilterQueryRef = useRef(pageFilterQuery);
  pageFilterQueryRef.current = pageFilterQuery;

  // Persistent sidebar collapsed rail state
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('moh_sidebar_collapsed');
      return saved === 'true';
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('moh_sidebar_collapsed', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Persistent accessibility configuration
  const [accessibilitySettings, setAccessibilitySettings] = useState<AccessibilitySettings>(() => {
    try {
      const saved = localStorage.getItem('moh_pmd_accessibility');
      return saved ? JSON.parse(saved) : DEFAULT_ACCESSIBILITY_SETTINGS;
    } catch {
      return DEFAULT_ACCESSIBILITY_SETTINGS;
    }
  });

  // Apply accessibility classes to documentElement
  useEffect(() => {
    const root = document.documentElement;

    root.classList.toggle('high-contrast', accessibilitySettings.highContrast);
    root.classList.toggle('text-spacing', accessibilitySettings.textSpacing);
    root.classList.toggle('underline-links', accessibilitySettings.underlineLinks);
    root.classList.toggle('enhanced-focus', accessibilitySettings.enhancedFocus);
    root.classList.toggle('reduced-motion', accessibilitySettings.reducedMotion);

    try {
      localStorage.setItem('moh_pmd_accessibility', JSON.stringify(accessibilitySettings));
    } catch {
      // storage unavailable
    }
  }, [accessibilitySettings]);

  // Scrollspy & Reading Progress Tracker
  useEffect(() => {
    const handleScroll = () => {
      // Calculate reading progress percentage
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight > 0) {
        const currentProgress = Math.min(100, Math.max(0, (window.scrollY / totalHeight) * 100));
        setReadingProgress(currentProgress);
      }

      // Track active section using element offsets
      const sectionElements = NAV_ITEMS.map(item => document.getElementById(item.id)).filter(Boolean) as HTMLElement[];
      const scrollPosition = window.scrollY + 160;

      for (let i = sectionElements.length - 1; i >= 0; i--) {
        const el = sectionElements[i];
        if (el.offsetTop <= scrollPosition) {
          setActiveNavId(el.id);
          break;
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Keyboard shortcuts: '/' for search, '[' to toggle sidebar rail
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
        return;
      }
      if (e.key === '/') {
        e.preventDefault();
        searchInputRef.current?.focus();
      } else if (e.key === '[') {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const handleBeforePrint = () => {
      if (printRestoreRef.current) return;

      const previousPageFilter = pageFilterQueryRef.current;
      printRestoreRef.current = { pageFilterQuery: previousPageFilter };
      if (previousPageFilter) {
        flushSync(() => setPageFilterQuery(''));
      }
    };

    const handleAfterPrint = () => {
      const previousState = printRestoreRef.current;
      if (!previousState) return;

      setPageFilterQuery(previousState.pageFilterQuery);
      printRestoreRef.current = null;
    };

    window.addEventListener('beforeprint', handleBeforePrint);
    window.addEventListener('afterprint', handleAfterPrint);
    return () => {
      window.removeEventListener('beforeprint', handleBeforePrint);
      window.removeEventListener('afterprint', handleAfterPrint);
    };
  }, []);

  const handlePrint = () => window.print();

  const handleNavigate = (id: string) => {
    setActiveNavId(id);
    const element = document.getElementById(id);
    if (element) {
      const topOffset = 80;
      const elementPosition = element.getBoundingClientRect().top + window.pageYOffset;
      window.scrollTo({
        top: elementPosition - topOffset,
        behavior: 'smooth'
      });

      // Temporary focus highlight pulse on arrived element
      element.classList.add('ring-2', 'ring-blue-600', 'bg-blue-50/40', 'transition-all');
      setTimeout(() => {
        element.classList.remove('ring-2', 'ring-blue-600', 'bg-blue-50/40');
      }, 2000);
    }
  };

  const handleOpenSearch = () => {
    searchInputRef.current?.focus();
    searchInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  // Section visibility filtering based on pageFilterQuery (keeps full page intact during live search dropdown)
  const filterQuery = pageFilterQuery.trim().toLowerCase();
  const isMatch = (text: string) => filterQuery === '' || text.toLowerCase().includes(filterQuery);

  const welcomeMatches = isMatch('welcome') || isMatch('overview') || isMatch('home page') || isMatch('dhis2');
  const loginMatches = isMatch('login') || isMatch('log in') || isMatch('sign in') || isMatch('password') || isMatch('username') || isMatch('dark mode');
  const filtersMatches = FILTER_OPTIONS.some((f) => isMatch(f.name) || isMatch(f.description)) || isMatch('filter') || isMatch('apply');
  const readingChartsMatches = isMatch('chart') || isMatch('baseline') || isMatch('target') || isMatch('performance') || isMatch('color') || isMatch('legend') || isMatch('map') || isMatch('download');
  const dataSourcesMatches = isMatch('data source') || DATA_SOURCES.some((d) => isMatch(d.code) || isMatch(d.fullName));
  const troubleshootingMatches = isMatch('troubleshoot') || isMatch('error') || isMatch('problem') || isMatch('no data') || isMatch('empty') || TROUBLESHOOTING_ITEMS.some((t) => isMatch(t.issue));
  const supportMatches = isMatch('support') || isMatch('help') || isMatch('contact') || isMatch('feedback') || isMatch('administrator');

  // Count matching modules
  const matchingModules = MODULES_DATA.filter((m) =>
    isMatch(m.name) ||
    isMatch(m.purpose) ||
    isMatch(m.shortSummary) ||
    m.tabs.some((tab) => isMatch(tab.name) || isMatch(tab.description)) ||
    m.filters.some(isMatch)
  );

  const totalVisibleSections =
    (welcomeMatches ? 1 : 0) +
    (loginMatches ? 1 : 0) +
    (filtersMatches ? 1 : 0) +
    (readingChartsMatches ? 1 : 0) +
    matchingModules.length +
    (dataSourcesMatches ? 1 : 0) +
    (troubleshootingMatches ? 1 : 0) +
    (supportMatches ? 1 : 0);

  const fontSizeClass =
    accessibilitySettings.fontSize === 'xlarge'
      ? 'text-[19px]'
      : accessibilitySettings.fontSize === 'large'
      ? 'text-[17px]'
      : 'text-[15px]';

  return (
    <div className={`min-h-screen bg-slate-50 text-slate-900 antialiased ${fontSizeClass}`}>
      {/* Institutional Top Bar & Header */}
      <Header
        onPrint={handlePrint}
        onOpenSearch={handleOpenSearch}
        onOpenSupport={() => setIsSupportModalOpen(true)}
        onOpenAccessibility={() => setIsAccessibilityModalOpen(true)}
        isHighContrast={accessibilitySettings.highContrast}
        onToggleHighContrast={() =>
          setAccessibilitySettings((prev) => ({
            ...prev,
            highContrast: !prev.highContrast
          }))
        }
      />

      {/* Main Page Layout Wrapper */}
      <div className={`print-layout mx-auto px-4 sm:px-6 lg:px-8 py-6 transition-all duration-300 ${isSidebarCollapsed ? 'max-w-[1440px]' : 'max-w-7xl'}`}>
        <div className="flex flex-col lg:flex-row gap-6 lg:gap-8">
          {/* Persistent Left Sidebar Navigation (Desktop) + Mobile Banner */}
          <SidebarNav
            activeId={activeNavId}
            onNavigate={handleNavigate}
            onOpenAccessibility={() => setIsAccessibilityModalOpen(true)}
            isHighContrast={accessibilitySettings.highContrast}
            readingProgress={readingProgress}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={toggleSidebar}
          />

          {/* Main Reading Canvas (dynamically expands when sidebar is collapsed) */}
          <main className={`print-content flex-1 min-w-0 transition-all duration-300 ${isSidebarCollapsed ? 'max-w-5xl xl:max-w-6xl' : 'max-w-4xl'} pb-24`}>
            {/* Search and Quick Start Area with Floating Dropdown */}
            <div className="no-print">
              <SearchQuickStart
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                onSelectQuickLink={handleNavigate}
                onFilterPageByQuery={(q) => setPageFilterQuery(q)}
                isPageFiltered={filterQuery.length > 0}
                onClearPageFilter={() => {
                  setPageFilterQuery('');
                  setSearchQuery('');
                }}
                searchInputRef={searchInputRef}
              />
            </div>

            {/* Empty Search Filter State (When explicit document filter yields no sections) */}
            {filterQuery.length > 0 && totalVisibleSections === 0 && (
              <div className="no-print">
              <div className="my-12 p-8 text-center bg-white rounded-2xl border border-slate-200">
                <HelpCircle className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <h3 className="text-base font-bold text-slate-900">No matching sections for "{pageFilterQuery}"</h3>
                <p className="text-sm text-slate-600 max-w-md mx-auto mt-1 mb-4">
                  Try another word, or clear the search to read all sections.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setPageFilterQuery('');
                    setSearchQuery('');
                  }}
                  className="px-4 py-2 bg-blue-900 text-white rounded-lg text-xs font-semibold hover:bg-blue-800 transition-colors cursor-pointer"
                >
                  Reset filter and show all sections
                </button>
              </div>
              </div>
            )}

            {/* SECTION 1: WELCOME */}
            {welcomeMatches && (
              <section id="welcome" className="pt-4 pb-12 border-b border-slate-200 scroll-mt-24">
                <SectionHeading group="Getting Started" title="Welcome">
                  The MOH Performance Monitoring Dashboard brings health data from across the country into one place, so you can track performance from the national level down through the health system. You do not need any technical knowledge to use it.
                </SectionHeading>

                <div className="my-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <Stat value="7" label="Sections on the home page" />
                  <Stat value="94 + 19" label="Monthly and quarterly indicators" />
                  <Stat value="6" label="Main data sources" />
                </div>

                <p className="text-sm text-slate-700 leading-relaxed">The seven sections are:</p>
                <ul className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-sm list-none pl-0">
                  {MODULES_DATA.map((m) => (
                    <li key={m.id} className="p-3 rounded-lg border border-slate-200 bg-white">
                      <button type="button" onClick={() => handleNavigate(m.id)} className="font-semibold text-blue-900 hover:underline cursor-pointer text-left">
                        {m.name}
                      </button>
                      <span className="block text-slate-600 mt-0.5">{m.shortSummary}</span>
                    </li>
                  ))}
                </ul>

                <Callout type="tip" title="Where to start">
                  Check Data Quality first. It tells you how far you can trust the numbers in the other sections.
                </Callout>

                <Callout type="note" title="About the pictures in this guide">
                  The pictures were taken from the dashboard on 3 November 2026. The numbers in them are examples only, so always use the live dashboard. What you see may differ depending on your account.
                </Callout>
              </section>
            )}

            {/* SECTION 2: LOGIN AND NAVIGATION */}
            {loginMatches && (
              <section id="login-navigation" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
                <SectionHeading group="Getting Started" title="Logging in and finding your way">
                  You need a username and password from your organisation.
                </SectionHeading>

                <ol className="my-4 space-y-2 text-sm text-slate-700 list-decimal pl-5">
                  <li>Open <strong>pmd.mohdigitalhealth.gov.et</strong> in Chrome, Firefox, or Edge.</li>
                  <li>Enter your username and password.</li>
                  <li>Click <strong>Sign in</strong>.</li>
                </ol>

                <ScreenshotPlaceholder
                  data={{
                    id: 'sc-login',
                    imagePath: 'images/guide/login.png',
                    displaySize: 'medium',
                    title: 'The sign-in page',
                    altText: 'The sign-in page with username and password boxes and a Sign in button.',
                    annotations: [
                      { number: 1, title: 'Username', description: 'Enter your username.', position: { top: '46.4%', left: '36.5%' } },
                      { number: 2, title: 'Password', description: 'Enter your password. The eye icon shows or hides it.', position: { top: '55.1%', left: '36.5%' } },
                      { number: 3, title: 'Sign in', description: 'Click to open the dashboard.', position: { top: '60.7%', left: '36.5%' } },
                    ],
                  }}
                />

                <h4 className="text-base font-bold text-slate-900 mt-8 mb-2">The home page</h4>
                <p className="text-sm text-slate-700 leading-relaxed">
                  After you sign in, you see a card for each section you can access. Click a card to open it.
                </p>
                <ScreenshotPlaceholder
                  data={{
                    id: 'sc-landing',
                    imagePath: 'images/guide/landing.png',
                    title: 'The home page',
                    altText: 'The home page with cards for Summary, Data Quality, Routine Health Indicators, Multi Source, Triangulation, Health Intelligence, and AI Assistant.',
                    annotations: [
                      { number: 1, title: 'Section cards', description: 'Click a card to open that section.', position: { top: '36%', left: '11.5%' } },
                      { number: 2, title: 'User Guide and Feedback', description: 'Open this guide, or send your comments.', position: { top: '8.2%', left: '76%' } },
                      { number: 3, title: 'Dark mode', description: 'Switch between light and dark colors.', position: { top: '8.2%', left: '85.8%' } },
                      { number: 4, title: 'Sign out', description: 'Sign out when you finish, especially on a shared computer.', position: { top: '8.2%', left: '96.7%' } },
                    ],
                  }}
                />

                <h4 className="text-base font-bold text-slate-900 mt-8 mb-2">Inside a section</h4>
                <ul className="space-y-2 text-sm text-slate-700 list-disc pl-5">
                  <li><strong>Top menu:</strong> click Home to return to the home page.</li>
                  <li><strong>Tabs:</strong> the first row moves between sections. The second row moves within a section.</li>
                  <li><strong>Information bar:</strong> shows the page name, source, data date, and reporting completeness.</li>
                  <li><strong>ASK AI button:</strong> at the bottom right of the page, for quick access to the AI assistant.</li>
                </ul>
              </section>
            )}

            {/* SECTION 3: FILTERS */}
            {filtersMatches && (
              <section id="filters" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
                <SectionHeading group="Using the Dashboard" title="Filters">
                  Filters choose the period, place, and indicator that the charts show.
                </SectionHeading>

                <h4 className="text-base font-bold text-slate-900 mt-6 mb-2 flex items-center gap-2">
                  <Filter className="w-4 h-4 text-blue-800" aria-hidden="true" />
                  <span>How to use filters</span>
                </h4>
                <ol className="space-y-2 text-sm text-slate-700 list-decimal pl-5">
                  <li>Click the funnel icon on the left side of the page to open <strong>Filters and controls</strong>.</li>
                  <li>Change the filters you need.</li>
                  <li>Click <strong>Apply filters</strong>. The charts do not change until you do.</li>
                </ol>

                <ScreenshotPlaceholder
                  data={{
                    id: 'sc-filter-panel',
                    imagePath: 'images/guide/filter-panel.png',
                    title: 'The filter panel on the Routine Health Indicators, Monthly tab',
                    altText: 'The filter panel with global filters for period and organisation unit, dashboard-specific filters, and Apply filters and Clear all filters buttons.',
                    annotations: [
                      { number: 1, title: 'Global filters', description: 'The period and the organisation unit.', position: { top: '7.5%', left: '12.5%' } },
                      { number: 2, title: 'Dashboard-specific filters', description: 'These change with the tab you are on.', position: { top: '47.3%', left: '13.5%' } },
                      { number: 3, title: 'Apply filters', description: 'Updates the charts with your choices.', position: { top: '88.9%', left: '4%' } },
                      { number: 4, title: 'Clear all filters', description: 'Removes your choices.', position: { top: '93.3%', left: '3.5%' } },
                    ],
                  }}
                />

                <Callout type="important" title="Some filters depend on others">
                  Choose filters from the top down. For example, choose the Program before the Sub Program and the Indicator. If you change a filter, the ones that depend on it may reset.
                </Callout>

                <Callout type="tip" title="Check what a chart is showing">
                  The grey line under a chart title shows the year, place, source, and data date for that chart. The small funnel with a number shows how many filters apply to it.
                </Callout>

                <h4 className="text-base font-bold text-slate-900 mt-8 mb-2">The filters in this dashboard</h4>
                <div className="print-table-wrap overflow-x-auto rounded-xl border border-slate-200 bg-white">
                  <table className="print-table w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                    <thead className="bg-slate-100 font-semibold text-slate-900 text-xs">
                      <tr>
                        <th scope="col" className="px-3 py-2.5">Filter</th>
                        <th scope="col" className="px-3 py-2.5">What it does</th>
                        <th scope="col" className="px-3 py-2.5">Where you see it</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {FILTER_OPTIONS.map((f) => (
                        <tr key={f.id}>
                          <td className="px-3 py-2 font-semibold text-slate-900 align-top">{f.name}</td>
                          <td className="px-3 py-2 align-top">
                            {f.description}
                            {f.isDependent && <span className="block text-xs text-amber-800 mt-0.5">Choose {f.dependentOn} first.</span>}
                          </td>
                          <td className="px-3 py-2 text-slate-600 align-top">{f.whereUsed}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* SECTION 4: READING CHARTS */}
            {readingChartsMatches && (
              <section id="reading-charts" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
                <SectionHeading group="Using the Dashboard" title="Reading cards, charts, and colors">
                  Most indicators are shown as a performance compared with a baseline and a target.
                </SectionHeading>

                <div className="my-6 print-table-wrap overflow-x-auto rounded-xl border border-slate-200 bg-white">
                  <table className="print-table w-full text-left text-sm text-slate-700 divide-y divide-slate-200">
                    <thead className="bg-slate-100 font-semibold text-slate-900 text-xs">
                      <tr>
                        <th scope="col" className="px-3 py-2.5">Term</th>
                        <th scope="col" className="px-3 py-2.5">On most charts</th>
                        <th scope="col" className="px-3 py-2.5">What it means</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {CHART_INTERPRETATION_RULES.map((rule) => (
                        <tr key={rule.concept}>
                          <td className="px-3 py-2 font-semibold text-slate-900">{rule.concept}</td>
                          <td className="px-3 py-2">{rule.color}</td>
                          <td className="px-3 py-2">{rule.meaning}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <Callout type="important" title="Always read the color key">
                  Colors can change from chart to chart, and higher is not always better. On a coverage map, for example, red is low. On a map of deaths, darker colors mean higher values.
                </Callout>

                <h4 className="text-base font-bold text-slate-900 mt-6 mb-2">The information bar</h4>
                <p className="text-sm text-slate-700 leading-relaxed">
                  The bar at the top of a page shows the data source and how recent the data is. A colored message shows reporting completeness and on-time reporting against the 80% target. It is green when on target and brown when below it. Low completeness means the numbers on that page may change as more reports arrive.
                </p>

                <h4 className="text-base font-bold text-slate-900 mt-6 mb-2">Working with a chart</h4>
                <ul className="space-y-2 text-sm text-slate-700 list-disc pl-5">
                  <li><strong>See an exact value:</strong> move your mouse over a bar, line, or map area.</li>
                  <li><strong>Hide or show a series:</strong> click its name in the chart key, or use Select all and Invert selection.</li>
                  <li><strong>Zoom a map:</strong> use the + and − buttons, or hold Ctrl and scroll.</li>
                  <li><strong>Read an AI note:</strong> many charts have an AI Insight panel. Check its statements against the chart.</li>
                </ul>

                <ScreenshotPlaceholder
                  data={{
                    id: 'sc-chart-menu',
                    imagePath: 'images/guide/chart-menu.png',
                    title: 'The chart menu',
                    altText: 'A chart menu listing View fullscreen, View as table, Explore visual, Download, Force refresh, View query, and Share.',
                    annotations: [
                      { number: 1, title: 'Three dots', description: 'Click to open the menu for that chart.', position: { top: '24.3%', left: '79.5%' } },
                      { number: 2, title: 'View fullscreen and View as table', description: 'Make the chart larger, or see its numbers.', position: { top: '34%', left: '65.5%' } },
                      { number: 3, title: 'Download', description: 'Save the chart or its data.', position: { top: '42.1%', left: '65.5%' } },
                      { number: 4, title: 'Share', description: 'Get a link to the chart.', position: { top: '58.2%', left: '65.5%' } },
                    ],
                  }}
                />
              </section>
            )}

            {/* SECTIONS 5 TO 11: SECTION GUIDES */}
            <div className="space-y-4">
              {matchingModules.map((module) => (
                <ModuleGuideSection key={module.id} module={module} />
              ))}
            </div>

            {/* SECTION 12: DATA SOURCES */}
            {dataSourcesMatches && (
              <section id="data-sources" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
                <SectionHeading group="Reference" title="Data sources">
                  To see the source and date of what you are looking at, check the information bar at the top of the page. Health Intelligence also uses program data, such as HR records, health financing, pharmaceutical supply, blood bank, and PHEM surveillance data.
                </SectionHeading>

                <div className="my-6 space-y-3">
                  {DATA_SOURCES.map((source) => (
                    <div key={source.code} className="p-4 rounded-xl border border-slate-200 bg-white text-sm">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="font-mono font-bold text-white bg-blue-900 px-2 py-0.5 rounded-md">{source.code}</span>
                        <h4 className="font-bold text-slate-900">{source.fullName}</h4>
                      </div>
                      <p className="mt-2 text-slate-700">{source.description}</p>
                      <p className="mt-1 text-slate-600"><strong className="text-slate-800">Where you see it:</strong> {source.whereUsed}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* SECTION 13: TROUBLESHOOTING */}
            {troubleshootingMatches && (
              <section id="troubleshooting" className="pt-8 pb-12 border-b border-slate-200 scroll-mt-24">
                <SectionHeading group="Reference" title="Troubleshooting">
                  Solutions to common problems.
                </SectionHeading>

                <div className="my-6 space-y-3">
                  {TROUBLESHOOTING_ITEMS.map((item) => (
                    <div key={item.issue} className="p-4 rounded-xl border border-slate-200 bg-white text-sm">
                      <h4 className="font-bold text-slate-900 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" aria-hidden="true" />
                        <span>{item.issue}</span>
                      </h4>
                      <ul className="mt-2 space-y-1 list-disc pl-5 text-slate-700">
                        {item.actions.map((action) => <li key={action}>{action}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* SECTION 14: GETTING HELP */}
            {supportMatches && (
              <section id="support" className="pt-8 pb-12 scroll-mt-24">
                <SectionHeading group="Reference" title="Getting help">
                  For a login or access problem, contact the person in your organisation who gave you your account, or your dashboard administrator. To report a problem or suggest an improvement, use the Feedback form.
                </SectionHeading>
                <a
                  href="/feedback/"
                  className="no-print mt-2 inline-flex items-center gap-2 px-4 py-2 bg-blue-900 text-white rounded-lg text-sm font-semibold hover:bg-blue-800 transition-colors"
                >
                  <MessageSquare className="w-4 h-4" aria-hidden="true" />
                  <span>Open the Feedback form</span>
                </a>
                <Callout type="note" title="Include these details">
                  Your username and organisation unit, the section and tab, the chart name and filters, and a screenshot of the problem. Do not include personal information about patients.
                </Callout>
              </section>
            )}
          </main>
        </div>
      </div>

      {/* Footer */}
      <footer className="print-footer mt-16 bg-slate-900 text-slate-300 text-xs py-8 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="font-bold text-white block text-sm">MOH Performance Monitoring Dashboard — User Guide</span>
            <span className="text-slate-400">Ministry of Health, Ethiopia · Last updated 3 November 2026</span>
          </div>
          <div className="no-print flex items-center gap-4">
            <button type="button" onClick={() => handleNavigate('welcome')} className="text-slate-400 hover:text-white transition-colors cursor-pointer">Top of guide</button>
            <button type="button" onClick={() => setIsSupportModalOpen(true)} className="text-slate-400 hover:text-white transition-colors cursor-pointer">Getting help</button>
            <button type="button" onClick={() => setIsAccessibilityModalOpen(true)} className="text-slate-400 hover:text-white transition-colors cursor-pointer">Accessibility</button>
          </div>
        </div>
      </footer>

      <BackToTop />

      <SupportModal isOpen={isSupportModalOpen} onClose={() => setIsSupportModalOpen(false)} />

      <AccessibilityMenu
        isOpen={isAccessibilityModalOpen}
        onClose={() => setIsAccessibilityModalOpen(false)}
        settings={accessibilitySettings}
        onUpdateSettings={setAccessibilitySettings}
        onResetSettings={() => setAccessibilitySettings(DEFAULT_ACCESSIBILITY_SETTINGS)}
      />
    </div>
  );
}
