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
import { findPercentOverHundred } from './findPercentOverHundred';

const rows = (data: Record<string, unknown>[]) => [{ data }];

test('flags a coverage-titled chart whose neutral metric exceeds 100', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Full Immunization Coverage',
      formData: { metrics: ['Performance', 'Baseline'], x_axis: 'region' },
      queriesResponse: rows([
        { region: 'Oromia', Performance: 96.2, Baseline: 90 },
        { region: 'Amhara', Performance: 120.16, Baseline: 95 },
      ]),
    }),
  ).toBe(true);
});

test('stays quiet when every percentage is at or below 100', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Measles 1st Dose Coverage',
      formData: { metrics: ['Performance'] },
      queriesResponse: rows([{ Performance: 100 }, { Performance: 88.4 }]),
    }),
  ).toBe(false);
});

test('recognises a percentage metric on a neutrally titled chart', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Performance Trend',
      formData: {
        metrics: [
          {
            expressionType: 'SIMPLE',
            aggregate: 'AVG',
            column: { column_name: 'coverage' },
          },
        ],
        x_axis: 'period',
      },
      queriesResponse: rows([{ period: 201811, 'AVG(coverage)': 104.5 }]),
    }),
  ).toBe(true);
});

test('attributes pivoted group columns to the single metric', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Performance Comparison',
      formData: { metrics: ['AVG(coverage)'], groupby: ['region'] },
      queriesResponse: rows([{ __timestamp: 1, Oromia: 99, Afar: 131 }]),
    }),
  ).toBe(true);
});

test('ignores count columns on a coverage-titled chart', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'CBHI Coverage by region',
      formData: {
        metrics: ['Household Coverage', 'Renewal rate', 'Woredas with CBHI'],
        x_axis: 'region',
      },
      queriesResponse: rows([
        {
          region: 'Oromia',
          'Household Coverage': 81,
          'Renewal rate': 92,
          'Woredas with CBHI': 287,
        },
      ]),
    }),
  ).toBe(false);
});

test('never flags target achievement, which may legitimately exceed 100%', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'map with region',
      formData: { metric: 'MAX(target_achievement_pct)', groupby: ['region'] },
      queriesResponse: rows([
        { region: 'Oromia', 'MAX(target_achievement_pct)': 140 },
      ]),
    }),
  ).toBe(false);
});

test('ignores non-percentage charts and dimension values', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Health Facilities by Region',
      formData: { metrics: ['COUNT(*)'], x_axis: 'fiscal_year' },
      queriesResponse: rows([{ fiscal_year: 2018, 'COUNT(*)': 5400 }]),
    }),
  ).toBe(false);
  expect(
    findPercentOverHundred({
      sliceName: 'Full Immunization Coverage',
      formData: { metrics: ['Performance'], x_axis: 'fiscal_year' },
      queriesResponse: rows([{ fiscal_year: 2018, Performance: 76 }]),
    }),
  ).toBe(false);
});

test('reads numeric strings and the second query of mixed charts', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Cumulative ANC 4+ Coverage to Date(%)',
      formData: { metrics: ['Baseline'], metrics_b: ['Performance'] },
      queriesResponse: [
        { data: [{ Baseline: '80.1' }] },
        { data: [{ Performance: '101.7' }] },
      ],
    }),
  ).toBe(true);
});

test('skips map payloads and empty responses', () => {
  expect(
    findPercentOverHundred({
      sliceName: 'Coverage Map',
      formData: { metric: 'AVG(coverage)' },
      queriesResponse: [{ data: { features: [{ coverage: 150 }] } }, null],
    }),
  ).toBe(false);
  expect(
    findPercentOverHundred({
      sliceName: 'Coverage',
      formData: {},
      queriesResponse: undefined,
    }),
  ).toBe(false);
});
