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
import { RootState } from 'src/dashboard/types';
import ChartContextChip from './ChartContextChip';
import DashboardContextStrip from './DashboardContextStrip';

fetchMock.get('glob:*/api/v1/moh/dhis2/data-freshness', {
  sources: { routine: '2026-09-20T20:46:32', quality: '2026-09-21T06:20:32' },
});

fetchMock.get('glob:*/api/v1/moh/dhis2/latest-period', {
  latestPeriod: {
    period: '201812',
    fiscalYear: '2019',
    quarter: 1,
    monthName: 'Nehase',
  },
});

fetchMock.get('glob:*/api/v1/moh/dhis2/me/organisationUnit', {
  organisationUnit: { id: 'XU2wpLlX4Vk', name: 'Oromia Region', level: 2 },
});

const filter = (
  id: string,
  name: string,
  column: string,
  chartsInScope: number[],
  defaultValue?: string[],
) => ({
  id,
  name,
  filterType: 'filter_select',
  type: 'NATIVE_FILTER',
  targets: [{ datasetId: 1, column: { name: column } }],
  defaultDataMask: { filterState: { value: defaultValue } },
  controlValues: {},
  cascadeParentIds: [],
  scope: { rootPath: ['TAB-1'], excluded: [] },
  chartsInScope,
  tabsInScope: [],
});

const tab = (id: string, text: string, parents: string[]) => ({
  id,
  type: 'TAB',
  children: [],
  parents,
  meta: { text },
});

const year = filter('year', 'Year', 'fiscal_year', [10], ['2018']);
const org = filter('org', 'Org Unit', 'region', [11]);

const state = {
  ...stateWithoutNativeFilters,
  dashboardInfo: {
    ...stateWithoutNativeFilters.dashboardInfo,
    metadata: {
      ...stateWithoutNativeFilters.dashboardInfo.metadata,
      native_filter_configuration: [year, org],
    },
  },
  dashboardLayout: {
    past: [],
    future: [],
    present: {
      'TAB-1': tab('TAB-1', 'Summary', ['ROOT_ID', 'TABS-1']),
      'TAB-2': tab('TAB-2', 'Child Health', [
        'ROOT_ID',
        'TABS-1',
        'TAB-1',
        'TABS-2',
      ]),
      'TAB-3': tab('TAB-3', 'Data Quality', ['ROOT_ID', 'TABS-1']),
      'TAB-4': tab('TAB-4', 'Multi Source', ['ROOT_ID', 'TABS-1']),
    },
  },
  dashboardState: {
    ...stateWithoutNativeFilters.dashboardState,
    editMode: false,
    activeTabs: ['TAB-1', 'TAB-2'],
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

const renderWithState = (ui: JSX.Element, initialState: object = state) => {
  const store = createStore(initialState, reducerIndex);
  render(ui, { store, useRedux: true, useRouter: true });
  return store;
};

test('chart chip shows the period and the user org unit for a chart both filters reach', async () => {
  renderWithState(<ChartContextChip chartId={99} />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [
          { ...year, chartsInScope: [99] },
          { ...org, chartsInScope: [99] },
        ],
      },
    },
  });
  await waitFor(() =>
    expect(screen.getByTestId('chart-context-chip')).toHaveTextContent(
      '2018 EFY | Oromia Region',
    ),
  );
});

test('chart chip shows the user org unit for a chart no org unit filter reaches', async () => {
  renderWithState(<ChartContextChip chartId={10} />);
  await waitFor(() =>
    expect(screen.getByTestId('chart-context-chip')).toHaveTextContent(
      '2018 EFY | Oromia Region',
    ),
  );
});

test('chart chip shows the latest period for a chart no filter reaches', async () => {
  renderWithState(<ChartContextChip chartId={500} />);
  await waitFor(() =>
    expect(screen.getByTestId('chart-context-chip')).toHaveTextContent(
      'Latest: 2019 EFY · Q1 · Nehase | Oromia Region',
    ),
  );
});

test('chart chip resolves the user org unit even when the org filter has no targets', async () => {
  renderWithState(<ChartContextChip chartId={11} />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [year, { ...org, targets: undefined }],
      },
    },
  });
  await waitFor(() =>
    expect(screen.getByTestId('chart-context-chip')).toHaveTextContent(
      'Oromia Region',
    ),
  );
  expect(screen.getByTestId('chart-context-chip')).not.toHaveTextContent(
    'Loading',
  );
});

test('chart chip renders nothing when the dashboard has no global filters', () => {
  renderWithState(<ChartContextChip chartId={10} />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [],
      },
    },
  });
  expect(screen.queryByTestId('chart-context-chip')).not.toBeInTheDocument();
});

test('chart chip ignores a stale filter left over in nativeFilters.filters from a previous dashboard', () => {
  // Regression: the chip used to read state.nativeFilters.filters directly,
  // which does not get cleared on every dashboard navigation the way
  // dashboardInfo.metadata does. A dashboard with genuinely no Period or Org
  // Unit filter (dashboardInfo.metadata says so) must never show one just
  // because an old filter object is still sitting in that other slice.
  renderWithState(<ChartContextChip chartId={10} />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [],
      },
    },
    nativeFilters: {
      filters: { year, org },
      filtersState: {},
    },
  });
  expect(screen.queryByTestId('chart-context-chip')).not.toBeInTheDocument();
});

test('strip shows the active tab path and the data update date', async () => {
  renderWithState(<DashboardContextStrip />);
  expect(screen.getByTestId('context-strip-title')).toHaveTextContent(
    'Summary · Child Health',
  );
  await waitFor(() =>
    expect(screen.getByTestId('data-as-of')).toHaveTextContent(
      'Data as of 20 Sep 2026',
    ),
  );
  expect(screen.getByText('Data Quality')).toBeInTheDocument();
  expect(screen.getAllByText('Not available')).toHaveLength(1);
});

test('strip shows Not available for a tab without an agreed data source', async () => {
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardState: { ...state.dashboardState, activeTabs: ['TAB-4'] },
  });
  await screen.findByTestId('context-strip-title');
  expect(screen.getByTestId('data-as-of')).toHaveTextContent(
    'Data as of Not available',
  );
});

test('strip marks the default view when filters hold their defaults', async () => {
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [{ ...year, chartsInScope: [10] }],
      },
    },
  });
  expect(await screen.findByTestId('default-view-chip')).toHaveTextContent(
    'Default view: 2018 EFY',
  );
});

test('strip turns into a custom view when a filter differs from its default', async () => {
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [{ ...year, chartsInScope: [10] }],
      },
    },
    dataMask: {
      year: {
        id: 'year',
        filterState: { value: ['2017'], label: '2017 EFY' },
        extraFormData: {},
      },
    },
  });
  expect(await screen.findByTestId('default-view-chip')).toHaveTextContent(
    'Custom view: 2017 EFY',
  );
});

test('strip links to the Data Quality tab', async () => {
  const store = renderWithState(<DashboardContextStrip />);
  userEvent.click(await screen.findByRole('button', { name: /View DQ/ }));
  expect(
    (store.getState() as unknown as RootState).dashboardState.directPathToChild,
  ).toEqual(['ROOT_ID', 'TABS-1', 'TAB-3']);
});

test('strip ignores a stale filter left over in nativeFilters.filters from a previous dashboard', async () => {
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [],
      },
    },
    nativeFilters: {
      filters: { year, org },
      filtersState: {},
    },
  });
  await screen.findByTestId('context-strip-title');
  expect(screen.queryByTestId('default-view-chip')).not.toBeInTheDocument();
});

test('strip is hidden while editing the dashboard', () => {
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardState: { ...state.dashboardState, editMode: true },
  });
  expect(
    screen.queryByTestId('dashboard-context-strip'),
  ).not.toBeInTheDocument();
});
