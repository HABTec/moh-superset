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
  isResponsiveDashboardEnabled,
  isResponsiveDashboardOptedOut,
} from './responsiveDashboard';

test('is on by default for any dashboard id', () => {
  [1, 3, 8, 10, 14, 987].forEach(id => {
    expect(isResponsiveDashboardEnabled({ id })).toBe(true);
    expect(isResponsiveDashboardEnabled({ id, metadata: {} })).toBe(true);
  });
});

test('is off only when the dashboard explicitly opts out', () => {
  const info = { id: 8, metadata: { responsive_dashboard_disabled: true } };
  expect(isResponsiveDashboardOptedOut(info)).toBe(true);
  expect(isResponsiveDashboardEnabled(info)).toBe(false);
});

test('old opt-in keys stay valid and change nothing', () => {
  const info = { id: 12, metadata: { responsive_mobile_enabled: true } };
  expect(isResponsiveDashboardEnabled(info)).toBe(true);
  expect(isResponsiveDashboardOptedOut(info)).toBe(false);
});

test('is off when no dashboard is loaded', () => {
  expect(isResponsiveDashboardEnabled(undefined)).toBe(false);
});
