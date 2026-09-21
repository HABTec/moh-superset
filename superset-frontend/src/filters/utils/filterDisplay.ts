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
import { t } from '@apache-superset/core/translation';

export type EmptyFilterPlaceholderArgs = {
  optionCount: number;
  enableEmptyFilter?: boolean;
  filterName?: string;
  columnName?: string;
  noDataLabel?: string;
};

function isIndicatorFilter(filterName?: string, columnName?: string): boolean {
  const haystack = `${filterName ?? ''} ${columnName ?? ''}`.toLowerCase();
  return haystack.includes('indicator');
}

/**
 * Closed-state copy for an empty native filter Select.
 * Required filters show "Select..."; optional filters show "All"
 * (or "All applicable" for indicator filters). Never "N options".
 */
export function getEmptyFilterPlaceholder({
  optionCount,
  enableEmptyFilter = false,
  filterName,
  columnName,
  noDataLabel,
}: EmptyFilterPlaceholderArgs): string {
  if (optionCount === 0) {
    return noDataLabel ?? t('No data');
  }
  if (enableEmptyFilter) {
    return t('Select...');
  }
  if (isIndicatorFilter(filterName, columnName)) {
    return t('All applicable');
  }
  return t('All');
}

const FISCAL_YEAR_COLUMNS = new Set(['fiscal_year']);

/**
 * Append the Ethiopian fiscal-year suffix when the column is a 4-digit year.
 */
export function formatFilterOptionLabel(
  label: string,
  columnName?: string,
): string {
  const col = (columnName ?? '').toLowerCase();
  if (FISCAL_YEAR_COLUMNS.has(col) && /^\d{4}$/.test(label)) {
    return `${label} EFY`;
  }
  return label;
}
