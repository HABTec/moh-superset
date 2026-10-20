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
import {
  DataMaskStateWithId,
  Divider,
  Filter,
  isFilterDivider,
  NativeFilterType,
} from '@superset-ui/core';

export type FilterBarSection = 'global' | 'local' | 'divider';

export type PeriodGrain = 'annual' | 'quarterly' | 'monthly';

export type PeriodFilterKind = 'year' | 'quarter' | 'month';

function normalizeName(name?: string): string {
  return (name ?? '').trim().toLowerCase();
}

export function isOrgUnitFilterName(name?: string): boolean {
  const n = normalizeName(name);
  return (
    n === 'org unit' || n === 'organisation unit' || n === 'organization unit'
  );
}

export function getFilterColumnName(filter: {
  targets?: { column?: { name?: string } }[];
}): string {
  return filter.targets?.[0]?.column?.name ?? '';
}

/**
 * DHIS2 programme period columns on moh_meged_data / quarterly_nov_periods.
 * Calendar `year` (vaccines) and `survey_year` (EDHS) are not this grain.
 */
export function getPeriodFilterKind(
  name?: string,
  columnName?: string,
): PeriodFilterKind | null {
  const col = normalizeName(columnName);
  if (col === 'fiscal_year') {
    return 'year';
  }
  if (col === 'quarter' || col === 'quarter_name') {
    return 'quarter';
  }
  if (
    col === 'month_name' ||
    col === 'month' ||
    col === 'fiscal_month_number'
  ) {
    return 'month';
  }
  if (col === 'year' || col === 'survey_year') {
    return null;
  }
  if (!col) {
    const n = normalizeName(name);
    if (n === 'year' || n === 'period' || n === 'fiscal year') {
      return 'year';
    }
    if (n === 'quarter') {
      return 'quarter';
    }
    if (n === 'month') {
      return 'month';
    }
  }
  return null;
}

export function getPeriodFilterKindFromFilter(
  filter: Filter | Divider,
): PeriodFilterKind | null {
  if (isFilterDivider(filter)) {
    return null;
  }
  return getPeriodFilterKind(filter.name, getFilterColumnName(filter));
}

export function getFilterBarSection(
  filter: Filter | Divider,
): FilterBarSection {
  if (isFilterDivider(filter)) {
    return 'divider';
  }
  if (
    getPeriodFilterKindFromFilter(filter) ||
    isOrgUnitFilterName(filter.name) ||
    filter.filterType === 'filter_org_unit_tree'
  ) {
    return 'global';
  }
  return 'local';
}

export function getFilterDisplayName(filter: {
  name?: string;
  title?: string;
  type?: string;
  filterType?: string;
  targets?: { column?: { name?: string } }[];
}): string {
  if (filter.type === NativeFilterType.Divider) {
    return filter.title ?? '';
  }
  const col = getFilterColumnName(filter);
  const kind = getPeriodFilterKind(filter.name, col);
  // The Period card supplies the "Period" heading; its year control is "Year".
  if (kind === 'year' && (col === 'fiscal_year' || !col)) {
    return t('Year');
  }
  if (
    isOrgUnitFilterName(filter.name) ||
    filter.filterType === 'filter_org_unit_tree'
  ) {
    return t('Organisation unit');
  }
  return filter.name ?? '';
}

function hasFilterValue(
  filter: Filter,
  dataMask: DataMaskStateWithId,
): boolean {
  const value = dataMask[filter.id]?.filterState?.value;
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return value != null && value !== '';
}

export function inferPeriodGrain(
  periodFilters: Filter[],
  dataMask: DataMaskStateWithId,
): PeriodGrain {
  const hasKindValue = (kind: PeriodFilterKind) =>
    periodFilters.some(
      filter =>
        getPeriodFilterKindFromFilter(filter) === kind &&
        hasFilterValue(filter, dataMask),
    );
  if (hasKindValue('month')) {
    return 'monthly';
  }
  if (hasKindValue('quarter')) {
    return 'quarterly';
  }
  const kinds = new Set(
    periodFilters.map(filter => getPeriodFilterKindFromFilter(filter)),
  );
  if (kinds.has('month')) {
    return 'monthly';
  }
  if (kinds.has('quarter')) {
    return 'quarterly';
  }
  return 'annual';
}

export function isPeriodFilterVisible(
  filter: Filter | Divider,
  grain: PeriodGrain,
): boolean {
  if (isFilterDivider(filter)) {
    return true;
  }
  const kind = getPeriodFilterKindFromFilter(filter);
  if (kind === 'quarter') {
    return grain === 'quarterly';
  }
  if (kind === 'month') {
    return grain === 'monthly';
  }
  return true;
}

export function shouldShowPeriodGrainControl(
  periodFilters: (Filter | Divider)[],
): boolean {
  const kinds = new Set(
    periodFilters
      .filter(filter => !isFilterDivider(filter))
      .map(filter => getPeriodFilterKindFromFilter(filter as Filter)),
  );
  return kinds.has('year') && (kinds.has('quarter') || kinds.has('month'));
}

const PERIOD_KIND_RANK: Record<PeriodFilterKind, number> = {
  year: 0,
  quarter: 1,
  month: 2,
};

/** Orders period filters coarse to fine: year, quarter, month. */
export function sortPeriodFilters(periodFilters: Filter[]): Filter[] {
  const rank = (filter: Filter) => {
    const kind = getPeriodFilterKindFromFilter(filter);
    return kind ? PERIOD_KIND_RANK[kind] : PERIOD_KIND_RANK.month + 1;
  };
  return [...periodFilters].sort((a, b) => rank(a) - rank(b));
}

/**
 * One-line summary of the selected period, e.g. "2018 EFY · Q3". Only the
 * controls visible for the current period type contribute.
 */
export function getPeriodSummary(
  periodFilters: Filter[],
  dataMask: DataMaskStateWithId,
  grain: PeriodGrain,
): string {
  return sortPeriodFilters(periodFilters)
    .filter(
      filter =>
        isPeriodFilterVisible(filter, grain) &&
        hasFilterValue(filter, dataMask),
    )
    .map(filter => {
      const { label, value } = dataMask[filter.id]?.filterState ?? {};
      if (typeof label === 'string' && label) {
        return label;
      }
      return Array.isArray(value) ? value.join(', ') : String(value ?? '');
    })
    .filter(Boolean)
    .join(' · ');
}

export function partitionFiltersInScope(filtersInScope: (Filter | Divider)[]): {
  periodFilters: Filter[];
  orgUnitFilters: Filter[];
  localFilters: (Filter | Divider)[];
} {
  const periodFilters: Filter[] = [];
  const orgUnitFilters: Filter[] = [];
  const localFilters: (Filter | Divider)[] = [];

  filtersInScope.forEach(filter => {
    if (isFilterDivider(filter) || getFilterBarSection(filter) === 'local') {
      localFilters.push(filter);
      return;
    }
    const named = filter as Filter;
    if (getPeriodFilterKindFromFilter(named)) {
      periodFilters.push(named);
      return;
    }
    if (isOrgUnitFilterName(named.name)) {
      orgUnitFilters.push(named);
      return;
    }
    localFilters.push(filter);
  });

  return { periodFilters, orgUnitFilters, localFilters };
}

export function getFilterVisualOrder(
  filterId: string,
  periodFilters: Filter[],
  orgUnitFilters: Filter[],
  localFilters: (Filter | Divider)[],
): number {
  const periodIndex = periodFilters.findIndex(filter => filter.id === filterId);
  if (periodIndex !== -1) {
    return 10 + periodIndex;
  }
  const orgIndex = orgUnitFilters.findIndex(filter => filter.id === filterId);
  if (orgIndex !== -1) {
    return 50 + orgIndex;
  }
  const localIndex = localFilters.findIndex(filter => filter.id === filterId);
  if (localIndex !== -1) {
    return 100 + localIndex;
  }
  return 1000;
}
