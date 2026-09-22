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
import type { QueryData } from '@superset-ui/core';
import { summarizeQueryData } from './summarizeQueryData';

const baseQuery = (overrides: Partial<QueryData>): QueryData => ({
  rowcount: 2,
  colnames: ['period', 'visits', 'region'],
  data: [],
  ...overrides,
});

test('returns null when queriesResponse is null or empty', () => {
  expect(summarizeQueryData(null)).toBeNull();
  expect(summarizeQueryData(undefined)).toBeNull();
  expect(summarizeQueryData([])).toBeNull();
  expect(summarizeQueryData([{} as QueryData])).toBeNull();
});

test('returns null when the response has no rows', () => {
  expect(
    summarizeQueryData([
      baseQuery({ rowcount: 0, colnames: ['period', 'visits'], data: [] }),
    ]),
  ).toBeNull();
});

test('computes numeric stats and columns', () => {
  const query = baseQuery({
    rowcount: 3,
    colnames: ['period', 'visits'],
    data: [
      { period: '2025-01', visits: 10 },
      { period: '2025-02', visits: 20 },
      { period: '2025-03', visits: 30 },
    ],
  });
  const summary = summarizeQueryData([query]);
  expect(summary?.rowCount).toBe(3);
  expect(summary?.columns).toEqual(['period', 'visits']);
  expect(summary?.numericStats).toEqual([
    expect.objectContaining({ column: 'visits', min: 10, max: 30, avg: 20 }),
  ]);
});

test('detects an increasing trend across a date-like column', () => {
  const query = baseQuery({
    rowcount: 4,
    colnames: ['period', 'visits'],
    data: [
      { period: '2025-01', visits: 10 },
      { period: '2025-02', visits: 20 },
      { period: '2025-03', visits: 30 },
      { period: '2025-04', visits: 40 },
    ],
  });
  const summary = summarizeQueryData([query]);
  expect(summary?.trend).toEqual(
    expect.objectContaining({
      column: 'visits',
      direction: 'increasing',
      start: 10,
      end: 40,
    }),
  );
});

test('builds top values for categorical columns', () => {
  const query = baseQuery({
    rowcount: 4,
    colnames: ['region', 'visits'],
    data: [
      { region: 'AA', visits: 1 },
      { region: 'AA', visits: 2 },
      { region: 'BB', visits: 3 },
      { region: 'AA', visits: 4 },
    ],
  });
  const summary = summarizeQueryData([query]);
  expect(summary?.topValues[0]).toEqual({
    column: 'region',
    values: [
      { value: 'AA', count: 3 },
      { value: 'BB', count: 1 },
    ],
    total: 4,
  });
});

test('caps sample rows at five', () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ i: index }));
  const query = baseQuery({
    rowcount: 12,
    colnames: ['i'],
    data: rows,
  });
  const summary = summarizeQueryData([query]);
  expect(summary?.sampleRows).toHaveLength(5);
});