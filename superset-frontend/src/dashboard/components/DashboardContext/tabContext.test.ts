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
import { DataMaskStateWithId, Filter } from '@superset-ui/core';
import { DashboardLayout } from 'src/dashboard/types';
import {
  collectTabSelections,
  formatCompletenessPeriod,
  formatSourceAsOf,
  getActiveTabChartIds,
  TabCompleteness,
} from './tabContext';

const filter = (id: string, column: string, filterType = 'filter_select') =>
  ({
    id,
    name: id,
    filterType,
    type: 'NATIVE_FILTER',
    targets: column ? [{ datasetId: 1, column: { name: column } }] : [{}],
  }) as unknown as Filter;

const nehase = {
  period: '201812',
  fiscalYear: '2019',
  monthName: 'Nehase',
  quarterName: 'Hamle to Meskerem (Q1)',
};

test('picks the charts on the innermost active tab only', () => {
  const layout = {
    'CHART-1': {
      type: 'CHART',
      parents: ['ROOT_ID', 'TAB-A'],
      meta: { chartId: 1 },
    },
    'CHART-2': {
      type: 'CHART',
      parents: ['ROOT_ID', 'TAB-B'],
      meta: { chartId: 2 },
    },
    'TAB-A': { type: 'TAB', parents: ['ROOT_ID'], meta: { text: 'A' } },
  } as unknown as DashboardLayout;
  expect(getActiveTabChartIds(layout, 'TAB-A')).toEqual([1]);
  expect(getActiveTabChartIds(layout, undefined)).toEqual([1, 2]);
});

test('collects indicators from chart filters and selections from in-scope filters', () => {
  const dataMask = {
    year: { id: 'year', filterState: { value: ['2019'] }, extraFormData: {} },
    month: { id: 'month', filterState: { value: 'Nehase' }, extraFormData: {} },
    ds: { id: 'ds', filterState: { value: ['01.1 - RMH'] }, extraFormData: {} },
    org: {
      id: 'org',
      filterState: { value: ['Arsi Zone'] },
      extraFormData: {
        filters: [{ col: 'zone', op: 'IN', val: ['Arsi Zone'] }],
      },
    },
  } as unknown as DataMaskStateWithId;

  const selections = collectTabSelections({
    chartFormData: [
      {
        adhoc_filters: [
          {
            expressionType: 'SIMPLE',
            clause: 'WHERE',
            subject: 'indicator',
            operator: 'IN',
            comparator: ['Skilled Birth Attendance'],
          },
          {
            expressionType: 'SIMPLE',
            clause: 'WHERE',
            subject: 'indicator_id',
            operator: '==',
            comparator: 'jsRSjbOfBRb',
          },
          // Not about which indicator: ignored.
          {
            expressionType: 'SIMPLE',
            subject: 'indicator',
            operator: 'NOT IN',
            comparator: ['CAR'],
          },
          {
            expressionType: 'SIMPLE',
            subject: 'data_element_id',
            operator: 'IN',
            comparator: ['lotDArt3TsU'],
          },
          { expressionType: 'SQL', sqlExpression: "indicator = 'X'" },
        ],
      },
      { adhoc_filters: [] },
      undefined,
    ],
    filters: [
      filter('year', 'fiscal_year'),
      filter('month', 'month_name'),
      filter('ds', 'data_set_name'),
      filter('org', '', 'filter_org_unit_tree'),
    ],
    dataMask,
  });

  expect(selections).toEqual({
    indicators: ['Skilled Birth Attendance'],
    indicatorIds: ['jsRSjbOfBRb'],
    dataElements: [],
    dataElementIds: ['lotDArt3TsU'],
    dataSets: ['01.1 - RMH'],
    fiscalYears: ['2019'],
    quarters: [],
    months: ['Nehase'],
    orgUnits: { zone: ['Arsi Zone'] },
  });
});

test('formats how current each kind of source is', () => {
  expect(
    formatSourceAsOf({
      key: 'dhis2',
      label: 'DHIS2',
      kind: 'dhis2',
      latestPeriod: nehase,
    }),
  ).toBe('2019 EFY · Nehase');
  expect(
    formatSourceAsOf({
      key: 'edhs',
      label: 'EDHS',
      kind: 'annual',
      latest: '2024',
    }),
  ).toBe('2024');
  expect(
    formatSourceAsOf({
      key: 'mfr',
      label: 'MFR',
      kind: 'snapshot',
      latest: '2026-05-22',
    }),
  ).toBe('updated 2026-05-22');
  expect(
    formatSourceAsOf({ key: 'phem', label: 'PHEM', kind: 'annual' }),
  ).toBeNull();
});

test('describes the months a completeness figure covers', () => {
  const base: TabCompleteness = {
    value: 93.5,
    timeliness: 84.6,
    months: 1,
    from: nehase,
    to: nehase,
    includesInProgress: false,
    target: 80,
    meetsTarget: true,
  };
  expect(formatCompletenessPeriod(base)).toBe('2019 EFY · Nehase');
  expect(
    formatCompletenessPeriod({
      ...base,
      months: 3,
      from: { ...nehase, period: '201811', monthName: 'Hamle' },
      to: { ...nehase, period: '201901', monthName: 'Meskerem' },
    }),
  ).toBe('2019 EFY · Hamle–Meskerem');
  expect(
    formatCompletenessPeriod({
      ...base,
      months: 12,
      from: {
        ...nehase,
        period: '201711',
        fiscalYear: '2018',
        monthName: 'Hamle',
      },
    }),
  ).toBe('2018 EFY · Hamle – 2019 EFY · Nehase');
});
