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
import { renderHook } from '@testing-library/react';
import { Provider } from 'react-redux';
import configureStore from 'redux-mock-store';
import { createElement } from 'react';
import type { ReactNode } from 'react';
import type { DataMaskStateWithId, NativeFilterScope } from '@superset-ui/core';
import { NativeFilterType } from '@superset-ui/core';
import { CHART_TYPE } from 'src/dashboard/util/componentTypes';
import { DASHBOARD_ROOT_ID } from 'src/dashboard/util/constants';
import { useDynamicChartTitle } from './useDynamicChartTitle';

const mockStore = configureStore([]);

const buildFilter = (
  id: string,
  name: string,
  defaultValue?: unknown,
  scope: NativeFilterScope = { rootPath: [DASHBOARD_ROOT_ID], excluded: [] },
) => ({
  id,
  name,
  type: NativeFilterType.NativeFilter,
  filterType: 'filter_select',
  targets: [],
  scope,
  controlValues: {},
  cascadeParentIds: [],
  defaultDataMask: { filterState: { value: defaultValue } },
  description: '',
});

const buildLayout = (
  chartId: number,
  parentIds: string[] = [DASHBOARD_ROOT_ID],
) => ({
  [DASHBOARD_ROOT_ID]: {
    id: DASHBOARD_ROOT_ID,
    type: 'ROOT',
    meta: {},
    parents: [],
  },
  [`${CHART_TYPE}-${chartId}`]: {
    id: `${CHART_TYPE}-${chartId}`,
    type: CHART_TYPE,
    meta: { chartId },
    parents: parentIds,
  },
});

const buildWrapper = (
  filters: object,
  dataMask: DataMaskStateWithId,
  layout?: object,
) => {
  const store = mockStore({
    nativeFilters: { filters },
    dataMask,
    dashboardLayout: { present: layout },
  });
  return ({ children }: { children: ReactNode }) =>
    createElement(Provider, { store }, children);
};

const buildDataMask = (filterId: string, value: unknown) => ({
  [filterId]: {
    id: filterId,
    filterState: { value },
  },
});

test('returns the base title when there are no matching filters', () => {
  const wrapper = buildWrapper(
    {
      F1: buildFilter('F1', 'Region'),
      F2: buildFilter('F2', 'Disease'),
    },
    buildDataMask('F1', ['Oromia']),
    buildLayout(1),
  );
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases');
});

test('appends Indicator and Year selections in order', () => {
  const filters = {
    IND: buildFilter('IND', 'Indicator'),
    YR: buildFilter('YR', 'Year'),
    QTR: buildFilter('QTR', 'Quarter'),
    MON: buildFilter('MON', 'Month'),
    ORG: buildFilter('ORG', 'Region'),
  };
  const dataMask = {
    ...buildDataMask('IND', ['Plasmodium']),
    ...buildDataMask('YR', ['2024']),
    ...buildDataMask('QTR', ['2']),
    ...buildDataMask('MON', ['June']),
    ...buildDataMask('ORG', ['Ethiopia']),
  };
  const wrapper = buildWrapper(filters, dataMask, buildLayout(1));
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases — Plasmodium — 2024');
});

test('skips filters that have no selection', () => {
  const filters = {
    IND: buildFilter('IND', 'Indicator'),
    YR: buildFilter('YR', 'Year'),
    QTR: buildFilter('QTR', 'Quarter'),
    MON: buildFilter('MON', 'Month'),
  };
  const dataMask = {
    ...buildDataMask('IND', ['Plasmodium']),
  };
  const wrapper = buildWrapper(filters, dataMask, buildLayout(1));
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases — Plasmodium');
});

test('matches filter names case-insensitively', () => {
  const filters = {
    A: buildFilter('A', 'select an Indicator here'),
    B: buildFilter('B', 'YEAR OF BIRTH'),
  };
  const dataMask = {
    ...buildDataMask('A', ['Malaria']),
    ...buildDataMask('B', ['1990']),
  };
  const wrapper = buildWrapper(filters, dataMask, buildLayout(1));
  const { result } = renderHook(() => useDynamicChartTitle(1, 'Cohort'), {
    wrapper,
  });
  expect(result.current).toBe('Cohort — Malaria — 1990');
});

test('joins multiple selected values with commas', () => {
  const wrapper = buildWrapper(
    { IND: buildFilter('IND', 'Indicator') },
    buildDataMask('IND', ['Malaria', 'Measles']),
    buildLayout(1),
  );
  const { result } = renderHook(() => useDynamicChartTitle(1, 'Cases'), {
    wrapper,
  });
  expect(result.current).toBe('Cases — Malaria, Measles');
});

test('ignores filters with empty selections', () => {
  const wrapper = buildWrapper(
    { IND: buildFilter('IND', 'Indicator') },
    buildDataMask('IND', []),
    buildLayout(1),
  );
  const { result } = renderHook(() => useDynamicChartTitle(1, 'Cases'), {
    wrapper,
  });
  expect(result.current).toBe('Cases');
});

test('skips values that only match the filter default', () => {
  const filters = {
    IND: buildFilter('IND', 'Indicator', ['Plasmodium']),
    YR: buildFilter('YR', 'Year'),
    MON: buildFilter('MON', 'Month', ['June']),
  };
  const dataMask = {
    ...buildDataMask('IND', ['Plasmodium']),
    ...buildDataMask('MON', ['June']),
  };
  const wrapper = buildWrapper(filters, dataMask, buildLayout(1));
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases');
});

test('includes a value once it differs from the filter default', () => {
  const filters = {
    IND: buildFilter('IND', 'Indicator', ['Plasmodium']),
    YR: buildFilter('YR', 'Year', ['2024']),
  };
  const dataMask = {
    ...buildDataMask('IND', ['Malaria']),
    ...buildDataMask('YR', ['2025']),
  };
  const wrapper = buildWrapper(filters, dataMask, buildLayout(1));
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases — Malaria — 2025');
});

test('skips defaults while still appending actively changed filters', () => {
  const filters = {
    IND: buildFilter('IND', 'Indicator', ['Plasmodium']),
    YR: buildFilter('YR', 'Year', ['2024']),
    QTR: buildFilter('QTR', 'Quarter'),
    MON: buildFilter('MON', 'Month', ['June']),
  };
  const dataMask = {
    ...buildDataMask('IND', ['Plasmodium']),
    ...buildDataMask('YR', ['2025']),
    ...buildDataMask('MON', ['June']),
  };
  const wrapper = buildWrapper(filters, dataMask, buildLayout(1));
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases — 2025');
});

test('only appends filters whose scope includes the chart', () => {
  const tabAScope = { rootPath: ['TAB_A'], excluded: [] };
  const tabBScope = { rootPath: ['TAB_B'], excluded: [] };
  const filters = {
    IND: buildFilter('IND', 'Indicator', undefined, tabAScope),
    YR: buildFilter('YR', 'Year', undefined, tabBScope),
  };
  const dataMask = {
    ...buildDataMask('IND', ['Plasmodium']),
    ...buildDataMask('YR', ['2024']),
  };
  const layout = {
    ...buildLayout(1, ['TAB_A', DASHBOARD_ROOT_ID]),
    ...buildLayout(2, ['TAB_B', DASHBOARD_ROOT_ID]),
  };
  const wrapper = buildWrapper(filters, dataMask, layout);
  const { result: chartOne } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    { wrapper },
  );
  const { result: chartTwo } = renderHook(
    () => useDynamicChartTitle(2, 'Malaria cases'),
    { wrapper },
  );
  expect(chartOne.current).toBe('Malaria cases — Plasmodium');
  expect(chartTwo.current).toBe('Malaria cases — 2024');
});

test('ignores filters that explicitly exclude the chart', () => {
  const filters = {
    YR: buildFilter('YR', 'Year', undefined, {
      rootPath: [DASHBOARD_ROOT_ID],
      excluded: [1],
    }),
  };
  const wrapper = buildWrapper(
    filters,
    buildDataMask('YR', ['2024']),
    buildLayout(1),
  );
  const { result } = renderHook(
    () => useDynamicChartTitle(1, 'Malaria cases'),
    {
      wrapper,
    },
  );
  expect(result.current).toBe('Malaria cases');
});
