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
import { getGlobalContext, hasOrgUnitFilter } from './globalContext';

function mockFilter(
  id: string,
  name: string,
  column: string,
  overrides: Partial<Filter> = {},
): Filter {
  return {
    id,
    name,
    filterType: 'filter_select',
    type: NativeFilterType.NativeFilter,
    targets: [{ column: { name: column } }],
    scope: { rootPath: [], excluded: [] },
    controlValues: {},
    defaultDataMask: {},
    cascadeParentIds: [],
    description: '',
    ...overrides,
  } as Filter;
}

const year = mockFilter('year', 'Year', 'fiscal_year', {
  defaultDataMask: { filterState: { value: ['2018'] } },
});
const org = mockFilter('org', 'Org Unit', 'region');
const facility = mockFilter('facility', 'Facility Type', 'type');
const filters = { year, org, facility } as Record<string, Filter>;
const everything = () => true;
const latestPeriodLabel = 'Latest: 2019 EFY · Q1 · Nehase';
const args = {
  filters,
  isRelevant: everything,
  orgUnitScopeLabel: 'National',
  latestPeriodLabel,
};

test('describes the selected period and falls back to the org unit scope', () => {
  const context = getGlobalContext({
    ...args,
    dataMask: {
      year: { id: 'year', filterState: { value: ['2018'], label: '2018 EFY' } },
    },
  });
  expect(context.period).toBe('2018 EFY');
  expect(context.orgUnit).toBe('National');
});

test('shows the selected org unit instead of the scope label', () => {
  const context = getGlobalContext({
    ...args,
    dataMask: {
      org: { id: 'org', filterState: { value: ['Oromia'], label: 'Oromia' } },
    },
  });
  expect(context.orgUnit).toBe('Oromia');
});

test('is the default view when filters hold their defaults', () => {
  expect(
    getGlobalContext({
      ...args,
      dataMask: { year: { id: 'year', filterState: { value: ['2018'] } } },
    }).isDefault,
  ).toBe(true);
});

test('is a custom view when the period differs or an org unit is picked', () => {
  expect(
    getGlobalContext({
      ...args,
      dataMask: { year: { id: 'year', filterState: { value: ['2017'] } } },
    }).isDefault,
  ).toBe(false);
  expect(
    getGlobalContext({
      ...args,
      dataMask: {
        year: { id: 'year', filterState: { value: ['2018'] } },
        org: { id: 'org', filterState: { value: ['Oromia'] } },
      },
    }).isDefault,
  ).toBe(false);
});

test('shows the latest period and the user scope where no filter reaches', () => {
  const context = getGlobalContext({
    ...args,
    isRelevant: () => false,
    dataMask: {
      year: { id: 'year', filterState: { value: ['2018'] } },
    },
  });
  expect(context.period).toBe(latestPeriodLabel);
  expect(context.orgUnit).toBe('National');
  expect(context.periodOverridden).toBe(false);
  expect(context.orgUnitOverridden).toBe(false);
});

test('flags a selection the scope does not follow', () => {
  const context = getGlobalContext({
    ...args,
    isRelevant: () => false,
    dataMask: {
      year: { id: 'year', filterState: { value: ['2017'] } },
      org: { id: 'org', filterState: { value: ['Oromia'] } },
    },
  });
  expect(context.periodOverridden).toBe(true);
  expect(context.orgUnitOverridden).toBe(true);
});

test('shows the latest period when a period filter has no selection', () => {
  const context = getGlobalContext({ ...args, dataMask: {} });
  expect(context.period).toBe(latestPeriodLabel);
});

test('does not flag a selected period that already is the latest period', () => {
  const latestPeriod = { fiscalYear: '2019', quarter: 1, monthName: 'Nehase' };
  const notReached = { ...args, isRelevant: () => false, latestPeriod };
  expect(
    getGlobalContext({
      ...notReached,
      dataMask: { year: { id: 'year', filterState: { value: ['2019'] } } },
    }).periodOverridden,
  ).toBe(false);
  expect(
    getGlobalContext({
      ...notReached,
      dataMask: { year: { id: 'year', filterState: { value: ['2017'] } } },
    }).periodOverridden,
  ).toBe(true);
  expect(
    getGlobalContext({ ...notReached, dataMask: {} }).periodOverridden,
  ).toBe(false);
});

test('adds the EFY suffix to a fiscal year that has no label', () => {
  const context = getGlobalContext({
    ...args,
    dataMask: { year: { id: 'year', filterState: { value: ['2018'] } } },
  });
  expect(context.period).toBe('2018 EFY');
});

test('reports nothing when the dashboard has no global filters', () => {
  const context = getGlobalContext({
    filters: { facility } as Record<string, Filter>,
    dataMask: {},
    isRelevant: everything,
    orgUnitScopeLabel: 'National',
    latestPeriodLabel,
  });
  expect(context.period).toBeNull();
  expect(context.orgUnit).toBeNull();
  expect(context.periodOverridden).toBe(false);
  expect(context.orgUnitOverridden).toBe(false);
});

test('finds an org unit filter that has no targets', () => {
  const noTargets = { ...org, targets: undefined } as unknown as Filter;
  expect(hasOrgUnitFilter({ org: noTargets } as Record<string, Filter>)).toBe(
    true,
  );
  expect(hasOrgUnitFilter({ facility } as Record<string, Filter>)).toBe(false);
});
