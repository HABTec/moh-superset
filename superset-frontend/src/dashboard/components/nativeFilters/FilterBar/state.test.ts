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
import { act, renderHook } from '@testing-library/react';
import { Filter } from '@superset-ui/core';
import { useInitialization } from 'src/dashboard/components/nativeFilters/FilterBar/state';
import { useSelector } from 'react-redux';

jest.mock('react-redux', () => ({
  ...jest.requireActual('react-redux'),
  useSelector: jest.fn(),
}));

const mockedUseSelector = useSelector as unknown as jest.Mock;

const NATIVE_FILTER = {
  id: 'NATIVE_FILTER-a',
  name: 'Region',
  filterType: 'NATIVE_FILTER',
} as unknown as Filter;

/**
 * Run the real selectors against a minimal state. The dashboard's
 * `native_filter_configuration` is the input `useFilters` ultimately reads, so
 * this exercises the same path the component uses.
 */
const mockState = () => {
  const state = {
    dashboardInfo: {
      metadata: { native_filter_configuration: [NATIVE_FILTER] },
    },
    dashboardState: { preselectNativeFilters: {} },
    charts: {},
  };
  mockedUseSelector.mockImplementation(selector => selector(state));
};

const addChartAnchors = (count: number) => {
  document.body.innerHTML = Array.from({ length: count })
    .map(() => '<div data-ui-anchor="chart"></div>')
    .join('');
};

beforeEach(() => {
  jest.useFakeTimers();
  mockState();
  addChartAnchors(0);
});

afterEach(() => {
  jest.useRealTimers();
  document.body.innerHTML = '';
  jest.clearAllMocks();
});

test('waits for charts by default, preserving dashboard behaviour', () => {
  addChartAnchors(1);
  const { result } = renderHook(() => useInitialization());

  expect(result.current).toBe(false);
});

test('initializes immediately when the caller opts out of waiting', () => {
  addChartAnchors(3);
  const { result } = renderHook(() => useInitialization(false));

  expect(result.current).toBe(true);
});

test('opting out needs no chart anchors at all', () => {
  const { result } = renderHook(() => useInitialization(false));

  expect(result.current).toBe(true);

  // Nothing was scheduled, so advancing time changes nothing.
  act(() => {
    jest.advanceTimersByTime(2000);
  });
  expect(result.current).toBe(true);
});

test('still waits a second when opted out is false and no charts are present', () => {
  const { result } = renderHook(() => useInitialization());

  expect(result.current).toBe(false);
  act(() => {
    jest.advanceTimersByTime(1000);
  });
  expect(result.current).toBe(true);
});
