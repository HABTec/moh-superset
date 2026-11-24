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
// Charts are created through echarts/core, as the ECharts chart plugin does;
// in Jest the 'echarts' entry point is a separate prebuilt copy with its own
// instance registry.
import { init, use, type EChartsType } from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import { GridComponent, LegendComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import { hideLegendSelectorsForExport } from './hideLegendSelectorsForExport';

use([BarChart, PieChart, GridComponent, LegendComponent, SVGRenderer]);

const SELECTORS = [
  { type: 'all', title: 'Select all' },
  { type: 'inverse', title: 'Invert selection' },
];

const charts: EChartsType[] = [];

afterEach(() => {
  charts.splice(0).forEach(chart => chart.isDisposed() || chart.dispose());
  document.body.innerHTML = '';
});

function makeChart(
  parent: HTMLElement,
  legend: Record<string, unknown> | Record<string, unknown>[] = {
    selector: SELECTORS,
  },
  extra: Record<string, unknown> = {},
): { chart: EChartsType; node: HTMLElement } {
  const node = document.createElement('div');
  parent.appendChild(node);
  // SVG renders into the DOM, so the drawn legend text can be inspected.
  const chart = init(node, undefined, {
    renderer: 'svg',
    width: 600,
    height: 300,
  });
  chart.setOption({
    legend,
    xAxis: { type: 'category', data: ['Hamle', 'Nehase'] },
    yAxis: { type: 'value' },
    series: [
      { name: 'Baseline', type: 'bar', data: [40, 43] },
      { name: 'Performance', type: 'bar', data: [54, 56] },
    ],
    ...extra,
  });
  charts.push(chart);
  return { chart, node };
}

const drawnText = (node: HTMLElement) => node.textContent ?? '';
const selectorOf = (chart: EChartsType, index = 0) =>
  (chart.getOption().legend as Array<{ selector: unknown }>)[index].selector;

test('removes the buttons from the drawn chart and puts them back after', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { chart, node } = makeChart(root);
  expect(drawnText(node)).toContain('Select all');
  expect(drawnText(node)).toContain('Invert selection');

  const restore = hideLegendSelectorsForExport(root);

  expect(drawnText(node)).not.toContain('Select all');
  expect(drawnText(node)).not.toContain('Invert selection');
  // The legend itself and the data stay in the export.
  expect(drawnText(node)).toContain('Baseline');
  expect(drawnText(node)).toContain('Performance');

  restore();

  expect(drawnText(node)).toContain('Select all');
  expect(drawnText(node)).toContain('Invert selection');
  expect(selectorOf(chart)).toEqual(SELECTORS);
});

test('keeps series the user switched off hidden in the export', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { chart } = makeChart(root, {
    selector: SELECTORS,
    selected: { Baseline: false },
  });

  const restore = hideLegendSelectorsForExport(root);
  const during = chart.getOption().legend as Array<{
    selected: Record<string, boolean>;
  }>;
  restore();

  expect(during[0].selected.Baseline).toBe(false);
  expect(
    (
      chart.getOption().legend as Array<{ selected: Record<string, boolean> }>
    )[0].selected.Baseline,
  ).toBe(false);
});

test('only touches charts inside the exported element', () => {
  const exported = document.createElement('div');
  const other = document.createElement('div');
  document.body.append(exported, other);
  const inside = makeChart(exported);
  const outside = makeChart(other);

  const restore = hideLegendSelectorsForExport(exported);

  expect(drawnText(inside.node)).not.toContain('Select all');
  expect(drawnText(outside.node)).toContain('Select all');
  restore();
});

test('handles a whole dashboard with several charts', () => {
  const dashboard = document.createElement('div');
  document.body.appendChild(dashboard);
  const made = [
    makeChart(dashboard),
    makeChart(dashboard),
    makeChart(dashboard),
  ];

  const restore = hideLegendSelectorsForExport(dashboard);
  made.forEach(({ node }) =>
    expect(drawnText(node)).not.toContain('Select all'),
  );
  restore();
  made.forEach(({ node }) => expect(drawnText(node)).toContain('Select all'));
});

test('works when the exported element is the chart node itself', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { node } = makeChart(root);

  const restore = hideLegendSelectorsForExport(node);

  expect(drawnText(node)).not.toContain('Select all');
  restore();
  expect(drawnText(node)).toContain('Select all');
});

test('leaves charts without selectors untouched', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { chart } = makeChart(root, { selector: false });
  const setOption = jest.spyOn(chart, 'setOption');

  hideLegendSelectorsForExport(root)();

  expect(setOption).not.toHaveBeenCalled();
});

test('leaves charts without a legend untouched', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const node = document.createElement('div');
  root.appendChild(node);
  const chart = init(node, undefined, {
    renderer: 'svg',
    width: 300,
    height: 200,
  });
  charts.push(chart);
  chart.setOption({
    series: [{ type: 'pie', data: [{ name: 'A', value: 1 }] }],
  });
  const setOption = jest.spyOn(chart, 'setOption');

  hideLegendSelectorsForExport(root)();

  expect(setOption).not.toHaveBeenCalled();
});

test('handles several legends on one chart', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { chart, node } = makeChart(root, [
    { selector: SELECTORS, top: 0 },
    { selector: false, bottom: 0 },
  ]);

  const restore = hideLegendSelectorsForExport(root);
  expect(drawnText(node)).not.toContain('Select all');
  restore();

  expect(selectorOf(chart, 0)).toEqual(SELECTORS);
  expect(selectorOf(chart, 1)).toBe(false);
});

test('redraws without animation and restores the animation setting', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { chart } = makeChart(
    root,
    { selector: SELECTORS },
    { animation: true },
  );
  const setOption = jest.spyOn(chart, 'setOption');

  const restore = hideLegendSelectorsForExport(root);
  expect(setOption.mock.calls[0][0]).toMatchObject({ animation: false });
  restore();

  expect(chart.getOption().animation).toBe(true);
});

test('restoring after the chart was disposed does not throw', () => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const { chart } = makeChart(root);

  const restore = hideLegendSelectorsForExport(root);
  chart.dispose();

  expect(() => restore()).not.toThrow();
});

test('an element with no charts is a no-op', () => {
  const root = document.createElement('div');
  root.innerHTML = '<p>table chart</p>';

  expect(() => hideLegendSelectorsForExport(root)()).not.toThrow();
});
