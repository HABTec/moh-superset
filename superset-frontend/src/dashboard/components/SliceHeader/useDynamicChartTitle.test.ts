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
import type { DataMaskStateWithId } from '@superset-ui/core';
import { NativeFilterType } from '@superset-ui/core';
import { useDynamicChartTitle } from './useDynamicChartTitle';

const mockStore = configureStore([]);

const buildFilter = (id: string, name: string) => ({
  id,
  name,
  type: NativeFilterType.NativeFilter,
  filterType: 'filter_select',
  targets: [],
  scope: { rootPath: [], excluded: [] },
  controlValues: {},
  cascadeParentIds: [],
  defaultDataMask: {},
  description: '',
});

const buildWrapper = (filters: object, dataMask: DataMaskStateWithId) => {
  const store = mockStore({ nativeFilters: { filters }, dataMask });
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
  );
  const { result } = renderHook(() => useDynamicChartTitle('Malaria cases'), {
    wrapper,
  });
  expect(result.current).toBe('Malaria cases');
});

test('appends Indicator, Year, Quarter and Month selections in order', () => {
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
  const wrapper = buildWrapper(filters, dataMask);
  const { result } = renderHook(() => useDynamicChartTitle('Malaria cases'), {
    wrapper,
  });
  expect(result.current).toBe('Malaria cases — Plasmodium — 2024 — Q2 — June');
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
    ...buildDataMask('QTR', ['2']),
  };
  const wrapper = buildWrapper(filters, dataMask);
  const { result } = renderHook(() => useDynamicChartTitle('Malaria cases'), {
    wrapper,
  });
  expect(result.current).toBe('Malaria cases — Plasmodium — Q2');
});

test('matches filter names case-insensitively', () => {
  const filters = {
    A: buildFilter('A', 'select a Quarter here'),
    B: buildFilter('B', 'YEAR OF BIRTH'),
  };
  const dataMask = {
    ...buildDataMask('A', ['3']),
    ...buildDataMask('B', ['1990']),
  };
  const wrapper = buildWrapper(filters, dataMask);
  const { result } = renderHook(() => useDynamicChartTitle('Cohort'), {
    wrapper,
  });
  expect(result.current).toBe('Cohort — 1990 — Q3');
});

test('joins multiple selected values with commas', () => {
  const wrapper = buildWrapper(
    { IND: buildFilter('IND', 'Indicator') },
    buildDataMask('IND', ['Malaria', 'Measles']),
  );
  const { result } = renderHook(() => useDynamicChartTitle('Cases'), {
    wrapper,
  });
  expect(result.current).toBe('Cases — Malaria, Measles');
});

test('ignores filters with empty selections', () => {
  const wrapper = buildWrapper(
    { IND: buildFilter('IND', 'Indicator') },
    buildDataMask('IND', []),
  );
  const { result } = renderHook(() => useDynamicChartTitle('Cases'), {
    wrapper,
  });
  expect(result.current).toBe('Cases');
});
