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
import { DashboardLayout } from '../types';
import fitOverfullRows from './fitOverfullRows';

const item = (
  id: string,
  type: string,
  children: string[] = [],
  width?: number,
) => ({
  id,
  type,
  children,
  parents: [],
  meta: width === undefined ? {} : { width },
});

const layout = (items: ReturnType<typeof item>[]): DashboardLayout =>
  Object.fromEntries(items.map(i => [i.id, i])) as unknown as DashboardLayout;

const widthsOf = (
  result: ReturnType<typeof fitOverfullRows>,
  ids: string[],
  source: DashboardLayout,
) => ids.map(id => (result[id] ?? source[id]).meta.width);

test('leaves rows that fit untouched', () => {
  const source = layout([
    item('GRID', 'GRID', ['ROW-1']),
    item('ROW-1', 'ROW', ['CHART-a', 'CHART-b']),
    item('CHART-a', 'CHART', [], 4),
    item('CHART-b', 'CHART', [], 8),
  ]);
  expect(fitOverfullRows(source)).toEqual({});
});

test('scales an over-full row down to 12 columns, keeping proportions', () => {
  const source = layout([
    item('GRID', 'GRID', ['ROW-1']),
    item('ROW-1', 'ROW', ['CHART-a', 'CHART-b']),
    item('CHART-a', 'CHART', [], 4),
    item('CHART-b', 'CHART', [], 12),
  ]);
  const result = fitOverfullRows(source);
  expect(widthsOf(result, ['CHART-a', 'CHART-b'], source)).toEqual([3, 9]);
});

test('fits rows inside a column to the column width, after the column shrinks', () => {
  const source = layout([
    item('GRID', 'GRID', ['ROW-1']),
    item('ROW-1', 'ROW', ['COLUMN-1', 'CHART-c']),
    item('COLUMN-1', 'COLUMN', ['ROW-2'], 8),
    item('CHART-c', 'CHART', [], 8),
    item('ROW-2', 'ROW', ['CHART-a', 'CHART-b']),
    item('CHART-a', 'CHART', [], 4),
    item('CHART-b', 'CHART', [], 4),
  ]);
  const result = fitOverfullRows(source);
  expect(widthsOf(result, ['COLUMN-1', 'CHART-c'], source)).toEqual([6, 6]);
  expect(widthsOf(result, ['CHART-a', 'CHART-b'], source)).toEqual([3, 3]);
});

test('leaves a row alone when its children cannot fit even at minimum width', () => {
  const ids = Array.from({ length: 13 }, (_, i) => `CHART-${i}`);
  const source = layout([
    item('GRID', 'GRID', ['ROW-1']),
    item('ROW-1', 'ROW', ids),
    ...ids.map(id => item(id, 'CHART', [], 1)),
  ]);
  expect(fitOverfullRows(source)).toEqual({});
});
