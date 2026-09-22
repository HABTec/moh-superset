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
import { formatDataDate, getFreshnessSource } from './dataFreshness';

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

test('formats an update time for display', () => {
  expect(formatDataDate('2026-09-20T20:46:32')).toEqual({
    date: '20 Sep 2026',
    dateTime: '20 Sep 2026, 20:46',
  });
  expect(formatDataDate('not a date')).toBeNull();
});
