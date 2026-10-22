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
  getCascadeClearedValue,
  isEmptyFilterValue,
  shouldClearForParentChange,
} from './cascadeReset';

test('clears the child when the parent value changes', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: ['2018'] },
      parentValues: { year: ['2019'] },
      prevOwnValue: ['Q3'],
      ownValue: ['Q3'],
    }),
  ).toBe(true);
});

test('clears the child when the parent is cleared', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: ['2018'] },
      parentValues: { year: null },
      prevOwnValue: ['Q3'],
      ownValue: ['Q3'],
    }),
  ).toBe(true);
});

test('clears the grandchild when a non-direct ancestor changes', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: ['2018'], quarter: ['Q3'] },
      parentValues: { year: ['2019'], quarter: ['Q3'] },
      prevOwnValue: ['July'],
      ownValue: ['July'],
    }),
  ).toBe(true);
});

test('does not clear when the parent receives its first value', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: undefined },
      parentValues: { year: ['2018'] },
      prevOwnValue: ['Q3'],
      ownValue: ['Q3'],
    }),
  ).toBe(false);
});

test('does not clear when parent and child change together', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: ['2018'] },
      parentValues: { year: ['2019'] },
      prevOwnValue: ['Q3'],
      ownValue: ['Q1'],
    }),
  ).toBe(false);
});

test('does not clear when the child is already empty', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: ['2018'] },
      parentValues: { year: ['2019'] },
      prevOwnValue: null,
      ownValue: null,
    }),
  ).toBe(false);
});

test('does not clear when the parent value is unchanged', () => {
  expect(
    shouldClearForParentChange({
      prevParentValues: { year: ['2018'] },
      parentValues: { year: ['2018'] },
      prevOwnValue: ['Q3'],
      ownValue: ['Q3'],
    }),
  ).toBe(false);
});

test('treats null, empty arrays and empty ranges as empty', () => {
  expect(isEmptyFilterValue(undefined)).toBe(true);
  expect(isEmptyFilterValue(null)).toBe(true);
  expect(isEmptyFilterValue([])).toBe(true);
  expect(isEmptyFilterValue([null, null])).toBe(true);
  expect(isEmptyFilterValue(['Q3'])).toBe(false);
  expect(isEmptyFilterValue([0, null])).toBe(false);
});

test('range filters clear to an empty range, others to null', () => {
  expect(getCascadeClearedValue('filter_range')).toEqual([null, null]);
  expect(getCascadeClearedValue('filter_select')).toBeNull();
});
