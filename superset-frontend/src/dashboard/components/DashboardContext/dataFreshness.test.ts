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
import {
  formatFreshnessPeriod,
  getFreshnessGrain,
  getFreshnessSource,
} from './dataFreshness';

test('maps top-level tabs to the data source they read', () => {
  expect(getFreshnessSource('Summary')).toBe('routine');
  expect(getFreshnessSource('Routine Health Indicators')).toBe('routine');
  expect(getFreshnessSource('Data Quality')).toBe('quality');
});

test('leaves tabs without an agreed source unmapped', () => {
  expect(getFreshnessSource('Multi Source')).toBeNull();
  expect(getFreshnessSource('Triangulation')).toBeNull();
  expect(getFreshnessSource(undefined)).toBeNull();
});

test('reads the grain from a Quarterly sub-tab in the path', () => {
  expect(getFreshnessGrain(['Data Quality', 'Quarterly'])).toBe('quarterly');
  expect(getFreshnessGrain(['Routine Health Indicators', 'Quarterly'])).toBe(
    'quarterly',
  );
});

test('defaults to monthly when the path names neither grain', () => {
  expect(getFreshnessGrain(['Data Quality', 'Monthly'])).toBe('monthly');
  expect(getFreshnessGrain(['Summary'])).toBe('monthly');
  expect(getFreshnessGrain([])).toBe('monthly');
});

const period = {
  period: '201901',
  fiscalYear: '2019',
  quarter: 1,
  quarterName: 'Hamle to Meskerem (Q1)',
  monthName: 'Meskerem',
};

test('formats a monthly period as fiscal year and month', () => {
  expect(formatFreshnessPeriod(period, 'monthly')).toBe('2019 EFY · Meskerem');
});

test('formats a quarterly period as fiscal year and quarter number', () => {
  expect(formatFreshnessPeriod(period, 'quarterly')).toBe('2019 EFY · Q1');
});

test('is null when there is no period, or the grain has no matching field', () => {
  expect(formatFreshnessPeriod(null, 'monthly')).toBeNull();
  expect(formatFreshnessPeriod(undefined, 'quarterly')).toBeNull();
  expect(
    formatFreshnessPeriod({ ...period, monthName: null }, 'monthly'),
  ).toBeNull();
});
