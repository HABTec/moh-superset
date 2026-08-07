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
  FC,
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { t } from '@apache-superset/core/translation';
import {
  ChartDataResponseResult,
  Behavior,
  DataMask,
  Filters,
  isFeatureEnabled,
  FeatureFlag,
  getChartMetadataRegistry,
  JsonObject,
  QueryFormData,
  SuperChart,
  ClientErrorObject,
  getClientErrorObject,
  isChartCustomization,
} from '@superset-ui/core';
import { styled } from '@apache-superset/core/theme';
import { useDispatch, useSelector } from 'react-redux';
import { isEqual, isEqualWith } from 'lodash';
import { getChartDataRequest } from 'src/components/Chart/chartAction';
import { ErrorAlert, ErrorMessageWithStackTrace } from 'src/components';
import {
  Loading,
  Constants,
  Flex,
  Dropdown,
  Icons,
} from '@superset-ui/core/components';
import { FilterPlugins } from 'src/constants';
import { waitForAsyncData } from 'src/middleware/asyncEvent';
import { FilterBarOrientation, RootState } from 'src/dashboard/types';
import {
  onFiltersRefreshSuccess,
  setDirectPathToChild,
} from 'src/dashboard/actions/dashboardState';
import {
  setHoveredChartCustomization,
  unsetHoveredChartCustomization,
} from 'src/dashboard/actions/nativeFilters';
import { RESPONSIVE_WIDTH } from 'src/filters/components/common';
import { dispatchHoverAction, dispatchFocusAction } from './utils';
import { FilterControlProps } from './types';
import { getFormData } from '../../utils';
import { useFilterDependencies, useTransitiveParentIds } from './state';
import { useFilterOutlined } from '../useFilterOutlined';

const HEIGHT = 32;

// Overrides superset-ui height with min-height
const StyledDiv = styled.div<{
  orientation: FilterBarOrientation;
  overflow: boolean;
}>`
  padding-bottom: ${({ theme, orientation, overflow }) =>
    orientation === FilterBarOrientation.Horizontal && !overflow
      ? 0
      : (theme?.sizeUnit ?? 4)}px;

  & > div {
    height: auto !important;
    min-height: ${HEIGHT}px;
  }
`;

const queriesDataPlaceholder = [{ data: [{}] }];

type TimeGrainFilterConfig = {
  time_grains?: string[];
};

const MultiSelectTrigger = styled.button<{
  orientation: FilterBarOrientation;
  overflow: boolean;
}>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: ${HEIGHT}px;
  gap: ${({ theme }) => theme.sizeUnit * 1.5}px;
  padding: ${({ theme }) => `0 ${theme.sizeUnit * 1.5}px`};
  border: 1px solid ${({ theme }) => theme.colorBorder};
  border-radius: ${({ theme }) => theme.borderRadius}px;
  background: ${({ theme }) => theme.colorBgContainer};
  color: ${({ theme }) => theme.colorText};
  font-size: ${({ theme }) => theme.fontSize}px;
  text-align: left;
  cursor: pointer;
  &:hover {
    border-color: ${({ theme }) => theme.colorPrimary};
  }
`;

const MultiSelectTriggerText = styled.span<{ hasValue: boolean }>`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: ${({ theme, hasValue }) =>
    hasValue ? theme.colorText : theme.colorTextSecondary};
`;

export const compactControlPlugins: string[] = [
  FilterPlugins.Select,
  FilterPlugins.Range,
  FilterPlugins.Time,
  FilterPlugins.TimeColumn,
  FilterPlugins.TimeGrain,
];

/**
 * Multi-value filters whose plugin already renders as a compact control (e.g.
 * the Select dropdown) keep their behavior. Plugins that render a full-size
 * value area (e.g. the Org Unit tree) are collapsed behind a dropdown trigger.
 */
export function shouldWrapInControl(
  filterType: string,
  multiSelect?: boolean,
): boolean {
  const allowsMultiple =
    filterType === FilterPlugins.OrgUnitTree || multiSelect === true;
  return allowsMultiple && !compactControlPlugins.includes(filterType);
}

export function formatMultiSelectTriggerValue(value: unknown): string | null {
  const list = Array.isArray(value) ? value : value != null ? [value] : [];
  if (list.length === 0) {
    return null;
  }
  return `${list
    .slice(0, 2)
    .map(String)
    .join(', ')}${list.length > 2 ? ` +${list.length - 2}` : ''}`;
}

export const applyTimeGrainAllowlist = (
  filterType: string,
  allowedTimeGrains: string[] | undefined,
  results: ChartDataResponseResult[],
): ChartDataResponseResult[] => {
  if (filterType !== 'filter_timegrain' || !allowedTimeGrains?.length) {
    return results;
  }

  return results.map(result => {
    if (!Array.isArray(result.data)) {
      return result;
    }

    return {
      ...result,
      data: result.data.filter(row =>
        allowedTimeGrains.includes(
          (row as { duration?: string }).duration ?? '',
        ),
      ),
    };
  });
};

const useShouldFilterRefresh = () => {
  const isDashboardRefreshing = useSelector<RootState, boolean>(
    state => state.dashboardState.isRefreshing,
  );
  const isFilterRefreshing = useSelector<RootState, boolean>(
    state => state.dashboardState.isFiltersRefreshing,
  );

  // trigger filter requests only after charts requests were triggered
  return !isDashboardRefreshing && isFilterRefreshing;
};

export type FilterValueProps = FilterControlProps;

const FilterValue: FC<FilterValueProps> = ({
  dataMaskSelected,
  filter,
  onFilterSelectionChange,
  inView = true,
  showOverflow,
  parentRef,
  setFilterActive,
  orientation = FilterBarOrientation.Vertical,
  overflow = false,
  validateStatus,
  clearAllTrigger,
  onClearAllComplete,
}) => {
  const { id, targets, filterType } = filter;
  const isCustomization = isChartCustomization(filter);
  const allowedTimeGrains = isCustomization
    ? undefined
    : (filter as TimeGrainFilterConfig).time_grains;
  const adhocFilters = isCustomization ? undefined : filter.adhoc_filters;
  const timeRange = isCustomization ? undefined : filter.time_range;
  const granularitySqla = isCustomization ? undefined : filter.granularity_sqla;
  const metadata = getChartMetadataRegistry().get(filterType);
  const dependencies = useFilterDependencies(id, dataMaskSelected);
  const transitiveParentIds = useTransitiveParentIds(id);
  const shouldRefresh = useShouldFilterRefresh();
  // Org Unit Tree auto-couples to CBMP without cascade-parent config: pull the
  // live (pre-Apply) CBMP selection from sibling filters in dataMaskSelected.
  const allNativeFilters = useSelector<RootState, Filters | undefined>(
    state => state.nativeFilters?.filters,
  );
  const cbmpLiveExtra = useMemo(() => {
    if (filterType !== 'filter_org_unit_tree' || !allNativeFilters) {
      return undefined;
    }
    const filters: Array<{ col: string; op: string; val: unknown }> = [];
    Object.values(allNativeFilters).forEach(candidate => {
      if (
        !candidate ||
        candidate.id === id ||
        !('filterType' in candidate) ||
        candidate.filterType === 'filter_org_unit_tree'
      ) {
        return;
      }
      const name = String(candidate.name || '').toLowerCase();
      const cols = (candidate.targets || []).map(target =>
        String(target.column?.name || '')
          .toLowerCase()
          .replace(/\s+/g, '_'),
      );
      const isCbmp =
        name.includes('cbmp') ||
        cols.some(
          col => col === 'cbmp' || col === 'cbmp_type' || col.includes('cbmp'),
        );
      if (!isCbmp) {
        return;
      }
      const mask = dataMaskSelected?.[candidate.id];
      const fromExtra = mask?.extraFormData?.filters || [];
      if (fromExtra.length) {
        fromExtra.forEach(item => {
          // Normalize to cbmp_type so OrgUnitTree recognizes the values.
          filters.push({
            col: 'cbmp_type',
            op: String(item.op || 'IN'),
            val: item.val,
          });
        });
        return;
      }
      const value = mask?.filterState?.value;
      if (value == null || (Array.isArray(value) && value.length === 0)) {
        return;
      }
      filters.push({ col: 'cbmp_type', op: 'IN', val: value });
    });
    return filters.length ? { filters } : { filters: [] };
  }, [filterType, allNativeFilters, dataMaskSelected, id]);

  const behaviors = useMemo(
    () => [
      isCustomization ? Behavior.ChartCustomization : Behavior.NativeFilter,
    ],
    [isCustomization],
  );
  const [state, setState] = useState<ChartDataResponseResult[]>([]);
  const hasDeps = Boolean(filter.cascadeParentIds?.length);
  const [hasDepsFilterValue, setHasDepsFilterValue] = useState(hasDeps);
  const dashboardId = useSelector<RootState, number>(
    state => state.dashboardInfo.id,
  );

  const [error, setError] = useState<ClientErrorObject>();
  const [formData, setFormData] = useState<Partial<QueryFormData>>({
    inView: false,
  });
  const [ownState, setOwnState] = useState<JsonObject>({});
  const [inViewFirstTime, setInViewFirstTime] = useState(inView);
  const inputRef = useRef<HTMLInputElement>(null);
  const [target] = targets || [];
  const {
    datasetId,
    column = {},
  }: Partial<{ datasetId: number; column: { name?: string } }> = target || {};
  const groupby = column?.name;
  const hasDataSource = !!datasetId;
  const [isLoading, setIsLoading] = useState<boolean>(hasDataSource);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const dispatch = useDispatch();

  const { outlinedFilterId, lastUpdated } = useFilterOutlined();

  const handleFilterLoadFinish = useCallback(() => {
    setIsRefreshing(false);
    setIsLoading(false);
    if (shouldRefresh) {
      dispatch(onFiltersRefreshSuccess());
    }
  }, [dispatch, shouldRefresh]);

  useEffect(() => {
    setHasDepsFilterValue(hasDeps);
  }, [hasDeps]);

  useEffect(() => {
    if (!inViewFirstTime && inView) {
      setInViewFirstTime(true);
    }
  }, [inView, inViewFirstTime, setInViewFirstTime]);

  useEffect(() => {
    if (!inViewFirstTime) {
      return;
    }
    const newFormData = getFormData({
      ...filter,
      datasetId,
      dependencies,
      groupby,
      adhoc_filters: adhocFilters,
      time_range: timeRange,
      granularity_sqla: granularitySqla,
      dashboardId,
    });
    // For Org Unit Tree, overlay live CBMP sibling selection so the tree
    // reloads as soon as CBMP changes (no cascade-parent config / Apply needed).
    if (cbmpLiveExtra) {
      const existing =
        (newFormData.extra_form_data as { filters?: unknown[] } | undefined)
          ?.filters || [];
      newFormData.extra_form_data = {
        ...((newFormData.extra_form_data as object) || {}),
        filters: [...existing, ...(cbmpLiveExtra.filters || [])],
      };
    }
    const filterOwnState = filter.dataMask?.ownState || {};
    if (transitiveParentIds.length) {
      // Prevent unnecessary backend requests by validating ancestor filter
      // selections first. We walk the full transitive ancestor chain (not just
      // direct parents) so the counts line up with `dependencies`, which is
      // itself built from the transitive chain by `useFilterDependencies`.

      let selectedParentFilterValueCounts = 0;
      let isTimeRangeSelected = false;
      transitiveParentIds.forEach(pId => {
        const extraFormData = dataMaskSelected?.[pId]?.extraFormData;
        if (extraFormData?.filters?.length) {
          selectedParentFilterValueCounts += extraFormData.filters.length;
        }
        if (extraFormData?.time_range) {
          isTimeRangeSelected = true;
        }
      });

      // check if all ancestor filters with defaults have a value selected

      const depsCount = dependencies.filters?.length ?? 0;
      const hasTimeRangeDeps = Boolean(dependencies?.time_range);

      if (
        selectedParentFilterValueCounts !== depsCount ||
        (hasTimeRangeDeps && !isTimeRangeSelected)
      ) {
        // child filter should not request backend until it
        // has all the required information from ancestor filters
        return;
      }
      setHasDepsFilterValue(false);
    }

    // TODO: We should try to improve our useEffect hooks to depend more on
    // granular information instead of big objects that require deep comparison.
    const customizer = (
      objValue: Partial<QueryFormData>,
      othValue: Partial<QueryFormData>,
      key: string,
    ) => (key === 'url_params' ? true : undefined);
    if (
      !isRefreshing &&
      (!isEqualWith(formData, newFormData, customizer) ||
        !isEqual(ownState, filterOwnState) ||
        shouldRefresh)
    ) {
      setFormData(newFormData);
      setOwnState(filterOwnState);
      if (!hasDataSource) {
        return;
      }
      setIsRefreshing(true);
      getChartDataRequest({
        formData: newFormData,
        force: shouldRefresh,
        ownState: filterOwnState,
      })
        .then(({ response, json }) => {
          if (isFeatureEnabled(FeatureFlag.GlobalAsyncQueries)) {
            // deal with getChartDataRequest transforming the response data
            const result = 'result' in json ? json.result[0] : json;
            if (response.status === 200) {
              setState(
                applyTimeGrainAllowlist(filterType, allowedTimeGrains, [
                  result as ChartDataResponseResult,
                ]),
              );
              setError(undefined);
              handleFilterLoadFinish();
            } else if (response.status === 202) {
              waitForAsyncData(result as Parameters<typeof waitForAsyncData>[0])
                .then((asyncResult: ChartDataResponseResult[]) => {
                  setState(
                    applyTimeGrainAllowlist(
                      filterType,
                      allowedTimeGrains,
                      asyncResult,
                    ),
                  );
                  setError(undefined);
                  handleFilterLoadFinish();
                })
                .catch((error: Response) => {
                  getClientErrorObject(error).then(clientErrorObject => {
                    setError(clientErrorObject);
                    handleFilterLoadFinish();
                  });
                });
            } else {
              throw new Error(
                `Received unexpected response status (${response.status}) while fetching chart data`,
              );
            }
          } else {
            setState(
              applyTimeGrainAllowlist(
                filterType,
                allowedTimeGrains,
                json.result as ChartDataResponseResult[],
              ),
            );
            setError(undefined);
            handleFilterLoadFinish();
          }
        })
        .catch((error: Response) => {
          getClientErrorObject(error).then(clientErrorObject => {
            setError(clientErrorObject);
            handleFilterLoadFinish();
          });
        });
    }
  }, [
    inViewFirstTime,
    dependencies,
    cbmpLiveExtra,
    datasetId,
    groupby,
    handleFilterLoadFinish,
    filter,
    allowedTimeGrains,
    hasDataSource,
    isRefreshing,
    shouldRefresh,
    dataMaskSelected,
    setHasDepsFilterValue,
    transitiveParentIds,
  ]);

  useEffect(() => {
    if (outlinedFilterId && outlinedFilterId === filter.id) {
      setTimeout(
        () => {
          inputRef?.current?.focus();
        },
        overflow ? Constants.FAST_DEBOUNCE : 0,
      );
    }
  }, [inputRef, outlinedFilterId, lastUpdated, filter.id, overflow]);

  const setDataMask = useCallback(
    (dataMask: DataMask) => onFilterSelectionChange(filter, dataMask),
    [filter, onFilterSelectionChange],
  );

  const setFocusedFilter = useCallback(() => {
    if (isCustomization) {
      return;
    }
    if (outlinedFilterId !== id) {
      dispatchFocusAction(dispatch, id);
    }
  }, [dispatch, id, outlinedFilterId, isCustomization]);

  const unsetFocusedFilter = useCallback(() => {
    if (isCustomization) {
      return;
    }
    dispatchFocusAction(dispatch);
    if (outlinedFilterId === id) {
      dispatch(setDirectPathToChild([]));
    }
  }, [dispatch, id, outlinedFilterId, isCustomization]);

  const setHoveredFilter = useCallback(() => {
    if (isCustomization) {
      dispatch(setHoveredChartCustomization(id));
    } else {
      dispatchHoverAction(dispatch, id);
    }
  }, [dispatch, id, isCustomization]);

  const unsetHoveredFilter = useCallback(() => {
    if (isCustomization) {
      dispatch(unsetHoveredChartCustomization());
    } else {
      dispatchHoverAction(dispatch);
    }
  }, [dispatch, isCustomization]);

  const hooks = useMemo(
    () => ({
      setDataMask,
      setHoveredFilter,
      unsetHoveredFilter,
      setFocusedFilter,
      unsetFocusedFilter,
      setFilterActive,
      clearAllTrigger,
      onClearAllComplete,
    }),
    [
      setDataMask,
      setFilterActive,
      setHoveredFilter,
      unsetHoveredFilter,
      setFocusedFilter,
      unsetFocusedFilter,
      clearAllTrigger,
      onClearAllComplete,
    ],
  );

  const filterState = useMemo(
    () => ({
      ...filter.dataMask?.filterState,
      validateStatus,
    }),
    [filter.dataMask?.filterState, validateStatus],
  );

  const displaySettings = useMemo(
    () => ({
      filterBarOrientation: orientation,
      isOverflowingFilterBar: overflow,
    }),
    [orientation, overflow],
  );

  if (error) {
    return (
      <ErrorMessageWithStackTrace
        error={error.errors?.[0]}
        compact
        fallback={
          <ErrorAlert
            errorType={t('Network error')}
            message={t('Network error while attempting to fetch resource')}
            type="error"
            compact
          />
        }
      />
    );
  }

  const wrapAsControl = shouldWrapInControl(
    filterType,
    filter.controlValues?.multiSelect,
  );

  const formattedTrigger = formatMultiSelectTriggerValue(
    filter.dataMask?.filterState?.value,
  );
  const triggerText = formattedTrigger ?? t('Select…');

  const filterControl = isLoading ? (
    <Flex align="center">
      <Loading position="inline" size="s" muted />
      {hasDepsFilterValue
        ? t('Awaiting filter selection')
        : t('Loading filter values')}
    </Flex>
  ) : (
    <SuperChart
      height={HEIGHT}
      width={RESPONSIVE_WIDTH}
      showOverflow={showOverflow}
      formData={formData}
      displaySettings={displaySettings}
      parentRef={parentRef}
      inputRef={inputRef}
      // For charts that don't have datasource we need workaround for empty placeholder
      queriesData={hasDataSource ? state : queriesDataPlaceholder}
      chartType={filterType}
      behaviors={behaviors}
      filterState={filterState}
      ownState={filter.dataMask?.ownState}
      enableNoResults={metadata?.enableNoResults}
      isRefreshing={isRefreshing}
      hooks={hooks}
    />
  );

  return (
    <StyledDiv
      data-test="form-item-value"
      orientation={orientation}
      overflow={overflow}
    >
      {wrapAsControl ? (
        <Dropdown
          popupRender={() => (
            <div style={{ width: 340, maxHeight: 480, overflow: 'auto' }}>
              {filterControl}
            </div>
          )}
          trigger={['click']}
          placement="bottomLeft"
          onOpenChange={open => {
            if (open) {
              setFocusedFilter();
            } else {
              unsetFocusedFilter();
            }
          }}
        >
          <MultiSelectTrigger
            orientation={orientation}
            overflow={overflow}
            data-test="multiselect-trigger"
          >
            <MultiSelectTriggerText hasValue={formattedTrigger != null}>
              {triggerText}
            </MultiSelectTriggerText>
            <Icons.DownOutlined iconSize="s" />
          </MultiSelectTrigger>
        </Dropdown>
      ) : (
        filterControl
      )}
    </StyledDiv>
  );
};
export default memo(FilterValue);
