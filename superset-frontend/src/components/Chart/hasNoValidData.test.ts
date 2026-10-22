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
import hasNoValidData from './hasNoValidData';

const avgRisk = {
  expressionType: 'SIMPLE',
  aggregate: 'AVG',
  column: { column_name: 'risk_index_final' },
  label: 'Risk Index',
};

test('a Big Number whose aggregate is NULL has no valid data', () => {
  expect(
    hasNoValidData([{ data: [{ 'Risk Index': null }] }], { metric: avgRisk }),
  ).toBe(true);
});

test('a Big Number of zero is a real result', () => {
  expect(
    hasNoValidData([{ data: [{ 'COUNT(*)': 0 }] }], { metric: 'COUNT(*)' }),
  ).toBe(false);
});

test('a zero count on a NULL category has no valid data', () => {
  expect(
    hasNoValidData(
      [{ data: [{ risk_category: null, 'COUNT(risk_category)': 0 }] }],
      { metric: 'COUNT(risk_category)', groupby: ['risk_category'] },
    ),
  ).toBe(true);
});

test('a zero count on a named category is a real result', () => {
  expect(
    hasNoValidData([{ data: [{ risk_category: 'High', 'COUNT(*)': 0 }] }], {
      metric: 'COUNT(*)',
    }),
  ).toBe(false);
});

test('bars whose measures are all NULL have no valid data', () => {
  expect(
    hasNoValidData(
      [
        {
          data: [
            { woreda: 'Abaya', 'Risk Index': null },
            { woreda: 'Adami Tulu', 'Risk Index': null },
          ],
        },
      ],
      { metrics: [avgRisk] },
    ),
  ).toBe(true);
});

test('one real measure among NULLs is valid data', () => {
  expect(
    hasNoValidData(
      [
        {
          data: [
            { woreda: 'Abaya', 'Risk Index': null },
            { woreda: 'Adami Tulu', 'Risk Index': 0.42 },
          ],
        },
      ],
      { metrics: [avgRisk] },
    ),
  ).toBe(false);
});

test('a map whose features all lack the metric has no valid data', () => {
  expect(
    hasNoValidData(
      [
        {
          data: {
            features: [
              { layer_type: 'region', 'Risk Index': null },
              { layer_type: 'woreda', 'Risk Index': null },
            ],
          },
        },
      ],
      { metric: avgRisk },
    ),
  ).toBe(true);
});

test('a map with one coloured feature is valid data', () => {
  expect(
    hasNoValidData(
      [
        {
          data: {
            features: [
              { layer_type: 'region', 'Risk Index': null },
              { layer_type: 'woreda', 'Risk Index': 61.5 },
            ],
          },
        },
      ],
      { metric: avgRisk },
    ),
  ).toBe(false);
});

test('a second query with a real value keeps the chart', () => {
  expect(
    hasNoValidData(
      [{ data: [{ 'SUM(cases)': null }] }, { data: [{ 'SUM(deaths)': 3 }] }],
      { metrics: ['SUM(cases)'], metrics_b: ['SUM(deaths)'] },
    ),
  ).toBe(false);
});

test('charts it cannot judge are left to draw themselves', () => {
  // no metrics (raw-records table)
  expect(hasNoValidData([{ data: [{ name: null }] }], {})).toBe(false);
  // measures renamed by post-processing (pivoted series)
  expect(
    hasNoValidData([{ data: [{ __timestamp: 1, 'SUM(x), A': null }] }], {
      metrics: ['SUM(x)'],
    }),
  ).toBe(false);
  // unknown payload shape
  expect(
    hasNoValidData([{ data: { records: [] } }], { metric: 'COUNT(*)' }),
  ).toBe(false);
});

test('queries with no rows are left to the built-in no-results state', () => {
  expect(hasNoValidData([{ data: [] }], { metric: 'COUNT(*)' })).toBe(false);
});
