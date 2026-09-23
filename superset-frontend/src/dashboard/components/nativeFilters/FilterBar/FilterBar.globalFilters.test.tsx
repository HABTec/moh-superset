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

import {
  act,
  createStore,
  render,
  screen,
  within,
} from 'spec/helpers/testing-library';
import fetchMock from 'fetch-mock';
import reducerIndex from 'spec/helpers/reducerIndex';
import { stateWithoutNativeFilters } from 'spec/fixtures/mockStore';
import { Preset } from '@superset-ui/core';
import { SelectFilterPlugin } from 'src/filters/components';
import { FilterBarOrientation } from 'src/dashboard/types';
import { resetAssignedOrgUnitCacheForTests } from 'src/filters/components/OrgUnitTree/useAssignedOrgUnit';
import FilterBar from '.';

class MainPreset extends Preset {
  constructor() {
    super({
      name: 'Legacy charts',
      plugins: [new SelectFilterPlugin().configure({ key: 'filter_select' })],
    });
  }
}

new MainPreset().register();

beforeEach(() => {
  resetAssignedOrgUnitCacheForTests();
});

const ORG_UNIT_ME_URL = 'glob:*/api/v1/moh/dhis2/me/organisationUnit';
// fetch-mock only recognises a bare matcher string as the route's name on
// the route that first registered it; overriding the response in a later
// test needs an explicit, stable name so removeRoute() actually finds it.
const ORG_UNIT_ME_ROUTE_NAME = 'org-unit-me';

function mockAssignedOrgUnit(
  organisationUnit: { id: string; name: string; level: number } | null,
) {
  fetchMock.removeRoute(ORG_UNIT_ME_ROUTE_NAME);
  fetchMock.get(
    ORG_UNIT_ME_URL,
    { organisationUnit },
    { name: ORG_UNIT_ME_ROUTE_NAME },
  );
}

function createFilter(id: string, name: string, column: string) {
  return {
    id,
    name,
    filterType: 'filter_select',
    targets: [{ datasetId: 1, column: { name: column } }],
    defaultDataMask: { filterState: { value: null }, extraFormData: {} },
    controlValues: {},
    cascadeParentIds: [],
    scope: { rootPath: ['ROOT_ID'], excluded: [] },
    type: 'NATIVE_FILTER',
    description: '',
    chartsInScope: [],
    tabsInScope: [],
  };
}

const year = createFilter('year', 'Year', 'fiscal_year');
const quarter = createFilter('quarter', 'Quarter', 'quarter');
const orgUnit = createFilter('org', 'Org Unit', 'region');
const facilityType = createFilter('facility', 'Facility Type', 'type');
const filters = [facilityType, quarter, orgUnit, year];

const dataMask = {
  year: {
    id: 'year',
    filterState: { value: ['2018'], label: '2018 EFY' },
    extraFormData: {
      filters: [{ col: 'fiscal_year', op: 'IN', val: ['2018'] }],
    },
  },
  quarter: {
    id: 'quarter',
    filterState: { value: ['Q3'], label: 'Q3' },
    extraFormData: {
      filters: [{ col: 'quarter', op: 'IN', val: ['Q3'] }],
    },
  },
  org: { id: 'org', filterState: { value: undefined }, extraFormData: {} },
  facility: {
    id: 'facility',
    filterState: { value: undefined },
    extraFormData: {},
  },
};

const state = {
  ...stateWithoutNativeFilters,
  dashboardInfo: {
    id: 1,
    dash_edit_perm: true,
    filterBarOrientation: FilterBarOrientation.Vertical,
    metadata: { native_filter_configuration: filters },
  },
  dashboardState: {
    ...stateWithoutNativeFilters.dashboardState,
    activeTabs: ['ROOT_ID'],
  },
  dataMask,
  nativeFilters: {
    filters: Object.fromEntries(filters.map(filter => [filter.id, filter])),
    filtersState: {},
  },
};

function renderOpenFilterBar() {
  return render(
    <FilterBar
      orientation={FilterBarOrientation.Vertical}
      verticalConfig={{
        width: 280,
        height: 600,
        offset: 0,
        filtersOpen: true,
        toggleFiltersBar: jest.fn(),
      }}
    />,
    {
      initialState: state,
      useDnd: true,
      useRedux: true,
      useRouter: true,
    },
  );
}

test('groups Period and Organisation unit in a Global filters box above dashboard-specific filters', async () => {
  renderOpenFilterBar();

  const globalBox = await screen.findByTestId(
    'global-filters',
    {},
    { timeout: 5000 },
  );
  expect(within(globalBox).getByText('Global filters')).toBeInTheDocument();
  expect(within(globalBox).getByTestId('period-card')).toBeInTheDocument();
  expect(within(globalBox).getByText('Organisation unit')).toBeInTheDocument();

  expect(
    within(globalBox).queryByText('Facility Type'),
  ).not.toBeInTheDocument();
  expect(screen.getByText('Facility Type')).toBeInTheDocument();
  expect(screen.getByText('Dashboard-specific')).toBeInTheDocument();
});

test('shows one Period card holding the period type, year and quarter controls', async () => {
  renderOpenFilterBar();

  const periodCard = await screen.findByTestId(
    'period-card',
    {},
    { timeout: 5000 },
  );
  expect(within(periodCard).getByText('Period')).toBeInTheDocument();
  expect(within(periodCard).getByText('Period type')).toBeInTheDocument();
  expect(within(periodCard).getByText('Year')).toBeInTheDocument();
  expect(within(periodCard).getByText('Quarter')).toBeInTheDocument();
});

test('keeps rendering when a tab switch changes which filters are in scope', async () => {
  const withScope = (
    filter: ReturnType<typeof createFilter>,
    tabs: string[],
  ) => ({
    ...filter,
    scope: { rootPath: tabs, excluded: [] },
  });
  const tabbedFilters = [
    withScope(facilityType, ['TAB-B']),
    withScope(quarter, ['TAB-A', 'TAB-B']),
    withScope(orgUnit, ['TAB-A']),
    withScope(year, ['TAB-A', 'TAB-B']),
  ];
  const tab = (id: string) => ({
    id,
    type: 'TAB',
    children: [],
    parents: ['ROOT_ID'],
    meta: { text: id },
  });
  const tabbedState = {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: { native_filter_configuration: tabbedFilters },
    },
    dashboardLayout: {
      past: [],
      future: [],
      present: { 'TAB-A': tab('TAB-A'), 'TAB-B': tab('TAB-B') },
    },
    dashboardState: {
      ...state.dashboardState,
      activeTabs: ['TAB-A'],
    },
    nativeFilters: {
      filters: Object.fromEntries(
        tabbedFilters.map(filter => [filter.id, filter]),
      ),
      filtersState: {},
    },
  };
  const store = createStore(tabbedState, reducerIndex);

  render(
    <FilterBar
      orientation={FilterBarOrientation.Vertical}
      verticalConfig={{
        width: 280,
        height: 600,
        offset: 0,
        filtersOpen: true,
        toggleFiltersBar: jest.fn(),
      }}
    />,
    { store, useDnd: true, useRedux: true, useRouter: true },
  );

  const globalBox = await screen.findByTestId(
    'global-filters',
    {},
    { timeout: 5000 },
  );
  expect(within(globalBox).getByText('Organisation unit')).toBeVisible();
  expect(screen.getByText('Facility Type')).not.toBeVisible();

  act(() => {
    store.dispatch({
      type: 'SET_ACTIVE_TAB',
      activeTabs: ['TAB-B'],
      prevTabId: 'TAB-A',
      inactiveTabs: ['TAB-A'],
    });
  });

  expect(await screen.findByText('Facility Type')).toBeVisible();
  expect(within(globalBox).getByText('Organisation unit')).not.toBeVisible();
  expect(screen.getByTestId('global-filters')).toBeInTheDocument();
  expect(screen.getByTestId('period-card')).toBeVisible();

  act(() => {
    store.dispatch({
      type: 'SET_ACTIVE_TAB',
      activeTabs: ['TAB-A'],
      prevTabId: 'TAB-B',
      inactiveTabs: ['TAB-B'],
    });
  });

  expect(await screen.findByText('Organisation unit')).toBeVisible();
  expect(screen.getByText('Facility Type')).not.toBeVisible();
});

test('keeps an out-of-scope Organisation unit visible with its value and a not-available note, without clearing it', async () => {
  mockAssignedOrgUnit(null);
  // Native filters are persisted with a "NATIVE_FILTER-" id; the dataMask
  // lookup for the applied value depends on it, so use realistic ids here.
  const prefixedYear = createFilter(
    'NATIVE_FILTER-year',
    'Year',
    'fiscal_year',
  );
  const prefixedOrgUnit = createFilter(
    'NATIVE_FILTER-org',
    'Org Unit',
    'region',
  );
  const withScope = (
    filter: ReturnType<typeof createFilter>,
    tabs: string[],
  ) => ({
    ...filter,
    scope: { rootPath: tabs, excluded: [] },
  });
  const tabbedFilters = [
    withScope(prefixedOrgUnit, ['TAB-A']),
    withScope(prefixedYear, ['TAB-A', 'TAB-B']),
  ];
  const tab = (id: string) => ({
    id,
    type: 'TAB',
    children: [],
    parents: ['ROOT_ID'],
    meta: { text: id },
  });
  const tabbedState = {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: { native_filter_configuration: tabbedFilters },
    },
    dashboardLayout: {
      past: [],
      future: [],
      present: { 'TAB-A': tab('TAB-A'), 'TAB-B': tab('TAB-B') },
    },
    dashboardState: {
      ...state.dashboardState,
      activeTabs: ['TAB-A'],
    },
    dataMask: {
      'NATIVE_FILTER-org': {
        id: 'NATIVE_FILTER-org',
        filterState: { value: ['Oromia'], label: 'Oromia' },
        extraFormData: {},
      },
    },
    nativeFilters: {
      filters: Object.fromEntries(
        tabbedFilters.map(filter => [filter.id, filter]),
      ),
      filtersState: {},
    },
  };
  const store = createStore(tabbedState, reducerIndex);

  render(
    <FilterBar
      orientation={FilterBarOrientation.Vertical}
      verticalConfig={{
        width: 280,
        height: 600,
        offset: 0,
        filtersOpen: true,
        toggleFiltersBar: jest.fn(),
      }}
    />,
    { store, useDnd: true, useRedux: true, useRouter: true },
  );

  await screen.findByTestId('global-filters', {}, { timeout: 5000 });
  expect(screen.queryByTestId('org-unit-unavailable')).not.toBeInTheDocument();

  act(() => {
    store.dispatch({
      type: 'SET_ACTIVE_TAB',
      activeTabs: ['TAB-B'],
      prevTabId: 'TAB-A',
      inactiveTabs: ['TAB-A'],
    });
  });

  expect(await screen.findByTestId('org-unit-unavailable')).toHaveTextContent(
    'Organisation unit: Oromia — not available for this source',
  );
  // Still visible and unchanged: switching tabs never touches the value, so
  // it still applies wherever the filter is in scope.
  expect(screen.getByTestId('global-filters')).toBeInTheDocument();
  expect(
    (
      store.getState() as unknown as {
        dataMask: Record<string, { filterState: { value: unknown } }>;
      }
    ).dataMask['NATIVE_FILTER-org'].filterState.value,
  ).toEqual(['Oromia']);
});

test("shows the user's own area for an out-of-scope Organisation unit with no selection", async () => {
  mockAssignedOrgUnit({ id: 'XU2wpLlX4Vk', name: 'Oromia Region', level: 2 });
  const prefixedYear = createFilter(
    'NATIVE_FILTER-year',
    'Year',
    'fiscal_year',
  );
  const prefixedOrgUnit = createFilter(
    'NATIVE_FILTER-org',
    'Org Unit',
    'region',
  );
  const withScope = (
    filter: ReturnType<typeof createFilter>,
    tabs: string[],
  ) => ({
    ...filter,
    scope: { rootPath: tabs, excluded: [] },
  });
  const tabbedFilters = [
    withScope(prefixedOrgUnit, ['TAB-A']),
    withScope(prefixedYear, ['TAB-A', 'TAB-B']),
  ];
  const tab = (id: string) => ({
    id,
    type: 'TAB',
    children: [],
    parents: ['ROOT_ID'],
    meta: { text: id },
  });
  const tabbedState = {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: { native_filter_configuration: tabbedFilters },
    },
    dashboardLayout: {
      past: [],
      future: [],
      present: { 'TAB-A': tab('TAB-A'), 'TAB-B': tab('TAB-B') },
    },
    dashboardState: {
      ...state.dashboardState,
      activeTabs: ['TAB-B'],
    },
    dataMask: {},
    nativeFilters: {
      filters: Object.fromEntries(
        tabbedFilters.map(filter => [filter.id, filter]),
      ),
      filtersState: {},
    },
  };
  const store = createStore(tabbedState, reducerIndex);

  render(
    <FilterBar
      orientation={FilterBarOrientation.Vertical}
      verticalConfig={{
        width: 280,
        height: 600,
        offset: 0,
        filtersOpen: true,
        toggleFiltersBar: jest.fn(),
      }}
    />,
    { store, useDnd: true, useRedux: true, useRouter: true },
  );

  expect(
    await screen.findByTestId('org-unit-unavailable', {}, { timeout: 5000 }),
  ).toHaveTextContent(
    'Organisation unit: Oromia Region — not available for this source',
  );
});

test('does not show an unavailable Period row when the current tab has one in scope', async () => {
  renderOpenFilterBar();
  await screen.findByTestId('period-card', {}, { timeout: 5000 });
  expect(screen.queryByTestId('period-unavailable')).not.toBeInTheDocument();
});
