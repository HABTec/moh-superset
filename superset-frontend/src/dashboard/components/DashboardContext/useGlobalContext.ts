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
import { RootState } from 'src/dashboard/types';
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

  return useMemo(
    () =>
      getGlobalContext({
        filters,
        dataMask,
        isRelevant,
        orgUnitScopeLabel,
        latestPeriodLabel,
        latestPeriod,
      }),
    [
      filters,
      dataMask,
      isRelevant,
      orgUnitScopeLabel,
      latestPeriodLabel,
      latestPeriod,
    ],
  );
}
