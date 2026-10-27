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
import { useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  DataMaskStateWithId,
  Filter,
  NativeFilterType,
} from '@superset-ui/core';
import { DashboardLayout, RootState, Slice } from 'src/dashboard/types';
import { useFilters } from '../nativeFilters/FilterBar/state';
import { useIsFilterInScope } from '../nativeFilters/state';
import {
  collectTabSelections,
  getActiveTabChartIds,
  TabContext,
} from './tabContext';

const API_BASE_URL = '/api/v1/moh/dhis2';

const requests = new Map<string, Promise<TabContext | null>>();

export function resetTabContextRequestsForTests() {
  requests.clear();
}

function fetchTabContext(query: string): Promise<TabContext | null> {
  let request = requests.get(query);
  if (!request) {
    request = fetch(
      `${API_BASE_URL}/tab-context?q=${encodeURIComponent(query)}`,
      { credentials: 'same-origin' },
    )
      .then(response => (response.ok ? response.json() : null))
      .then(data => (Array.isArray(data?.sources) ? data : null))
      .catch(() => null);
    requests.set(query, request);
    // Let a later visit refetch: the server caches, so this only bounds the
    // page's own memory of answers that may have gone stale.
    request.finally(() => {
      setTimeout(() => requests.delete(query), 10 * 60 * 1000);
    });
  }
  return request;
}

/**
 * Source, data-as-of and reporting completeness for the active tab, from
 * the MoH tab-context endpoint. `undefined` while loading, `null` when the
 * tab has no configured source or the lookup failed — callers then fall
 * back to the older per-source "data as of".
 */
export function useTabContext(
  tabTitles: string[],
  innermostTabId: string | undefined,
): TabContext | null | undefined {
  const dashboardId = useSelector<RootState, number | undefined>(
    state => state.dashboardInfo?.id,
  );
  const layout = useSelector<RootState, DashboardLayout>(
    state => state.dashboardLayout.present,
  );
  const slices = useSelector<RootState, Record<number, Slice>>(
    state => state.sliceEntities?.slices ?? {},
  );
  const dataMask = useSelector<RootState, DataMaskStateWithId>(
    state => state.dataMask,
  );
  const filters = useFilters();
  const isFilterInScope = useIsFilterInScope();

  const query = useMemo(() => {
    if (!dashboardId || tabTitles.length === 0) {
      return null;
    }
    const chartIds = getActiveTabChartIds(layout, innermostTabId);
    const inScopeFilters = Object.values(filters).filter(
      (filter): filter is Filter =>
        filter.type === NativeFilterType.NativeFilter &&
        Boolean(isFilterInScope(filter as Filter)),
    );
    const selections = collectTabSelections({
      chartFormData: chartIds.map(id => slices[id]?.form_data),
      filters: inScopeFilters,
      dataMask,
    });
    return JSON.stringify({ dashboardId, tabPath: tabTitles, ...selections });
  }, [
    dashboardId,
    tabTitles,
    layout,
    innermostTabId,
    filters,
    isFilterInScope,
    slices,
    dataMask,
  ]);

  const [context, setContext] = useState<TabContext | null | undefined>();

  useEffect(() => {
    if (!query) {
      setContext(null);
      return undefined;
    }
    let cancelled = false;
    setContext(undefined);
    fetchTabContext(query).then(result => {
      if (!cancelled) {
        setContext(result && result.sources.length > 0 ? result : null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [query]);

  return context;
}
