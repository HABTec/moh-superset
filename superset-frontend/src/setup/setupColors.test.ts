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
  getCategoricalSchemeRegistry,
  getSequentialSchemeRegistry,
} from '@superset-ui/core';
import setupColors from './setupColors';

const categorical = {
  id: 'test_categorical',
  label: 'Test categorical',
  colors: ['#1E5CE0', '#7A2E7A'],
  colorsDark: ['#5B8DEF', '#B76BB7'],
};

const sequential = {
  id: 'test_ramp',
  label: 'Test ramp',
  colors: ['#E3ECFB', '#173F8A'],
  colorsDark: ['#1B2F55', '#C9DAF8'],
};

test('registers the light colours by default', () => {
  setupColors([categorical], [sequential]);

  expect(
    getCategoricalSchemeRegistry().get('test_categorical')?.colors,
  ).toEqual(['#1E5CE0', '#7A2E7A']);
  expect(getSequentialSchemeRegistry().get('test_ramp')?.colors).toEqual([
    '#E3ECFB',
    '#173F8A',
  ]);
});

test('registers colorsDark in dark mode, and back to light', () => {
  setupColors([categorical], [sequential], true);

  expect(
    getCategoricalSchemeRegistry().get('test_categorical')?.colors,
  ).toEqual(['#5B8DEF', '#B76BB7']);
  expect(getSequentialSchemeRegistry().get('test_ramp')?.colors).toEqual([
    '#1B2F55',
    '#C9DAF8',
  ]);

  setupColors([categorical], [sequential], false);

  expect(
    getCategoricalSchemeRegistry().get('test_categorical')?.colors,
  ).toEqual(['#1E5CE0', '#7A2E7A']);
});

test('keeps the light colours in dark mode when a scheme has no colorsDark', () => {
  const { colorsDark, ...lightOnly } = categorical;
  setupColors([lightOnly], [], true);

  expect(colorsDark).toHaveLength(2);
  expect(
    getCategoricalSchemeRegistry().get('test_categorical')?.colors,
  ).toEqual(['#1E5CE0', '#7A2E7A']);
});
