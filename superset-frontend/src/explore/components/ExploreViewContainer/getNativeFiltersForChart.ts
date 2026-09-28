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
import { Divider, Filter } from '@superset-ui/core';
import { ActiveFilters } from 'src/dashboard/types';
import { isNativeFilter } from 'src/dashboard/components/nativeFilters/FiltersConfigModal/utils';

/**
 * Ids of the native filters that apply to the chart being explored.
 *
 * The scope of each filter is resolved by the dashboard when it hands Explore
 * its context, so the ids come straight from that scope map rather than from a
 * second implementation of the targeting rules. Filters that apply to every
 * chart have a scope covering all of them, which is why an empty scope is
 * treated as "applies here".
 *
 * Returns an empty list when Explore has no inherited filter context, which is
 * what keeps the query free of dashboard filters for charts opened directly.
 */
export default function getNativeFiltersForChart(
  configuration: (Filter | Divider)[] | undefined,
  activeFilters: ActiveFilters | undefined,
  sliceId: number,
): string[] {
  if (!configuration?.length || !activeFilters) {
    return [];
  }

  const knownFilterIds = new Set(
    configuration
      .filter(filter => 'targets' in filter)
      .map(filter => filter.id),
  );

  return Object.entries(activeFilters)
    .filter(([filterId, activeFilter]) => {
      if (!knownFilterIds.has(filterId)) {
        return false;
      }
      const scope = activeFilter?.scope;
      return !scope?.length || scope.includes(sliceId);
    })
    .map(([filterId]) => filterId)
    .filter(filterId => isNativeFilter(filterId));
}
