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
import { useMemo } from 'react';
import { useSelector } from 'react-redux';
import { Divider, Filter, isNativeFilter } from '@superset-ui/core';
import { RootState } from 'src/dashboard/types';
import { CHART_TYPE } from 'src/dashboard/util/componentTypes';
import { getChartIdsInFilterScope } from 'src/dashboard/util/getChartIdsInFilterScope';

const TITLE_FILTER_KEYWORDS = [
  'indicator',
  'dataset',
  'data element',
  'data_element',
  'year',
];
const TITLE_JOIN_SEPARATOR = ' — ';

const formatFilterValue = (value: unknown): string | null => {
  if (value == null) return null;
  const parts = Array.isArray(value) ? value : [value];
  const labels = parts
    .map(part => (part == null ? '' : String(part).trim()))
    .filter(Boolean);
  if (labels.length === 0) return null;
  return labels.join(', ');
};

/**
 * Builds a chart title that reflects the current selection of dashboard
 * filters named after the keywords Indicator, Dataset and Year, restricted to
 * filters whose scope includes the chart.
 *
 * Selected filter values (including configured defaults) are appended to the
 * base title, skipping any filter without a selection, e.g.
 * "Malaria cases — Ethiopia — 2024".
 */
export function useDynamicChartTitle(
  chartId: number,
  baseTitle: string,
): string {
  const filters = useSelector(
    (state: RootState) => state.nativeFilters?.filters,
  );
  const dataMask = useSelector((state: RootState) => state.dataMask);
  const dashboardLayout = useSelector(
    (state: RootState) => state.dashboardLayout?.present,
  );

  return useMemo(() => {
    const layoutItems = Object.values(dashboardLayout ?? {});
    const chartIds = layoutItems
      .filter(item => item.type === CHART_TYPE && item.meta?.chartId != null)
      .map(item => item.meta!.chartId as number);

    const filterValues = TITLE_FILTER_KEYWORDS.flatMap(keyword => {
      const filter = Object.values(filters ?? {}).find(
        (candidate): candidate is Filter => {
          if (!candidate) return false;
          const filterElement = candidate as Filter | Divider;
          return (
            isNativeFilter(filterElement) &&
            filterElement.name.toLowerCase().includes(keyword) &&
            getChartIdsInFilterScope(
              filterElement.scope,
              chartIds,
              layoutItems,
            ).includes(chartId)
          );
        },
      );
      if (!filter) return [];
      const label = formatFilterValue(
        dataMask?.[filter.id]?.filterState?.value,
      );
      return label ? [label] : [];
    });

    if (filterValues.length === 0) return baseTitle;
    return `${baseTitle}${TITLE_JOIN_SEPARATOR}${filterValues.join(
      TITLE_JOIN_SEPARATOR,
    )}`;
  }, [baseTitle, chartId, dataMask, dashboardLayout, filters]);
}
