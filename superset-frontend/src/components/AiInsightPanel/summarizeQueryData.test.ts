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

test('parses numeric strings into numeric stats (clickhouse metrics)', () => {
  const query = baseQuery({
    rowcount: 56,
    colnames: ['region', 'disease', 'AVG(deaths)', 'rank'],
    data: [
      {
        region: 'Amhara',
        disease: 'Cholera',
        'AVG(deaths)': '55.0',
        rank: '1.0',
      },
      {
        region: 'Oromia',
        disease: 'Malaria',
        'AVG(deaths)': '12.0',
        rank: '2.0',
      },
    ],
  });
  const summary = summarizeQueryData([query]);
  expect(summary?.numericStats).toContainEqual(
    expect.objectContaining({
      column: 'AVG(deaths)',
      min: 12,
      max: 55,
      avg: 33.5,
      count: 2,
    }),
  );
});

test('ignores structural columns and oversized strings in top values (deckgl)', () => {
  const geometry = `{"type":"Polygon","coordinates":["${'x'.repeat(2000)}"]}`;
  const query = baseQuery({
    rowcount: 4,
    colnames: ['geometry_geojson', 'region', 'target_achievement_pct'],
    data: [
      {
        geometry_geojson: geometry,
        region: 'Oromia',
        target_achievement_pct: 40,
      },
      {
        geometry_geojson: geometry,
        region: 'Oromia',
        target_achievement_pct: 55,
      },
      {
        geometry_geojson: geometry,
        region: 'Amhara',
        target_achievement_pct: null,
      },
      {
        geometry_geojson: geometry,
        region: 'Amhara',
        target_achievement_pct: null,
      },
    ],
  });
  const summary = summarizeQueryData([query]);
  const topColumns = summary?.topValues.map(top => top.column) ?? [];
  expect(topColumns).not.toContain('geometry_geojson');
  expect(topColumns).toContain('region');
  for (const top of summary?.topValues ?? []) {
    for (const { value } of top.values) {
      expect(typeof value).toBe('string');
      expect(value.length).toBeLessThanOrEqual(120);
    }
  }
});

test('strips structural columns and caps long strings in sample rows', () => {
  const geometry = `{"coordinates":["${'y'.repeat(5000)}"]}`;
  const query = baseQuery({
    rowcount: 1,
    colnames: ['geometry_geojson', 'region', 'notes'],
    data: [
      { geometry_geojson: geometry, region: 'Oromia', notes: 'n'.repeat(5000) },
    ],
  });
  const summary = summarizeQueryData([query]);
  expect(summary?.sampleRows).toHaveLength(1);
  const row = summary?.sampleRows[0];
  expect(row).not.toHaveProperty('geometry_geojson');
  expect(row?.region).toBe('Oromia');
  expect((row?.notes as string | undefined)?.length ?? 0).toBeLessThanOrEqual(
    201,
  );
});
