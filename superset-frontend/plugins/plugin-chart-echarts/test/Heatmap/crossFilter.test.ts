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
import { ChartProps } from '@superset-ui/core';
import { supersetTheme } from '@apache-superset/core/theme';
import { GenericDataType } from '@apache-superset/core/common';
import { HeatmapChartProps, HeatmapFormData } from '../../src/Heatmap/types';
import transformProps from '../../src/Heatmap/transformProps';
import {
  getHeatmapCrossFilterDataMask,
  getSelectedCells,
  HeatmapCell,
  isCellInSelection,
  toggleCell,
} from '../../src/Heatmap/crossFilter';

const highlandsKiremt: HeatmapCell = ['Kiremt', 'Highlands'];
const westernTsedey: HeatmapCell = ['Tsedey', 'Western lowlands'];

test('a plain click selects only the clicked cell', () => {
  expect(toggleCell([westernTsedey], highlandsKiremt, false)).toEqual([
    highlandsKiremt,
  ]);
});

test('a plain click on the only selected cell clears the selection', () => {
  expect(toggleCell([highlandsKiremt], highlandsKiremt, false)).toEqual([]);
});

test('an additive click adds a cell, and removes it when selected', () => {
  const both = toggleCell([highlandsKiremt], westernTsedey, true);
  expect(both).toEqual([highlandsKiremt, westernTsedey]);
  expect(toggleCell(both, highlandsKiremt, true)).toEqual([westernTsedey]);
});

test('the data mask filters both axis columns', () => {
  expect(
    getHeatmapCrossFilterDataMask({
      cells: [highlandsKiremt, westernTsedey],
      xAxis: 'season',
      yAxis: 'climate_region',
    }),
  ).toEqual({
    extraFormData: {
      filters: [
        { col: 'season', op: 'IN', val: ['Kiremt', 'Tsedey'] },
        {
          col: 'climate_region',
          op: 'IN',
          val: ['Highlands', 'Western lowlands'],
        },
      ],
    },
    filterState: {
      value: [highlandsKiremt, westernTsedey],
      label: 'Highlands × Kiremt, Western lowlands × Tsedey',
    },
  });
});

test('an empty selection clears the cross-filter', () => {
  expect(
    getHeatmapCrossFilterDataMask({
      cells: [],
      xAxis: 'season',
      yAxis: 'climate_region',
    }),
  ).toEqual({
    extraFormData: { filters: [] },
    filterState: { value: null, label: undefined },
  });
});

test('selection covers every row and column combination it filters on', () => {
  const selected = [highlandsKiremt, westernTsedey];
  expect(isCellInSelection(selected, 'Kiremt', 'Western lowlands')).toBe(true);
  expect(isCellInSelection(selected, 'Kiremt', 'Eastern lowlands')).toBe(false);
});

test('selected cells are read back from the filter state', () => {
  expect(getSelectedCells({ value: [highlandsKiremt] })).toEqual([
    highlandsKiremt,
  ]);
  expect(getSelectedCells({ value: null })).toEqual([]);
  expect(getSelectedCells(undefined)).toEqual([]);
});

const formData = {
  datasource: '5__table',
  viz_type: 'heatmap',
  xAxis: 'season',
  groupby: ['climate_region'],
  metric: 'risk',
  linearColorScheme: 'blue_white_yellow',
  normalized: false,
  normalizeAcross: 'heatmap',
  borderColor: { r: 255, g: 255, b: 255, a: 1 },
  borderWidth: 1,
  legendType: 'continuous',
  bottomMargin: 'auto',
  leftMargin: 'auto',
  xscaleInterval: 1,
  yscaleInterval: 1,
  xAxisLabelRotation: 0,
  valueBounds: [null, null],
} as HeatmapFormData;

const data = [
  { season: 'Kiremt', climate_region: 'Highlands', risk: 0.3 },
  { season: 'Tsedey', climate_region: 'Highlands', risk: 0.5 },
  { season: 'Kiremt', climate_region: 'Western lowlands', risk: 0.6 },
];

const createProps = (
  overrides: Record<string, unknown> = {},
  coltypes = [GenericDataType.String, GenericDataType.String],
) =>
  new ChartProps({
    formData,
    width: 800,
    height: 600,
    queriesData: [
      {
        data,
        colnames: ['season', 'climate_region', 'risk'],
        coltypes: [...coltypes, GenericDataType.Numeric],
      },
    ],
    theme: supersetTheme,
    ...overrides,
  }) as HeatmapChartProps;

test('clicking a cell emits a cross-filter on both axes', () => {
  const setDataMask = jest.fn();
  const { onCellClick, echartOptions } = transformProps(
    createProps({ emitCrossFilters: true, hooks: { setDataMask } }),
  );
  const { xAxis, yAxis } = echartOptions as {
    xAxis: { data: string[] };
    yAxis: { data: string[] };
  };

  onCellClick?.(
    xAxis.data.indexOf('Kiremt'),
    yAxis.data.indexOf('Highlands'),
    false,
  );

  expect(setDataMask).toHaveBeenCalledWith(
    expect.objectContaining({
      extraFormData: {
        filters: [
          { col: 'season', op: 'IN', val: ['Kiremt'] },
          { col: 'climate_region', op: 'IN', val: ['Highlands'] },
        ],
      },
    }),
  );
});

test('cells outside the selection are faded', () => {
  const { echartOptions } = transformProps(
    createProps({
      emitCrossFilters: true,
      hooks: { setDataMask: jest.fn() },
      filterState: { value: [highlandsKiremt] },
    }),
  );
  const [series] = (echartOptions as { series: { data: unknown[] }[] }).series;

  const faded = series.data.filter(
    item => !Array.isArray(item) && typeof item === 'object',
  );
  expect(series.data).toHaveLength(3);
  expect(faded).toHaveLength(2);
});

test('no click handler without cross-filtering or with a time axis', () => {
  expect(transformProps(createProps()).onCellClick).toBeUndefined();
  expect(
    transformProps(
      createProps(
        { emitCrossFilters: true, hooks: { setDataMask: jest.fn() } },
        [GenericDataType.Temporal, GenericDataType.String],
      ),
    ).onCellClick,
  ).toBeUndefined();
});
