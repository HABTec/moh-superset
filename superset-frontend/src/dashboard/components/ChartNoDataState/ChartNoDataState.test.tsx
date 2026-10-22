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
import fetchMock from 'fetch-mock';
import {
  createStore,
  render,
  screen,
  userEvent,
  waitFor,
} from 'spec/helpers/testing-library';
import reducerIndex from 'spec/helpers/reducerIndex';
import { stateWithoutNativeFilters } from 'spec/fixtures/mockStore';
import ChartNoDataState from '.';
import { RootState } from 'src/dashboard/types';

const getDashboardState = (store: { getState: () => unknown }) =>
  store.getState() as RootState;

fetchMock.get('glob:*/api/v1/moh/dhis2/data-freshness', { sources: {} });
fetchMock.get('glob:*/api/v1/moh/dhis2/latest-period', {
  latestPeriod: { period: '201812', fiscalYear: '2019', quarter: 1 },
});
fetchMock.get('glob:*/api/v1/moh/dhis2/me/organisationUnit', {
  organisationUnit: { id: 'XU2wpLlX4Vk', name: 'Oromia Region', level: 2 },
});

const filter = (
  id: string,
  name: string,
  column: string,
  chartsInScope: number[],
) => ({
  id,
  name,
  filterType: 'filter_select',
  type: 'NATIVE_FILTER',
  targets: [{ datasetId: 1, column: { name: column } }],
  defaultDataMask: { filterState: { value: undefined } },
  controlValues: {},
  cascadeParentIds: [],
  scope: { rootPath: ['TAB-1'], excluded: [] },
  chartsInScope,
  tabsInScope: [],
});

const state = {
  ...stateWithoutNativeFilters,
  dashboardInfo: {
    ...stateWithoutNativeFilters.dashboardInfo,
    metadata: {
      ...stateWithoutNativeFilters.dashboardInfo.metadata,
      native_filter_configuration: [
        filter('year', 'Year', 'fiscal_year', [10]),
        filter('org', 'Org Unit', 'region', [10]),
      ],
    },
  },
  dashboardLayout: {
    past: [],
    future: [],
    present: {
      'TAB-1': {
        id: 'TAB-1',
        type: 'TAB',
        children: ['CHART-10', 'CHART-20'],
        parents: ['ROOT_ID', 'TABS-1'],
        meta: { text: 'Services Delivery' },
      },
      'CHART-10': {
        id: 'CHART-10',
        type: 'CHART',
        children: [],
        parents: ['ROOT_ID', 'TABS-1', 'TAB-1'],
        meta: { chartId: 10 },
      },
      'CHART-20': {
        id: 'CHART-20',
        type: 'CHART',
        children: [],
        parents: ['ROOT_ID', 'TABS-1', 'TAB-1'],
        meta: { chartId: 20 },
      },
    },
  },
  dashboardState: {
    ...stateWithoutNativeFilters.dashboardState,
    editMode: false,
    activeTabs: ['TAB-1'],
  },
  dataMask: {
    year: {
      id: 'year',
      filterState: { value: ['2018'], label: '2018 EFY' },
      extraFormData: {},
    },
    org: { id: 'org', filterState: { value: undefined }, extraFormData: {} },
  },
};

const renderNoData = (props: { chartId: number; height?: number }) => {
  const store = createStore(state, reducerIndex);
  render(<ChartNoDataState width={600} height={400} {...props} />, {
    store,
    useRedux: true,
    useRouter: true,
  });
  return store;
};

test('names the outcome and the period and org unit that produced it', async () => {
  renderNoData({ chartId: 10 });
  expect(
    screen.getByText('No data for this filter combination'),
  ).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getByTestId('chart-no-data')).toHaveTextContent(
      'No valid records were found for 2018 EFY · Oromia Region.',
    ),
  );
});

test('Clear filters asks the filter bar to clear and apply', async () => {
  const store = renderNoData({ chartId: 10 });
  await userEvent.click(screen.getByTestId('chart-no-data-clear'));
  expect(getDashboardState(store).dashboardState.filterBarClearRequested).toBe(
    true,
  );
});

test('Change period opens the filter bar', async () => {
  const store = renderNoData({ chartId: 10 });
  await userEvent.click(screen.getByTestId('chart-no-data-change-period'));
  expect(getDashboardState(store).dashboardState.nativeFiltersBarOpen).toBe(
    true,
  );
});

test('offers no filter actions when no filter reaches the chart', () => {
  renderNoData({ chartId: 20 });
  expect(screen.getByTestId('chart-no-data')).toHaveTextContent(
    'No valid records were found for the selected filters.',
  );
  expect(screen.queryByTestId('chart-no-data-clear')).not.toBeInTheDocument();
  expect(
    screen.queryByTestId('chart-no-data-change-period'),
  ).not.toBeInTheDocument();
});

test('a KPI-sized tile keeps the title and actions but drops the context line', () => {
  renderNoData({ chartId: 10, height: 90 });
  expect(
    screen.getByText('No data for this filter combination'),
  ).toBeInTheDocument();
  expect(screen.queryByText(/No valid records/)).not.toBeInTheDocument();
  expect(screen.getByTestId('chart-no-data-clear')).toBeInTheDocument();
});
