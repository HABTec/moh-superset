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
  DataMaskStateWithId,
  ensureIsArray,
  Filter,
  Filters,
  NativeFilterType,
} from '@superset-ui/core';
import { formatFilterOptionLabel } from 'src/filters/utils/filterDisplay';
import {
  getPeriodFilterKindFromFilter,
  isOrgUnitFilterName,
  sortPeriodFilters,
} from './filterBarLayout';

export type GlobalContext = {
  /**
   * Text for the Period part, or null when the dashboard has no period filter.
   * With no selection, or for charts no period filter reaches, it is the
   * latest period.
   */
  period: string | null;
  /**
   * Text for the Organisation unit part, or null when the dashboard has no
   * org unit filter. With no selection, or for charts no org unit filter
   * reaches, it is the user's own area.
   */
  orgUnit: string | null;
  /** A selected period exists that this scope does not follow. */
  periodOverridden: boolean;
  /** A selected org unit exists that this scope does not follow. */
  orgUnitOverridden: boolean;
  /** Every relevant global filter holds its configured default value. */
  isDefault: boolean;
};

type GlobalContextArgs = {
  filters: Filters | undefined;
  dataMask: DataMaskStateWithId;
  /** Whether a filter applies to the scope being described (a chart or a tab). */
  isRelevant: (filter: Filter) => boolean;
  /** Text shown for the org unit when nothing is selected. */
  orgUnitScopeLabel: string;
  /** Text shown for the period when nothing is selected or no filter applies. */
  latestPeriodLabel: string;
  /** The latest period itself, to tell whether a selection already matches it. */
  latestPeriod?: LatestPeriodParts | null;
};

export type LatestPeriodParts = {
  fiscalYear: string;
  quarter: number;
  monthName: string;
};

export function isOrgUnitFilter(filter: Filter): boolean {
  return (
    isOrgUnitFilterName(filter.name) ||
    filter.filterType === 'filter_org_unit_tree'
  );
}

function normalizeValues(value: unknown): string[] {
  return ensureIsArray(value)
    .filter(item => item != null && item !== '')
    .map(String)
    .sort();
}

function getNativeFilters(filters: Filters | undefined): Filter[] {
  return Object.values(filters ?? {}).filter(
    (filter): filter is Filter =>
      (filter as Filter).type === NativeFilterType.NativeFilter,
  );
}

export function hasPeriodFilter(filters: Filters | undefined): boolean {
  return getNativeFilters(filters).some(getPeriodFilterKindFromFilter);
}

export function hasOrgUnitFilter(filters: Filters | undefined): boolean {
  return getNativeFilters(filters).some(isOrgUnitFilter);
}

function describeSelection(
  filter: Filter,
  dataMask: DataMaskStateWithId,
): string | null {
  const state = dataMask[filter.id]?.filterState;
  if (state?.label && !state.label.includes(undefined as unknown as string)) {
    return state.label;
  }
  const column = filter.targets?.[0]?.column?.name;
  const values = normalizeValues(state?.value);
  return values.length
    ? values.map(value => formatFilterOptionLabel(value, column)).join(', ')
    : null;
}

/** Whether every selected period value is part of the latest period. */
function selectionMatchesLatest(
  periodFilters: Filter[],
  dataMask: DataMaskStateWithId,
  latest: LatestPeriodParts | null | undefined,
): boolean {
  if (!latest) {
    return false;
  }
  return periodFilters.every(filter => {
    const values = normalizeValues(dataMask[filter.id]?.filterState?.value);
    switch (getPeriodFilterKindFromFilter(filter)) {
      case 'year':
        return values.every(value => value === String(latest.fiscalYear));
      case 'quarter':
        return values.every(value => value.includes(`Q${latest.quarter}`));
      case 'month':
        return values.every(
          value => value.toLowerCase() === latest.monthName.toLowerCase(),
        );
      default:
        return false;
    }
  });
}

function hasDefaultSelection(filter: Filter, dataMask: DataMaskStateWithId) {
  // The Org Unit tree never preloads a default; empty means the user's scope.
  const defaults = isOrgUnitFilter(filter)
    ? []
    : normalizeValues(filter.defaultDataMask?.filterState?.value);
  const selected = normalizeValues(dataMask[filter.id]?.filterState?.value);
  return (
    defaults.length === selected.length &&
    defaults.every((value, index) => value === selected[index])
  );
}

/**
 * Describes the Period and Organisation unit a dashboard, tab or chart is
 * showing, from the applied filter state.
 */
export function getGlobalContext({
  filters,
  dataMask,
  isRelevant,
  orgUnitScopeLabel,
  latestPeriodLabel,
  latestPeriod,
}: GlobalContextArgs): GlobalContext {
  const nativeFilters = getNativeFilters(filters);
  const allPeriod = nativeFilters.filter(getPeriodFilterKindFromFilter);
  const allOrgUnit = nativeFilters.filter(isOrgUnitFilter);
  const period = sortPeriodFilters(allPeriod.filter(isRelevant));
  const orgUnit = allOrgUnit.filter(isRelevant);

  const labels = (items: Filter[]) =>
    items
      .map(filter => describeSelection(filter, dataMask))
      .filter((label): label is string => Boolean(label));

  const ignoresPeriod = allPeriod.length > 0 && period.length === 0;
  const ignoresOrgUnit = allOrgUnit.length > 0 && orgUnit.length === 0;
  const hasCustomSelection = (items: Filter[]) =>
    items.some(filter => !hasDefaultSelection(filter, dataMask));

  const selectedPeriod = allPeriod.filter(
    filter => normalizeValues(dataMask[filter.id]?.filterState?.value).length,
  );

  let periodText: string | null = null;
  if (ignoresPeriod) {
    periodText = latestPeriodLabel;
  } else if (period.length) {
    periodText = labels(period).join(' · ') || latestPeriodLabel;
  }

  let orgUnitText: string | null = null;
  if (ignoresOrgUnit) {
    orgUnitText = orgUnitScopeLabel;
  } else if (orgUnit.length) {
    orgUnitText = labels(orgUnit).join(', ') || orgUnitScopeLabel;
  }

  return {
    period: periodText,
    orgUnit: orgUnitText,
    periodOverridden:
      ignoresPeriod &&
      hasCustomSelection(allPeriod) &&
      selectedPeriod.length > 0 &&
      !selectionMatchesLatest(selectedPeriod, dataMask, latestPeriod),
    orgUnitOverridden: ignoresOrgUnit && hasCustomSelection(allOrgUnit),
    isDefault: [...period, ...orgUnit].every(filter =>
      hasDefaultSelection(filter, dataMask),
    ),
  };
}
