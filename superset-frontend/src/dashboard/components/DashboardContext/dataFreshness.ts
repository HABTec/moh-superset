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
import { formatFilterOptionLabel } from 'src/filters/utils/filterDisplay';
import { FreshnessPeriod } from 'src/filters/components/OrgUnitTree/useDataFreshness';

export type FreshnessSource = 'routine' | 'quality';
export type FreshnessGrain = 'monthly' | 'quarterly';

export type { FreshnessPeriod };

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

/**
 * Which grain a tab's own path reads — from a "Quarterly" sub-tab, or
 * "Monthly" otherwise (also the default when the path names neither, since
 * that's how the Summary tab reads).
 */
export function getFreshnessGrain(
  tabTitles: (string | undefined)[],
): FreshnessGrain {
  const joined = tabTitles.filter(Boolean).join(' ').toLowerCase();
  return /quarter/.test(joined) ? 'quarterly' : 'monthly';
}

/**
 * "2019 EFY · Meskerem" for a monthly grain, "2019 EFY · Q1" for quarterly.
 * Null when the period, or the field that grain needs, is unknown.
 */
export function formatFreshnessPeriod(
  period: FreshnessPeriod | null | undefined,
  grain: FreshnessGrain,
): string | null {
  if (!period) {
    return null;
  }
  const fiscalYear = formatFilterOptionLabel(
    String(period.fiscalYear),
    'fiscal_year',
  );
  const grainPart =
    grain === 'quarterly'
      ? period.quarter
        ? `Q${period.quarter}`
        : null
      : period.monthName;
  if (!grainPart) {
    return null;
  }
  return [fiscalYear, grainPart].join(' · ');
}
