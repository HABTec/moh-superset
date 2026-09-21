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
  formatFilterOptionLabel,
  getEmptyFilterPlaceholder,
} from './filterDisplay';

test('shows No data when there are no options', () => {
  expect(getEmptyFilterPlaceholder({ optionCount: 0 })).toEqual('No data');
});

test('shows a custom empty label when there are no options', () => {
  expect(
    getEmptyFilterPlaceholder({
      optionCount: 0,
      noDataLabel: 'No time columns',
    }),
  ).toEqual('No time columns');
});

test('shows Select... when the filter is required', () => {
  expect(
    getEmptyFilterPlaceholder({
      optionCount: 12,
      enableEmptyFilter: true,
    }),
  ).toEqual('Select...');
});

test('shows All when the filter is optional', () => {
  expect(
    getEmptyFilterPlaceholder({
      optionCount: 12,
      enableEmptyFilter: false,
      filterName: 'Month',
    }),
  ).toEqual('All');
});

test('shows All applicable for indicator filters', () => {
  expect(
    getEmptyFilterPlaceholder({
      optionCount: 40,
      filterName: 'Indicator',
    }),
  ).toEqual('All applicable');
});

test('appends EFY to four-digit fiscal years', () => {
  expect(formatFilterOptionLabel('2018', 'fiscal_year')).toEqual('2018 EFY');
});

test('does not append EFY to calendar or survey years', () => {
  expect(formatFilterOptionLabel('2018', 'year')).toEqual('2018');
  expect(formatFilterOptionLabel('2018', 'survey_year')).toEqual('2018');
  expect(formatFilterOptionLabel('Q1', 'fiscal_year')).toEqual('Q1');
});
