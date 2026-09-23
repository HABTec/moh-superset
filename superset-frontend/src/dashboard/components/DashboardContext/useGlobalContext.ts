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
import { useCallback, useMemo } from 'react';
import { useSelector } from 'react-redux';
import { t } from '@apache-superset/core/translation';
import { DataMaskStateWithId, Filter } from '@superset-ui/core';
import { DashboardLayout, RootState } from 'src/dashboard/types';
import { CHART_TYPE, TAB_TYPE } from 'src/dashboard/util/componentTypes';
import {
  getOrgUnitScopeLabel,
  useAssignedOrgUnit,
} from 'src/filters/components/OrgUnitTree/useAssignedOrgUnit';
import { useIsFilterInScope } from '../nativeFilters/state';
import { useFilters } from '../nativeFilters/FilterBar/state';
import {
  formatLatestPeriod,
  useLatestPeriod,
} from 'src/filters/components/OrgUnitTree/useLatestPeriod';
import {
  getGlobalContext,
  GlobalContext,
  hasOrgUnitFilter,
  hasPeriodFilter,
} from '../nativeFilters/FilterBar/globalContext';
import { getFreshnessSource } from './dataFreshness';

type LayoutItem = DashboardLayout[string];

const byDepth = (a: LayoutItem, b: LayoutItem) =>
  (a.parents?.length ?? 0) - (b.parents?.length ?? 0);

/**
 * The title of the outermost tab a chart lives under (or, with no
 * `chartId`, the outermost active tab) — the "Summary" in
 * "Summary · Child Health".
 */
function useTopLevelTabTitle(chartId?: number): string | undefined {
  const layout = useSelector<RootState, DashboardLayout>(
    state => state.dashboardLayout.present,
  );
  const activeTabs = useSelector<RootState, string[]>(
    state => state.dashboardState?.activeTabs ?? [],
  );

  return useMemo(() => {
    if (chartId === undefined) {
      const tabs = Object.values(layout)
        .filter(item => item?.type === TAB_TYPE && activeTabs.includes(item.id))
        .sort(byDepth);
      return tabs[0]?.meta?.text?.trim();
    }
    const chartItem = Object.values(layout).find(
      item => item?.type === CHART_TYPE && item.meta?.chartId === chartId,
    );
    const tabParents = (chartItem?.parents ?? [])
      .filter(id => layout[id]?.type === TAB_TYPE)
      .map(id => layout[id])
      .sort(byDepth);
    return tabParents[0]?.meta?.text?.trim();
  }, [layout, activeTabs, chartId]);
}

/**
 * The Period and Organisation unit currently applied. With a `chartId` it
 * describes what that chart is filtered by; without one, what the active tab is.
 */
export function useGlobalContext(chartId?: number): GlobalContext {
  // Same source the visible filter panel uses (dashboardInfo.metadata), not
  // the separate `state.nativeFilters.filters` slice — that one can still
  // hold a filter from a dashboard the user was on before this one, which
  // showed as a fabricated "Latest period" / "National / Ethiopia" on
  // dashboards that have no Period or Org Unit filter at all.
  const filters = useFilters();
  const dataMask = useSelector<RootState, DataMaskStateWithId>(
    state => state.dataMask,
  );
  const isFilterInScope = useIsFilterInScope();

  const orgUnitFilterExists = useMemo(
    () => hasOrgUnitFilter(filters),
    [filters],
  );
  const periodFilterExists = useMemo(() => hasPeriodFilter(filters), [filters]);
  const latestPeriod = useLatestPeriod(periodFilterExists);
  const latestPeriodLabel = formatLatestPeriod(latestPeriod);
  const assignedOrgUnit = useAssignedOrgUnit(orgUnitFilterExists);
  const orgUnitScopeLabel =
    assignedOrgUnit === undefined
      ? t('Loading…')
      : getOrgUnitScopeLabel(assignedOrgUnit);

  const isRelevant = useCallback(
    (filter: Filter) =>
      chartId === undefined
        ? Boolean(isFilterInScope(filter))
        : Boolean(filter.chartsInScope?.includes(chartId)),
    [chartId, isFilterInScope],
  );

  // A tab like Summary can sit outside every Period/Org Unit filter's scope
  // by design — deliberately pinned to the latest period and the user's own
  // area, not driven by whatever the user picked elsewhere — while still
  // being built on the same period/org-unit data as the rest of the routine
  // dashboards. Multi Source and Triangulation are a different case: their
  // charts have no period or org unit dimension at all. Both look identical
  // from filter scope alone (no filter reaches either), so the fallback
  // below is gated on the tab's own data source instead.
  const topLevelTabTitle = useTopLevelTabTitle(chartId);
  const sourceIsKnown = getFreshnessSource(topLevelTabTitle) !== null;

  return useMemo(
    () =>
      getGlobalContext({
        filters,
        dataMask,
        isRelevant,
        orgUnitScopeLabel,
        latestPeriodLabel,
        sourceIsKnown,
      }),
    [
      filters,
      dataMask,
      isRelevant,
      orgUnitScopeLabel,
      latestPeriodLabel,
      sourceIsKnown,
    ],
  );
}
