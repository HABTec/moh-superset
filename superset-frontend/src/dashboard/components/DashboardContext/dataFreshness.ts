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
export type FreshnessSource = 'routine' | 'quality';

/**
 * The data source a top-level tab reads. Tabs whose source has no agreed
 * update time (Multi Source, Triangulation, …) return null.
 */
export function getFreshnessSource(tabName?: string): FreshnessSource | null {
  const name = tabName ?? '';
  if (/data quality/i.test(name)) {
    return 'quality';
  }
  if (/summary|routine/i.test(name)) {
    return 'routine';
  }
  return null;
}

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

const twoDigits = (value: number) => String(value).padStart(2, '0');

/**
 * "20 Sep 2026" for display and "20 Sep 2026, 20:46" for the tooltip, formatted
 * the same in every browser.
 */
export function formatDataDate(isoTime: string): {
  date: string;
  dateTime: string;
} | null {
  const time = new Date(isoTime);
  if (Number.isNaN(time.getTime())) {
    return null;
  }
  const date = `${time.getDate()} ${MONTHS[time.getMonth()]} ${time.getFullYear()}`;
  return {
    date,
    dateTime: `${date}, ${twoDigits(time.getHours())}:${twoDigits(time.getMinutes())}`,
  };
}
