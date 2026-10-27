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
import { useDispatch, useSelector } from 'react-redux';
import { css, styled, useTheme } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import {
  DataMaskStateWithId,
  ensureIsArray,
  Filter,
  NativeFilterType,
} from '@superset-ui/core';
import { Button, EmptyState } from '@superset-ui/core/components';
import { RootState } from 'src/dashboard/types';
import {
  requestFilterBarClear,
  toggleNativeFiltersBar,
} from 'src/dashboard/actions/dashboardState';
import { useFilters } from '../nativeFilters/FilterBar/state';
import {
  getPeriodFilterKindFromFilter,
  sortPeriodFilters,
} from '../nativeFilters/FilterBar/filterBarLayout';
import { useGlobalContext } from '../DashboardContext/useGlobalContext';

/** Below this, the empty state drops its illustration. */
const IMAGE_MIN_HEIGHT = 220;
/** Below this, it also drops the context line (KPI tiles). */
const DESCRIPTION_MIN_HEIGHT = 110;
/** Wait for the filter bar's open transition before scrolling into it. */
const FILTER_BAR_OPEN_DELAY_MS = 300;

const Actions = styled.div`
  ${({ theme }) => css`
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: ${theme.sizeUnit * 2}px;
    margin-top: ${theme.sizeUnit * 2}px;
  `}
`;

const Container = styled.div<{ height?: number }>`
  height: ${({ height }) => (height ? `${height}px` : '100%')};
  overflow: hidden;
`;

function hasSelection(filter: Filter, dataMask: DataMaskStateWithId) {
  return ensureIsArray(dataMask[filter.id]?.filterState?.value).some(
    value => value !== null && value !== undefined && value !== '',
  );
}

export type ChartNoDataStateProps = {
  chartId: number;
  width?: number;
  height?: number;
};

/**
 * The one empty state every dashboard chart uses when the selected filters
 * leave nothing valid to draw: it keeps the chart's own title (rendered by
 * the chart holder above), says which Period / Organisation unit produced
 * the empty result, and offers recovery right where the user is looking.
 * Loading and query errors have their own states; this is only "no data".
 */
const ChartNoDataState = ({
  chartId,
  width,
  height,
}: ChartNoDataStateProps) => {
  const dispatch = useDispatch();
  const theme = useTheme();
  const filters = useFilters();
  const dataMask = useSelector<RootState, DataMaskStateWithId>(
    state => state.dataMask,
  );
  const { period, orgUnit } = useGlobalContext(chartId);

  const filtersInScope = useMemo(
    () =>
      Object.values(filters).filter(
        (filter): filter is Filter =>
          filter.type === NativeFilterType.NativeFilter &&
          Boolean((filter as Filter).chartsInScope?.includes(chartId)),
      ),
    [chartId, filters],
  );
  // Required filters are never cleared (see the filter bar), so only an
  // optional filter with a value gives "Clear filters" something to do.
  const canClear = filtersInScope.some(
    filter =>
      !filter.controlValues?.enableEmptyFilter &&
      hasSelection(filter, dataMask),
  );
  const periodFilter = useMemo(
    () =>
      sortPeriodFilters(
        filtersInScope.filter(filter => getPeriodFilterKindFromFilter(filter)),
      )[0],
    [filtersInScope],
  );

  const handleClear = useCallback(() => {
    dispatch(requestFilterBarClear());
  }, [dispatch]);

  const handleChangePeriod = useCallback(() => {
    dispatch(toggleNativeFiltersBar(true));
    setTimeout(() => {
      const target =
        document.querySelector<HTMLElement>('[data-test="period-card"]') ??
        (periodFilter
          ? document.getElementById(`filter-name-${periodFilter.id}`)
          : null);
      if (!target) return;
      target.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
      target.animate?.(
        [
          { boxShadow: `0 0 0 3px ${theme.colorPrimary}` },
          { boxShadow: '0 0 0 0 transparent' },
        ],
        { duration: 1600, easing: 'ease-out' },
      );
      target
        .querySelector<HTMLElement>('input, [tabindex]:not([tabindex="-1"])')
        ?.focus({ preventScroll: true });
    }, FILTER_BAR_OPEN_DELAY_MS);
  }, [dispatch, periodFilter, theme.colorPrimary]);

  const context = [period, orgUnit].filter(Boolean).join(' · ');
  const description = context
    ? t('No valid records were found for %s.', context)
    : t('No valid records were found for the selected filters.');

  const availableHeight = height ?? Number.MAX_SAFE_INTEGER;
  const showImage = availableHeight >= IMAGE_MIN_HEIGHT;
  const showDescription = availableHeight >= DESCRIPTION_MIN_HEIGHT;
  const compact = !showImage || (width ?? Number.MAX_SAFE_INTEGER) < 320;
  const buttonSize = compact ? 'xsmall' : 'small';

  return (
    <Container height={height} data-test="chart-no-data" title={description}>
      <EmptyState
        size={compact ? 'small' : 'medium'}
        image={showImage ? 'filter-results.svg' : null}
        title={t('No data for this filter combination')}
        description={showDescription ? description : null}
      >
        {(canClear || periodFilter) && (
          <Actions>
            {canClear && (
              <Button
                buttonStyle="secondary"
                buttonSize={buttonSize}
                onClick={handleClear}
                data-test="chart-no-data-clear"
              >
                {t('Clear filters')}
              </Button>
            )}
            {periodFilter && (
              <Button
                buttonStyle="primary"
                buttonSize={buttonSize}
                onClick={handleChangePeriod}
                data-test="chart-no-data-change-period"
              >
                {t('Change period')}
              </Button>
            )}
          </Actions>
        )}
      </EmptyState>
    </Container>
  );
};

export default ChartNoDataState;
