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
import { Filter, NativeFilterType } from '@superset-ui/core';
import {
  getFilterBarSection,
  getFilterDisplayName,
  getFilterVisualOrder,
  getPeriodSummary,
  inferPeriodGrain,
  isPeriodFilterVisible,
  partitionFiltersInScope,
  shouldShowPeriodGrainControl,
  sortPeriodFilters,
} from './filterBarLayout';

function mockFilter(
  name: string,
  id = name,
  column?: string,
  filterType = 'filter_select',
): Filter {
  return {
    id,
    name,
    filterType,
    type: NativeFilterType.NativeFilter,
    targets: column ? [{ column: { name: column } }] : [],
    scope: { rootPath: [], excluded: [] },
    controlValues: {},
    defaultDataMask: {},
    cascadeParentIds: [],
    description: '',
  };
}

test('classifies Year, Quarter, Month and Org Unit as global filters', () => {
  expect(getFilterBarSection(mockFilter('Year'))).toEqual('global');
  expect(getFilterBarSection(mockFilter('Quarter'))).toEqual('global');
  expect(getFilterBarSection(mockFilter('Month'))).toEqual('global');
  expect(getFilterBarSection(mockFilter('Org Unit'))).toEqual('global');
});

test('classifies dashboard-specific filters as local', () => {
  expect(getFilterBarSection(mockFilter('Facility Type'))).toEqual('local');
  expect(getFilterBarSection(mockFilter('Equity Year'))).toEqual('local');
  expect(getFilterBarSection(mockFilter('Indicator'))).toEqual('local');
});

test('classifies DHIS2 fiscal period columns as global and survey/coverage years as local', () => {
  expect(getFilterBarSection(mockFilter('Year', 'fy', 'fiscal_year'))).toEqual(
    'global',
  );
  expect(getFilterBarSection(mockFilter('Quarter', 'q', 'quarter'))).toEqual(
    'global',
  );
  expect(getFilterBarSection(mockFilter('Month', 'm', 'month_name'))).toEqual(
    'global',
  );
  expect(getFilterBarSection(mockFilter('Year', 'vax', 'year'))).toEqual(
    'local',
  );
  expect(
    getFilterBarSection(mockFilter('Year', 'edhs', 'survey_year')),
  ).toEqual('local');
});

test('labels the fiscal year control Year inside the Period card', () => {
  expect(getFilterDisplayName(mockFilter('Year', 'fy', 'fiscal_year'))).toEqual(
    'Year',
  );
  expect(getFilterDisplayName(mockFilter('Year', 'vax', 'year'))).toEqual(
    'Year',
  );
  expect(getFilterDisplayName(mockFilter('Org Unit'))).toEqual(
    'Organisation unit',
  );
  expect(getFilterDisplayName(mockFilter('Facility Type'))).toEqual(
    'Facility Type',
  );
});

test('infers period grain from selected values, else from columns in scope', () => {
  const year = mockFilter('Year', 'year', 'fiscal_year');
  const quarter = mockFilter('Quarter', 'quarter', 'quarter');
  const month = mockFilter('Month', 'month', 'month_name');

  expect(inferPeriodGrain([year, quarter, month], {})).toEqual('monthly');
  expect(inferPeriodGrain([year, quarter], {})).toEqual('quarterly');
  expect(inferPeriodGrain([year], {})).toEqual('annual');
  expect(
    inferPeriodGrain([year, quarter, month], {
      quarter: { id: 'quarter', filterState: { value: ['Q1'] } },
    }),
  ).toEqual('quarterly');
  expect(
    inferPeriodGrain([year, quarter, month], {
      month: { id: 'month', filterState: { value: ['Meskerem'] } },
    }),
  ).toEqual('monthly');
});

test('hides quarter and month unless that grain is selected', () => {
  const quarter = mockFilter('Quarter');
  const month = mockFilter('Month');
  expect(isPeriodFilterVisible(quarter, 'annual')).toEqual(false);
  expect(isPeriodFilterVisible(quarter, 'quarterly')).toEqual(true);
  expect(isPeriodFilterVisible(month, 'monthly')).toEqual(true);
  expect(isPeriodFilterVisible(month, 'annual')).toEqual(false);
});

test('shows a period type control when year plus quarter or month are in scope', () => {
  expect(
    shouldShowPeriodGrainControl([
      mockFilter('Year'),
      mockFilter('Quarter'),
      mockFilter('Month'),
    ]),
  ).toEqual(true);
  expect(shouldShowPeriodGrainControl([mockFilter('Year')])).toEqual(false);
});

test('partitions global period and org unit filters from local filters', () => {
  const { periodFilters, orgUnitFilters, localFilters } =
    partitionFiltersInScope([
      mockFilter('Year'),
      mockFilter('Org Unit'),
      mockFilter('Facility Type'),
    ]);
  expect(periodFilters.map(filter => filter.name)).toEqual(['Year']);
  expect(orgUnitFilters.map(filter => filter.name)).toEqual(['Org Unit']);
  expect(localFilters.map(filter => (filter as Filter).name)).toEqual([
    'Facility Type',
  ]);
  expect(
    getFilterVisualOrder('Year', periodFilters, orgUnitFilters, localFilters),
  ).toEqual(10);
  expect(
    getFilterVisualOrder(
      'Facility Type',
      periodFilters,
      orgUnitFilters,
      localFilters,
    ),
  ).toEqual(100);
});

test('orders period filters year, quarter, month regardless of config order', () => {
  const year = mockFilter('Year', 'year', 'fiscal_year');
  const quarter = mockFilter('Quarter', 'quarter', 'quarter');
  const month = mockFilter('Month', 'month', 'month_name');
  expect(
    sortPeriodFilters([month, year, quarter]).map(filter => filter.id),
  ).toEqual(['year', 'quarter', 'month']);
});

test('summarises the selected period for the current period type', () => {
  const year = mockFilter('Year', 'year', 'fiscal_year');
  const quarter = mockFilter('Quarter', 'quarter', 'quarter');
  const month = mockFilter('Month', 'month', 'month_name');
  const dataMask = {
    year: { id: 'year', filterState: { value: ['2018'], label: '2018 EFY' } },
    quarter: { id: 'quarter', filterState: { value: ['Q3'], label: 'Q3' } },
    month: { id: 'month', filterState: { value: ['Meskerem'] } },
  };
  const filters = [month, quarter, year];
  expect(getPeriodSummary(filters, dataMask, 'annual')).toEqual('2018 EFY');
  expect(getPeriodSummary(filters, dataMask, 'quarterly')).toEqual(
    '2018 EFY · Q3',
  );
  expect(getPeriodSummary(filters, dataMask, 'monthly')).toEqual(
    '2018 EFY · Meskerem',
  );
  expect(getPeriodSummary(filters, {}, 'monthly')).toEqual('');
});
