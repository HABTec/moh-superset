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
   * Text for the Period part. Null when the dashboard has no period filter,
   * or when no period filter reaches this scope and the scope's own data
   * source has no period dimension (the filter panel calls this "not
   * available for this source"). With a relevant filter but no selection
   * yet — or with no relevant filter but a scope built on a known,
   * period-having source (e.g. a Summary tab deliberately pinned to the
   * latest period) — it is the latest period.
   */
  period: string | null;
  /**
   * Text for the Organisation unit part. Same rule as `period`, for the
   * user's own area instead of the latest period.
   */
  orgUnit: string | null;
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
  /** Text shown for the period when a relevant filter has no selection yet. */
  latestPeriodLabel: string;
  /**
   * Whether the scope being described (a chart or a tab) is built on a data
   * source known to have a period/org-unit dimension, even when no filter's
   * own scope reaches it — e.g. a Summary tab deliberately left out of every
   * filter's scope so it always shows the latest period, as opposed to
   * Multi Source, whose charts have no period or org unit dimension at all.
   * Filter scope alone can't tell those two apart, since neither has a
   * filter reaching it.
   */
  sourceIsKnown: boolean;
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
  sourceIsKnown,
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

  // No relevant filter reaches this scope. When the scope's own source has
  // no period/org-unit dimension at all (Multi Source), report nothing
  // rather than a fabricated "latest" label that belongs to a different
  // data source. When it does (a Summary tab deliberately left unfiltered),
  // fall back to the latest period / the user's own area, same as a
  // relevant filter with no selection yet.
  const periodText = period.length
    ? labels(period).join(' · ') || latestPeriodLabel
    : allPeriod.length > 0 && sourceIsKnown
      ? latestPeriodLabel
      : null;
  const orgUnitText = orgUnit.length
    ? labels(orgUnit).join(', ') || orgUnitScopeLabel
    : allOrgUnit.length > 0 && sourceIsKnown
      ? orgUnitScopeLabel
      : null;

  return {
    period: periodText,
    orgUnit: orgUnitText,
    isDefault: [...period, ...orgUnit].every(filter =>
      hasDefaultSelection(filter, dataMask),
    ),
  };
}
