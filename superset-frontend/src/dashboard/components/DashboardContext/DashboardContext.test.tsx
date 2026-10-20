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
  waitFor,
} from 'spec/helpers/testing-library';
import reducerIndex from 'spec/helpers/reducerIndex';
import { stateWithoutNativeFilters } from 'spec/fixtures/mockStore';
import ChartContextChip from './ChartContextChip';
import DashboardContextStrip from './DashboardContextStrip';

const monthlyPeriod = {
  period: '201901',
  fiscalYear: '2019',
  quarter: 1,
  quarterName: 'Hamle to Meskerem (Q1)',
  monthName: 'Meskerem',
};
const quarterlyNativePeriod = {
  period: '2018NovQ4',
  fiscalYear: '2018',
  quarter: 4,
  quarterName: 'Miyaziya to Sene (Q4)',
  monthName: null,
};

fetchMock.get('glob:*/api/v1/moh/dhis2/data-freshness', {
  sources: {
    routine: { monthly: monthlyPeriod, quarterly: quarterlyNativePeriod },
    // Data Quality has no separately-collected quarterly data — both grains
    // read the same latest monthly period.
    quality: { monthly: monthlyPeriod, quarterly: monthlyPeriod },
  },
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

const chart = (id: string, chartId: number, tabParent: string) => ({
  id,
  type: 'CHART',
  children: [],
  parents: ['ROOT_ID', 'TABS-1', tabParent],
  meta: { chartId },
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
      'CHART-10': chart('CHART-10', 10, 'TAB-1'),
      'CHART-11': chart('CHART-11', 11, 'TAB-1'),
      'CHART-99': chart('CHART-99', 99, 'TAB-1'),
      // A chart on the Multi Source tab — outside the Period/Org Unit
      // filters' scope, same as the routine dashboards' "not available for
      // this source" case.
      'CHART-500': chart('CHART-500', 500, 'TAB-4'),
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

test('chart chip falls back to the user org unit for a chart under a known source', async () => {
  // Chart 10 lives under the "Summary" tab (CHART-10 -> TAB-1), a known
  // routine source, even though the Org Unit filter's own chartsInScope
  // excludes it — so the fallback still applies, same as it would for the
  // rest of that tab.
  renderWithState(<ChartContextChip chartId={10} />);
  await waitFor(() =>
    expect(screen.getByTestId('chart-context-chip')).toHaveTextContent(
      '2018 EFY | Oromia Region',
    ),
  );
});

test('chart chip renders nothing for a chart no filter reaches', async () => {
  // Regression: a chart whose source has no period/org unit dimension (e.g.
  // a Multi Source chart) used to show a fabricated "Latest: <routine
  // period>" chip that had nothing to do with that chart's actual data.
  renderWithState(<ChartContextChip chartId={500} />);
  await waitFor(() =>
    expect(screen.queryByTestId('chart-context-chip')).not.toBeInTheDocument(),
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

test('strip shows the active tab path and the latest period with data', async () => {
  renderWithState(<DashboardContextStrip />);
  expect(screen.getByTestId('context-strip-title')).toHaveTextContent(
    'Summary · Child Health',
  );
  await waitFor(() =>
    expect(screen.getByTestId('data-as-of')).toHaveTextContent(
      'Data as of 2019 EFY · Meskerem',
    ),
  );
});

test('strip reads the latest quarterly-native period on a Quarterly sub-tab', async () => {
  // Routine indicators genuinely have separate quarterly-collected data,
  // which can be older than the latest monthly period.
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardLayout: {
      ...state.dashboardLayout,
      present: {
        ...state.dashboardLayout.present,
        'TAB-1': tab('TAB-1', 'Routine Health Indicators', [
          'ROOT_ID',
          'TABS-1',
        ]),
        'TAB-2': tab('TAB-2', 'Quarterly', [
          'ROOT_ID',
          'TABS-1',
          'TAB-1',
          'TABS-2',
        ]),
      },
    },
  });
  await waitFor(() =>
    expect(screen.getByTestId('data-as-of')).toHaveTextContent(
      'Data as of 2018 EFY · Q4',
    ),
  );
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
  // Regression: Multi Source has no period or org unit dimension — the
  // "Default view: Latest ..." chip used to show anyway, borrowed from the
  // routine dashboards' Period filter, which does not apply to this tab.
  expect(screen.queryByTestId('default-view-chip')).not.toBeInTheDocument();
});

test('strip shows a real "data as of" period for Data Quality, not a fabricated load timestamp', async () => {
  // Regression: this used to read monthly_data_set_registration_status's
  // loaded_at column, an ETL bulk-load stamp that is identical across every
  // row in the table regardless of period — it always showed today's date.
  // "Data as of" now reads the latest period the table has real data for.
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardLayout: {
      ...state.dashboardLayout,
      present: {
        ...state.dashboardLayout.present,
        'TAB-4': tab('TAB-4', 'Data Quality', ['ROOT_ID', 'TABS-1']),
      },
    },
    dashboardState: { ...state.dashboardState, activeTabs: ['TAB-4'] },
  });
  await waitFor(() =>
    expect(screen.getByTestId('data-as-of')).toHaveTextContent(
      'Data as of 2019 EFY · Meskerem',
    ),
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

test('strip restores the default view on Summary, which no filter is scoped to reach', async () => {
  // Regression: on the real dashboard, no Period or Org Unit filter's scope
  // includes the Summary tab at all — it's deliberately left out so Summary
  // always shows the latest period and the user's own area, the same as a
  // chart excluded from a filter's chartsInScope. The chip used to disappear
  // there entirely, indistinguishable from Multi Source, until the tab's
  // known source (getFreshnessSource) restored the fallback specifically
  // for tabs built on routine/quality data.
  renderWithState(<DashboardContextStrip />, {
    ...state,
    dashboardInfo: {
      ...state.dashboardInfo,
      metadata: {
        ...state.dashboardInfo.metadata,
        native_filter_configuration: [
          {
            ...year,
            scope: { rootPath: ['TAB-3'], excluded: [] },
            chartsInScope: [],
          },
          {
            ...org,
            scope: { rootPath: ['TAB-3'], excluded: [] },
            chartsInScope: [],
          },
        ],
      },
    },
  });
  expect(await screen.findByTestId('default-view-chip')).toHaveTextContent(
    'Default view: Latest: 2019 EFY · Q1 · Nehase · Oromia Region',
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
