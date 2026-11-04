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
import { DataSourceItem, FilterOption, ModuleSection, NavItem } from '../types/guide';

export const NAV_ITEMS: NavItem[] = [
  { id: 'welcome', title: 'Welcome', category: 'GETTING STARTED' },
  { id: 'login-navigation', title: 'Logging in and finding your way', category: 'GETTING STARTED' },

  { id: 'filters', title: 'Filters', category: 'USING THE DASHBOARD' },
  { id: 'reading-charts', title: 'Reading cards, charts, and colors', category: 'USING THE DASHBOARD' },
  { id: 'module-summary', title: 'Summary', category: 'USING THE DASHBOARD' },
  { id: 'module-data-quality', title: 'Data Quality', category: 'USING THE DASHBOARD' },
  { id: 'module-routine-indicators', title: 'Routine Health Indicators', category: 'USING THE DASHBOARD' },

  { id: 'module-multi-source', title: 'Multi Source', category: 'COMPARING AND EXPLORING DATA' },
  { id: 'module-triangulation', title: 'Triangulation', category: 'COMPARING AND EXPLORING DATA' },
  { id: 'module-health-intelligence', title: 'Health Intelligence', category: 'COMPARING AND EXPLORING DATA' },
  { id: 'module-ai-assistant', title: 'AI Assistant', category: 'COMPARING AND EXPLORING DATA' },

  { id: 'data-sources', title: 'Data sources', category: 'REFERENCE' },
  { id: 'troubleshooting', title: 'Troubleshooting', category: 'REFERENCE' },
  { id: 'support', title: 'Getting help', category: 'REFERENCE' },
];

export const DATA_SOURCES: DataSourceItem[] = [
  {
    code: 'DHIS2',
    fullName: 'District Health Information Software 2',
    description: 'The national system for routine health data reported by health facilities.',
    whereUsed: 'Summary, Data Quality, Routine Health Indicators, Triangulation, and Services Delivery in Health Intelligence.',
  },
  {
    code: 'eCHIS',
    fullName: 'Electronic Community Health Information System',
    description: 'Community-level data recorded by health extension workers.',
    whereUsed: 'Triangulation, eCHIS vs DHIS2 tab.',
  },
  {
    code: 'EDHS',
    fullName: 'Ethiopia Demographic and Health Survey',
    description: 'A nationally representative household survey. The dashboard shows the 2000, 2005, 2011, 2016, 2019, and 2024 rounds.',
    whereUsed: 'Multi Source, Triangulation, and some Services Delivery charts in Health Intelligence.',
  },
  {
    code: 'WUENIC',
    fullName: 'WHO/UNICEF Estimates of National Immunization Coverage',
    description: 'Annual international estimates of immunization coverage.',
    whereUsed: 'Multi Source, WUENIC tab, shown next to HMIS figures.',
  },
  {
    code: 'IGME',
    fullName: 'UN Inter-agency Group for Child Mortality Estimation',
    description: 'International estimates of under-five, infant, and child mortality.',
    whereUsed: 'Multi Source, IGME tab.',
  },
  {
    code: 'MFR',
    fullName: 'Master Facility Registry',
    description: 'The list of health facilities, including their type, location, and services.',
    whereUsed: 'Multi Source, MFR tab, and Infrastructure in Health Intelligence.',
  },
];

export const FILTER_OPTIONS: FilterOption[] = [
  { id: 'f1', name: 'Period type', category: 'Time', description: 'Choose Monthly or Quarterly periods.', isDependent: false, whereUsed: 'Global filters' },
  { id: 'f2', name: 'Year', category: 'Time', description: 'The Ethiopian fiscal year, for example 2019 EFY.', isDependent: false, whereUsed: 'Global filters, and some Multi Source tabs' },
  { id: 'f3', name: 'Month', category: 'Time', description: 'One or more months. Leave it on All to see the whole year.', isDependent: false, whereUsed: 'Data Quality, Routine Monthly, Health Intelligence' },
  { id: 'f4', name: 'Quarter', category: 'Time', description: 'One or more quarters of the year.', isDependent: false, whereUsed: 'Routine Quarterly, Health Intelligence' },
  { id: 'f5', name: 'Organisation unit', category: 'Geography', description: 'The place you want to see, from national level down through the health system. You see only the units your account allows.', isDependent: false, whereUsed: 'Most tabs' },
  { id: 'f6', name: 'Program', category: 'Program Area', description: 'The program area, for example MCAH.', isDependent: false, whereUsed: 'Routine Health Indicators' },
  { id: 'f7', name: 'Sub Program', category: 'Program Area', description: 'A part of the chosen program, for example Maternal Health (MH).', isDependent: true, dependentOn: 'Program', whereUsed: 'Routine Health Indicators' },
  { id: 'f8', name: 'Indicator / Indicators', category: 'Program Area', description: 'The indicator shown in the charts.', isDependent: true, dependentOn: 'Sub Program', whereUsed: 'Routine Health Indicators, Multi Source, eCHIS vs DHIS2' },
  { id: 'f9', name: 'Data Element', category: 'Program Area', description: 'The raw value reported by facilities, for example ANC 1st visits by maternal age.', isDependent: false, whereUsed: 'Routine Data Elements' },
  { id: 'f10', name: 'Dataset', category: 'Facility & Dataset', description: 'The monthly reporting form to check.', isDependent: false, whereUsed: 'Data Quality, Monthly' },
  { id: 'f11', name: 'Quarter Dataset', category: 'Facility & Dataset', description: 'The quarterly reporting form to check.', isDependent: false, whereUsed: 'Data Quality, Quarterly' },
  { id: 'f12', name: 'Indicators for Consistency Check', category: 'Facility & Dataset', description: 'The pair of indicators to compare, for example Penta 1 and Penta 3.', isDependent: false, whereUsed: 'Data Quality, Internal Consistency' },
  { id: 'f13', name: 'Facility Type', category: 'Facility & Dataset', description: 'Limit results to one type of facility.', isDependent: false, whereUsed: 'Data Quality, Routine Data Elements' },
  { id: 'f14', name: 'Ownership', category: 'Facility & Dataset', description: 'Limit results by who owns the facility.', isDependent: false, whereUsed: 'Data Quality, Routine Data Elements' },
  { id: 'f15', name: 'CBMP', category: 'Facility & Dataset', description: 'An additional filter on Data Quality and Routine tabs. Leave it on All unless you need it.', isDependent: false, whereUsed: 'Data Quality, Routine Health Indicators' },
  { id: 'f16', name: 'External Population Indicators', category: 'Program Area', description: 'The indicator to compare using a different population figure.', isDependent: false, whereUsed: 'Routine Adjusted Denominator' },
  { id: 'f17', name: 'Category / Sub Category', category: 'Program Area', description: 'How to split survey results, for example by residence.', isDependent: false, whereUsed: 'Multi Source, EDHS' },
  { id: 'f18', name: 'Equity Year, Dimension, Subgroup, and Indicator', category: 'Program Area', description: 'Choose what to measure on the Health Equity tab.', isDependent: false, whereUsed: 'Health Intelligence, Health Equity' },
  { id: 'f19', name: 'Blood Region and Center', category: 'Geography', description: 'Limit blood donation results to a region or center.', isDependent: false, whereUsed: 'Health Intelligence, Blood Donation' },
  { id: 'f20', name: 'PHEM Diseases', category: 'Program Area', description: 'Choose the diseases shown.', isDependent: false, whereUsed: 'Health Intelligence, PHEM' },
];

export const MODULES_DATA: ModuleSection[] = [
  {
    id: 'module-summary',
    name: 'Summary',
    badgeNumber: '1',
    shortSummary: 'A quick look at key indicators compared with their targets.',
    purpose: 'How are the key indicators doing against their targets?',
    whenToUse: 'Start here for a quick overview, for a review meeting, or before looking at one program in detail.',
    howToOpen: [
      'On the home page, click View Summary.',
      'Read the Indicators Summary table, or click a theme such as Child Health or EPI.',
      'Open the filter panel to change the year or the organisation unit.',
    ],
    screenshot: {
      id: 'sc-summary',
      imagePath: 'images/guide/summary-indicators.png',
      title: 'Summary, Indicators Summary tab',
      altText: 'A table of indicators with columns for target, performance, variance, and status.',
      annotations: [
        { number: 1, title: 'Performance', description: 'The result for the selected year and place. Green is at or above target, red is below it.', position: { top: '42%', left: '69%' } },
        { number: 2, title: 'Variance', description: 'Performance minus target.', position: { top: '42%', left: '81%' } },
        { number: 3, title: 'Status', description: 'Shows Met Target, Below Target, or N/A when there is no target.', position: { top: '42%', left: '92%' } },
      ],
    },
    extraScreenshots: [
      {
        id: 'sc-summary-theme',
        imagePath: 'images/guide/summary-theme.png',
        title: 'Summary, a theme tab (Child Health)',
        altText: 'A performance card beside a monthly bar chart of baseline and performance against a target line.',
        annotations: [
          { number: 1, title: 'Performance card', description: 'The result so far, with the target and baseline.', position: { top: '42%', left: '11%' } },
          { number: 2, title: 'Monthly chart', description: 'Baseline and performance bars for each month, with a green target line.', position: { top: '35%', left: '32%' } },
          { number: 3, title: 'AI Insight', description: 'A panel for an AI-written note about the chart.', position: { top: '29%', left: '80%' } },
        ],
      },
    ],
    tabs: [
      { name: 'Indicators Summary', description: 'One table of the key indicators with target, performance, variance, and status.' },
      { name: 'Child Health, Maternal Health, Family Planning, EPI, DPC, HIV, Nutrition, Medical Service', description: 'One tab for each theme. Each has performance cards and a chart for each indicator.' },
    ],
    filters: ['Year', 'Organisation unit'],
    howToRead: [
      'Sort the Indicators Summary table to find the indicators furthest from target.',
      'The table and cards show the year so far. The bar chart shows each month.',
    ],
    ifSomethingLooksWrong: [
      'If the latest month is much lower than the others, its reports may not all be in yet. Check the reporting completeness message at the top of the page.',
      'If a status shows N/A, that indicator has no target to compare with.',
    ],
  },
  {
    id: 'module-data-quality',
    name: 'Data Quality',
    badgeNumber: '2',
    shortSummary: 'Shows whether reports are complete and on time, and whether related indicators agree.',
    purpose: 'Can I trust the numbers for this place and period?',
    whenToUse: 'Check this section first, before you use a number from any other section.',
    howToOpen: [
      'On the home page, click View Data Quality.',
      'Choose the Monthly, Quarterly, or Internal Consistency tab.',
      'Open the filter panel and choose the dataset, period, and organisation unit.',
    ],
    screenshot: {
      id: 'sc-data-quality',
      imagePath: 'images/guide/dq-monthly.png',
      title: 'Data Quality, Monthly tab',
      altText: 'Cards for report completeness and timeliness beside a table and a trend chart.',
      annotations: [
        { number: 1, title: 'Report Completeness', description: 'The share of expected reports received. Actual / Expected shows the counts.', position: { top: '47.5%', left: '12%' } },
        { number: 2, title: 'Report Timeliness', description: 'The share of expected reports received on time.', position: { top: '85%', left: '12%' } },
        { number: 3, title: 'Table by organisation unit', description: 'Completeness and timeliness for each place.', position: { top: '40%', left: '38%' } },
        { number: 4, title: 'Trend', description: 'How both measures change from month to month.', position: { top: '77.5%', left: '38%' } },
      ],
    },
    tabs: [
      { name: 'Monthly', description: 'Completeness and timeliness for the monthly reporting form you choose.' },
      { name: 'Quarterly', description: 'The same measures for quarterly reporting forms, with a 100% target on the cards.' },
      { name: 'Internal Consistency', description: 'Compares pairs of related indicators, for example Penta 1 and Penta 3, as a check and as a trend.' },
    ],
    filters: [
      'Monthly: Year, Month, Organisation unit, Dataset, Facility Type, Ownership, CBMP',
      'Quarterly: Year, Month, Organisation unit, Quarter Dataset, Facility Type, Ownership, CBMP',
      'Internal Consistency: Year, Month, Organisation unit, Indicators for Consistency Check, Facility Type, Ownership',
    ],
    howToRead: [
      'Completeness tells you how many reports arrived, not whether the numbers in them are correct.',
      'The top of the page shows the completeness message against the 80% target.',
      'A very low value for the latest month usually means reporting is still in progress.',
    ],
    ifSomethingLooksWrong: [
      'If a chart says "Couldn\'t load this visual", your account may not have access to that data. Contact your dashboard administrator.',
      'If completeness is low, treat the indicator results for that place and period with caution.',
    ],
  },
  {
    id: 'module-routine-indicators',
    name: 'Routine Health Indicators',
    badgeNumber: '3',
    shortSummary: 'Monthly and quarterly indicators from DHIS2, with trends, comparisons, and maps.',
    purpose: 'How is one indicator performing over time and across places?',
    whenToUse: 'Use this section to review a program or to find the places that need attention.',
    howToOpen: [
      'On the home page, click View Routine Health Indicators.',
      'Choose the Monthly, Quarterly, Data Elements, or Adjusted Denominator tab.',
      'Open the filter panel, choose the Program, Sub Program, and Indicator, then click Apply filters.',
    ],
    screenshot: {
      id: 'sc-routine',
      imagePath: 'images/guide/routine-monthly.png',
      title: 'Routine Health Indicators, Monthly tab',
      altText: 'A performance card, a baseline and target chart, a comparison by organisation unit, and a woreda map.',
      annotations: [
        { number: 1, title: 'Indicators Performance', description: 'The result so far, with the target and baseline.', position: { top: '30%', left: '6%' } },
        { number: 2, title: 'Performance vs Baseline/Target', description: 'Each month against the baseline and target.', position: { top: '35%', left: '38%' } },
        { number: 3, title: 'Comparison by Org Units', description: 'Select two or more organisation units in the filter panel to compare them.', position: { top: '72%', left: '6%' } },
        { number: 4, title: 'Woreda Level Heatmap', description: 'A map colored by value. Read the color key on the map.', position: { top: '72%', left: '54%' } },
      ],
    },
    extraScreenshots: [
      {
        id: 'sc-adjusted',
        imagePath: 'images/guide/routine-adjusted.png',
        title: 'Routine Health Indicators, Adjusted Denominator tab',
        altText: 'A table and chart comparing DHIS2 coverage with coverage using an external population figure.',
      },
    ],
    tabs: [
      { name: 'Monthly', description: 'Performance card, chart against baseline and target, comparison by organisation unit, woreda map, and trend.' },
      { name: 'Quarterly', description: 'The same views for indicators reported every quarter.' },
      { name: 'Data Elements', description: 'The raw values behind indicators. It has two tabs: Data Element Performance Trend and Data Element Performance by Category.' },
      { name: 'Adjusted Denominator', description: 'Compares DHIS2 coverage with coverage using a different population figure.' },
    ],
    filters: [
      'Monthly: Year, Month, Organisation unit, Program, Sub Program, Indicator, CBMP',
      'Quarterly: Year, Quarter, Organisation unit, Program, Sub Program, Indicators, CBMP',
      'Data Elements: Year, Organisation unit, Program, Sub Program, Data Element, Facility Type, Ownership, CBMP',
      'Adjusted Denominator: Year, Organisation unit, External Population Indicators',
    ],
    howToRead: [
      'Compare performance with both the baseline and the target.',
      'Each map has its own color key. On a coverage map, red is low and green is high. Blue means above 100 or below 0, and grey means no data.',
      'Use the map zoom buttons, or hold Ctrl and scroll, to look closer.',
    ],
    ifSomethingLooksWrong: [
      'A value above 100% can happen when the population estimate is lower than the number of people served. See the Adjusted Denominator tab.',
      'If a value rises or falls sharply in one month, check Data Quality for the same place and period.',
    ],
  },
  {
    id: 'module-multi-source',
    name: 'Multi Source',
    badgeNumber: '4',
    shortSummary: 'Data from surveys, international estimates, and the facility registry, plus links to other dashboards.',
    purpose: 'What do sources outside routine reporting show?',
    whenToUse: 'Use this section to look at long-term patterns or to find a related national dashboard.',
    accessNote: 'Multi Source is shown only to national-level users. If you do not see this tab, your account does not have access to it.',
    howToOpen: [
      'On the home page, click View Multi Source.',
      'Choose a tab for the source you want.',
      'Open the filter panel to choose the indicator.',
    ],
    screenshot: {
      id: 'sc-multi',
      imagePath: 'images/guide/multi-wuenic.png',
      title: 'Multi Source, WUENIC tab',
      altText: 'The number of doses beside a line chart comparing HMIS and WUENIC BCG coverage from 2015 to 2023.',
    },
    extraScreenshots: [
      {
        id: 'sc-multi-other',
        imagePath: 'images/guide/multi-other.png',
        title: 'Multi Source, Other Dashboards tab',
        altText: 'Four cards linking to HISPMD, HEAT+, Woreda Transformation, and Fanos.',
      },
    ],
    tabs: [
      { name: 'WUENIC', description: 'Number of doses and a trend comparing HMIS and WUENIC coverage.' },
      { name: 'IGME', description: 'Child mortality trends and results by gender.' },
      { name: 'EDHS', description: 'Survey trends and results by category.' },
      { name: 'MFR', description: 'A map of facilities by type and a table of services for a selected facility.' },
      { name: 'Other Dashboards', description: 'Links to HISPMD, the Health Equity Assessment Toolkit (HEAT+), Woreda Transformation, and Fanos. Each opens in a new window.' },
    ],
    filters: [
      'WUENIC: Indicators, Year',
      'IGME: Indicators',
      'EDHS: Indicators, Category, Sub Category, Year',
      'MFR: Year, Organisation unit',
    ],
    howToRead: [
      'These sources are measured differently, so their numbers will not match exactly. Look at whether they move in the same direction.',
      'Surveys and estimates are not monthly. Look at the years shown on each chart.',
    ],
    ifSomethingLooksWrong: [
      'If the MFR tab says "Showing the first 10k rows only", not all facilities are displayed. Narrow your selection with the filters.',
      'If an Other Dashboards link asks you to log in, that dashboard has its own account.',
    ],
  },
  {
    id: 'module-triangulation',
    name: 'Triangulation',
    badgeNumber: '5',
    shortSummary: 'Puts the same indicator from two sources side by side.',
    purpose: 'Do DHIS2 and other sources agree on this indicator?',
    whenToUse: 'Use this section when a number looks surprising, or before you rely on an indicator for an important decision.',
    accessNote: 'Triangulation is shown to national-level users and to users in Dire Dawa City Administration. If you do not see this tab, your account does not have access to it.',
    howToOpen: [
      'On the home page, click View Triangulation.',
      'Choose EDHS vs DHIS2 or eCHIS vs DHIS2.',
    ],
    screenshot: {
      id: 'sc-tri',
      imagePath: 'images/guide/tri-edhs.png',
      title: 'Triangulation, EDHS vs DHIS2 tab',
      altText: 'Four bar charts comparing DHIS2 and EDHS values for neonatal deaths, CAR, full immunization, and skilled birth attendance.',
    },
    tabs: [
      { name: 'EDHS vs DHIS2', description: 'Compares DHIS2 with the survey for % of Neonatal Deaths, CAR, Full Immunization Coverage, and Skilled Birth Attendance.' },
      { name: 'eCHIS vs DHIS2', description: 'Compares eCHIS with DHIS2 for the chosen indicator. The 2016 eCHIS data was limited to Dire Dawa Region.' },
    ],
    filters: ['EDHS vs DHIS2: no filters', 'eCHIS vs DHIS2: Indicators'],
    howToRead: [
      'A gap does not tell you which source is right. It tells you where to look more closely.',
      'Routine data can also exceed 100% when the population estimate is too low.',
    ],
    ifSomethingLooksWrong: [
      'Check the source and date at the top of the page. The two sources may cover different periods.',
      'Check Data Quality for the same place before drawing a conclusion from a gap.',
    ],
  },
  {
    id: 'module-health-intelligence',
    name: 'Health Intelligence',
    badgeNumber: '6',
    shortSummary: 'A separate dashboard that brings together services, workforce, financing, supply, and other areas.',
    purpose: 'What is the overall picture across the health system?',
    whenToUse: 'Use this section for a high-level review across different parts of the health system.',
    accessNote: 'Health Intelligence is shown only to national-level users.',
    howToOpen: [
      'On the home page, click View Health Intelligence.',
      'Choose a tab across the top. Use the arrow at the right end of the tabs if you cannot see them all.',
      'Open the filter panel to change the year or the place.',
    ],
    screenshot: {
      id: 'sc-hi',
      imagePath: 'images/guide/hi-maternal.png',
      title: 'Health Intelligence, Services Delivery, Maternal tab',
      altText: 'Maternal health charts from DHIS2 and EDHS, including a map of institutional maternal deaths.',
    },
    extraScreenshots: [
      {
        id: 'sc-hi-financing',
        imagePath: 'images/guide/hi-financing.png',
        title: 'Health Intelligence, Health Financing tab',
        altText: 'Cards for eligible households, CBHI member households, and budget share, with trend and regional charts.',
      },
      {
        id: 'sc-hi-phc',
        imagePath: 'images/guide/hi-phc.png',
        title: 'Health Intelligence, PHC tab',
        altText: 'The Primary Health Care Status Dashboard with health status, system capacity, and service performance.',
      },
    ],
    tabs: [
      { name: 'Services Delivery', description: 'Maternal, EDAM (Fistula, Prolapse, Still Birth), Neonatal, NCD (Risk Factors, Screenings), Malaria, HIV, Family Planning, and TB.' },
      { name: 'Health Equity', description: 'Simple Measures and Order Disproportionality, showing how an indicator differs between groups.' },
      { name: 'Health Work Force', description: 'Total workforce, staff by category, and density per 1,000 people.' },
      { name: 'Health Financing', description: 'CBHI households and coverage, budget share, and SDG Performance Fund disbursement.' },
      { name: 'Supply and Logistics', description: 'Wastage, procurement lead time, supply, and fill rates.' },
      { name: 'Blood Donation', description: 'Tests, positivity, units collected, and donation by region and center.' },
      { name: 'PHEM', description: 'Suspected disease cases, deaths, and case fatality rate, by region.' },
      { name: 'Infrastructure', description: 'Functional facilities by type and region, and the facility map.' },
      { name: 'PHC', description: 'The Primary Health Care Status Dashboard, which also links to a regional scorecard.' },
      { name: 'Digital Systems Monitoring', description: 'Monitoring of digital health systems. This page loads from another system and can take a while.' },
    ],
    filters: [
      'Year, Quarter, Month, and Organisation unit, where they apply',
      'Health Equity: Equity Year, Dimension, Subgroup, and Indicator',
      'Blood Donation: Calendar Year, Blood Region, and Center',
      'PHEM: PHEM Diseases',
    ],
    howToRead: [
      'Each tab shows its own source and data date at the top. These differ between tabs, so check them before comparing.',
      'Some charts show a warning when only the first rows of the data are displayed.',
    ],
    ifSomethingLooksWrong: [
      'A message such as "No valid records were found" means there is no data for that year and place. Try another year.',
      'If the PHC or Digital Systems Monitoring tab stays blank, wait a moment and reload the page.',
    ],
  },
  {
    id: 'module-ai-assistant',
    name: 'AI Assistant',
    badgeNumber: '7',
    shortSummary: 'Ask questions in plain language, look for unusual values, and create reports.',
    purpose: 'How can I get an answer without searching through tabs and filters?',
    whenToUse: 'Use it for a quick answer, a first look at unusual values, or a first draft of a report.',
    howToOpen: [
      'On the home page, click Open Assistant.',
      'Choose Chat, Anomaly, Report Generator, or Help at the top.',
    ],
    screenshot: {
      id: 'sc-ai-chat',
      imagePath: 'images/guide/ai-chat.png',
      title: 'AI Assistant, Chat',
      altText: 'The chat page with suggested questions, a question box, and a list of earlier chats.',
      annotations: [
        { number: 1, title: 'Tabs', description: 'Move between Chat, Anomaly, Report Generator, and Help.', position: { top: '8.7%', left: '21.5%' } },
        { number: 2, title: 'Chat history', description: 'Start a new chat or reopen an earlier one.', position: { top: '14%', left: '2%' } },
        { number: 3, title: 'Suggested questions', description: 'Click one to get started.', position: { top: '46.5%', left: '31%' } },
        { number: 4, title: 'Question box', description: 'Type your question, or use the microphone to speak it.', position: { top: '72.7%', left: '38%' } },
        { number: 5, title: 'Language', description: 'Choose the language you want to use.', position: { top: '8.7%', left: '87.5%' } },
      ],
    },
    extraScreenshots: [
      {
        id: 'sc-ai-anomaly',
        imagePath: 'images/guide/ai-anomaly.png',
        title: 'AI Assistant, Anomaly',
        altText: 'Indicator and organisation unit panels, a Run button, a results area, and a Feedback Alerts panel.',
        annotations: [
          { number: 1, title: 'Indicator', description: 'Search for and choose the indicator.', position: { top: '22.9%', left: '6.5%' } },
          { number: 2, title: 'Org Unit Hierarchy', description: 'Choose the place.', position: { top: '39.7%', left: '8.5%' } },
          { number: 3, title: 'Run', description: 'Click to start the check.', position: { top: '54.6%', left: '6.8%' } },
          { number: 4, title: 'Results tabs', description: 'Anomaly Detection shows unusual values over time. Unexpected Datasets Reporting shows unusual reporting.', position: { top: '15%', left: '19%' } },
          { number: 5, title: 'Feedback Alerts', description: 'A count of anomalies by High, Medium, and New.', position: { top: '14.7%', left: '85.5%' } },
        ],
      },
      {
        id: 'sc-ai-report',
        imagePath: 'images/guide/ai-report-generator.png',
        title: 'AI Assistant, Report Generator',
        altText: 'Template, parameter, and geography settings beside a sample report preview with language and export options.',
        annotations: [
          { number: 1, title: 'Template', description: 'Choose the type of report.', position: { top: '23%', left: '12.5%' } },
          { number: 2, title: 'Parameters', description: 'Choose the period.', position: { top: '30%', left: '10%' } },
          { number: 3, title: 'Geography', description: 'Choose the place.', position: { top: '37%', left: '9.5%' } },
          { number: 4, title: 'Language and format', description: 'English or Amharic, and DOCX or PPTX.', position: { top: '89%', left: '55.5%' } },
          { number: 5, title: 'Generate Report', description: 'Creates the report. Until then, the page shows only a sample, so do not use its numbers.', position: { top: '95.8%', left: '74.5%' } },
        ],
      },
    ],
    tabs: [
      { name: 'Chat', description: 'Ask about indicators, places, and time periods. Answers can include charts, tables, and explanations.' },
      { name: 'Anomaly', description: 'Choose an indicator and a place, then click Run to look for unusual values.' },
      { name: 'Report Generator', description: 'Create a report and export it as DOCX or PPTX. Your last 3 reports are listed on the page.' },
      { name: 'Help', description: 'Guidance and example questions.' },
    ],
    filters: [
      'Name the indicator, place, and period in your question.',
      'Good: "What is the malaria positivity rate in Oromia for 2017 E.C.?"',
      'Too general: "Show malaria data."',
    ],
    howToRead: [
      'AI answers may contain errors. Check important numbers against the dashboard before you use them.',
      'Do not enter patient names or other personal information.',
    ],
    ifSomethingLooksWrong: [
      'If an answer disagrees with the dashboard, check the indicator, place, and period that the answer used.',
      'If the answer is not what you wanted, ask again with a more specific indicator, place, and period.',
    ],
  },
];

export const CHART_INTERPRETATION_RULES = [
  { concept: 'Baseline', color: 'Teal bar', meaning: 'The earlier value used as a starting point for comparison.' },
  { concept: 'Performance', color: 'Dark blue bar', meaning: 'The result for the period you selected.' },
  { concept: 'Target', color: 'Green line', meaning: 'The value the program aims to reach.' },
];

export const TROUBLESHOOTING_ITEMS = [
  {
    issue: 'I cannot log in',
    actions: [
      'Check your username and password carefully.',
      'Try again in a private browser window.',
      'If it still fails, contact the person who gave you your account.',
    ],
  },
  {
    issue: 'I do not see a section or tab',
    actions: [
      'Some sections are shown only to certain users. See the note at the start of each section.',
      'If you think you should have access, contact your dashboard administrator.',
    ],
  },
  {
    issue: 'A chart says "Couldn\'t load this visual"',
    actions: [
      'Click Retry.',
      'If it still fails, your account may not have access to that data. Contact your dashboard administrator.',
    ],
  },
  {
    issue: 'A chart is empty or says there is no data',
    actions: [
      'Your filters may be too narrow. Click Clear all filters, then add them back one at a time.',
      'Try an earlier month or year. The latest period may not be reported yet.',
    ],
  },
  {
    issue: 'A filter list is empty or has the wrong choices',
    actions: [
      'Choose the filter above it first. For example, choose the Program before the Sub Program.',
      'Reload the page if the choices do not update.',
    ],
  },
  {
    issue: 'Two charts show different numbers',
    actions: [
      'Compare the grey line under each chart title. It shows the year, place, source, and data date.',
      'A card can show the year so far, while a bar chart shows single months.',
    ],
  },
];
