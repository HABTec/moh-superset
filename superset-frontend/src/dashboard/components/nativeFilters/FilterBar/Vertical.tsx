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

/* eslint-disable no-param-reassign */
import { throttle } from 'lodash';
import {
  memo,
  useEffect,
  useState,
  useCallback,
  useMemo,
  useRef,
  createContext,
  FC,
} from 'react';
import { useSelector } from 'react-redux';
import cx from 'classnames';
import { t } from '@apache-superset/core/translation';
import { styled, useTheme } from '@apache-superset/core/theme';
import { RootState } from 'src/dashboard/types';
import { DataMaskStateWithId } from '@superset-ui/core';
import { Icons } from '@superset-ui/core/components/Icons';
import { EmptyState, Loading } from '@superset-ui/core/components';
import { useChartLayoutItems } from 'src/dashboard/util/useChartLayoutItems';
import { useChartIds } from 'src/dashboard/util/charts/useChartIds';
import { getFilterBarTestId, useChartsVerboseMaps } from './utils';
import { VerticalBarProps } from './types';
import Header from './Header';
import FilterControls from './FilterControls/FilterControls';
import CrossFiltersVertical from './CrossFilters/Vertical';
import crossFiltersSelector from './CrossFilters/selectors';

enum SectionType {
  Filters = 'filters',
  ChartCustomization = 'chartCustomization',
  CrossFilters = 'crossFilters',
}

const BarWrapper = styled.div<{ width: number }>`
  /* Mobile responsiveness: adjust width based on screen size */
  @media (max-width: 575px) {
    width: ${({ theme }) => theme.sizeUnit * 8}px;
    
    &.open {
      width: 100%; /* Full width on mobile */
    }
  }
  
  @media (min-width: 576px) and (max-width: 768px) {
    width: ${({ theme }) => theme.sizeUnit * 8}px;
    
    &.open {
      width: 150px; /* Compact on tablet */
    }
  }
  
  @media (min-width: 769px) {
    width: ${({ theme }) => theme.sizeUnit * 8}px;

    &.open {
      width: ${({ width }) => width}px; /* Full width on desktop */
    }
  }

  & .ant-tabs-top > .ant-tabs-nav {
    margin: 0;
  }
`;

const Bar = styled.div<{ width: number }>`
  ${({ theme, width }) => `
    & .ant-typography-edit-content {
      left: 0;
      margin-top: 0;
      width: 100%;
    }
    position: absolute;
    top: 0;
    left: 0;
    flex-direction: column;
    flex-grow: 1;
    background: ${theme.colorBgContainer};
    border-right: 1px solid ${theme.colorSplit};
    border-bottom: 1px solid ${theme.colorSplit};
    min-height: 100%;
    display: none;
    
    /* Mobile: full width */
    @media (max-width: 575px) {
      width: 100%;
      &.open {
        display: flex;
        position: fixed;
        z-index: 1000;
        top: 0;
        left: 0;
        right: 0;
        height: auto;
        max-height: 70vh;
        overflow-y: auto;
        border-bottom: 1px solid ${theme.colorSplit};
      }
    }
    
    /* Tablet: compact width */
    @media (min-width: 576px) and (max-width: 768px) {
      width: 150px;
      &.open {
        display: flex;
      }
    }
    
    /* Desktop: full configured width */
    @media (min-width: 769px) {
      width: ${width}px;
      &.open {
        display: flex;
      }
    }
  `}
`;

const CollapsedBar = styled.div<{ offset: number }>`
  ${({ theme, offset }) => `
    position: absolute;
    top: ${offset}px;
    left: 0;
    height: 100%;
    padding-top: ${theme.sizeUnit * 2}px;
    display: none;
    text-align: center;
    
    /* Mobile: collapse button */
    @media (max-width: 575px) {
      width: ${theme.sizeUnit * 6}px;
      &.open {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: ${theme.sizeUnit}px;
      }
    }
    
    /* Tablet & Desktop */
    @media (min-width: 576px) {
      width: ${theme.sizeUnit * 8}px;
      &.open {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: ${theme.sizeUnit * 2}px;
      }
    }
    
    svg {
      cursor: pointer;
    }
  `}
`;

const FilterBarEmptyStateContainer = styled.div`
  margin-top: ${({ theme }) => theme.sizeUnit * 8}px;
`;

const FilterControlsWrapper = styled.div`
  ${({ theme }) => `
    display: flex;
    flex-direction: column;
    gap: ${theme.sizeUnit * 2}px;
    
    /* Mobile: reduced padding */
    @media (max-width: 575px) {
      padding: ${theme.sizeUnit * 2}px;
      padding-bottom: ${theme.sizeUnit * 12}px;
    }
    
    /* Tablet: medium padding */
    @media (min-width: 576px) and (max-width: 768px) {
      padding: ${theme.sizeUnit * 2.5}px;
      padding-bottom: ${theme.sizeUnit * 20}px;
    }
    
    /* Desktop: full padding */
    @media (min-width: 769px) {
      padding: ${theme.sizeUnit * 4}px;
      padding-top: 0;
      padding-bottom: ${theme.sizeUnit * 27}px;
    }
  `}
`;

export const FilterBarScrollContext = createContext(false);
const VerticalFilterBar: FC<VerticalBarProps> = ({
  actions,
  canEdit,
  dataMaskSelected,
  filtersOpen,
  filterValues,
  chartCustomizationValues,
  height,
  isInitialized,
  offset,
  onSelectionChange,
  onPendingCustomizationDataMaskChange,
  toggleFiltersBar,
  width,
  clearAllTriggers,
  onClearAllComplete,
}) => {
  const theme = useTheme();
  const [isScrolling, setIsScrolling] = useState(false);
  const timeout = useRef<any>();

  const openFiltersBar = useCallback(
    () => toggleFiltersBar(true),
    [toggleFiltersBar],
  );

  const onScroll = useMemo(
    () =>
      throttle(() => {
        clearTimeout(timeout.current);
        setIsScrolling(true);
        timeout.current = setTimeout(() => {
          setIsScrolling(false);
        }, 300);
      }, 200),
    [],
  );

  useEffect(() => {
    document.onscroll = onScroll;
    return () => {
      document.onscroll = null;
    };
  }, [onScroll]);

  const tabPaneStyle = useMemo(
    () => ({ overflow: 'auto', height, overscrollBehavior: 'contain' }),
    [height],
  );

  const dataMask = useSelector<RootState, DataMaskStateWithId>(
    state => state.dataMask,
  );
  const chartIds = useChartIds();
  const chartLayoutItems = useChartLayoutItems();
  const verboseMaps = useChartsVerboseMaps();
  const selectedCrossFilters = crossFiltersSelector({
    dataMask,
    chartIds,
    chartLayoutItems,
    verboseMaps,
  });

  // Determine available section types
  const availableSectionTypes = useMemo(() => {
    const types: SectionType[] = [];

    if (filterValues.length > 0) {
      types.push(SectionType.Filters);
    }

    if (chartCustomizationValues.length > 0) {
      types.push(SectionType.ChartCustomization);
    }

    if (selectedCrossFilters.length > 0) {
      types.push(SectionType.CrossFilters);
    }

    return types;
  }, [
    filterValues.length,
    chartCustomizationValues.length,
    selectedCrossFilters.length,
  ]);

  const hasOnlyOneSectionType = availableSectionTypes.length === 1;

  const filterControls = useMemo(() => {
    const hasFiltersOrCustomizations =
      filterValues.length > 0 || chartCustomizationValues.length > 0;

    return hasFiltersOrCustomizations ? (
      <FilterControlsWrapper>
        <FilterControls
          dataMaskSelected={dataMaskSelected}
          onFilterSelectionChange={onSelectionChange}
          onPendingCustomizationDataMaskChange={
            onPendingCustomizationDataMaskChange
          }
          chartCustomizationValues={chartCustomizationValues}
          hideHeader={hasOnlyOneSectionType}
        />
      </FilterControlsWrapper>
    ) : (
      <FilterBarEmptyStateContainer>
        <EmptyState
          size="small"
          title={t('No global filters are currently added')}
          image="filter.svg"
          description={
            canEdit &&
            t(
              'Click on "Add or edit filters and controls" option in Settings to create new dashboard filters',
            )
          }
        />
      </FilterBarEmptyStateContainer>
    );
  }, [
    canEdit,
    dataMaskSelected,
    filterValues.length,
    onSelectionChange,
    onPendingCustomizationDataMaskChange,
    chartCustomizationValues,
    hasOnlyOneSectionType,
  ]);

  return (
    <FilterBarScrollContext.Provider value={isScrolling}>
      <BarWrapper
        {...getFilterBarTestId()}
        className={cx({ open: filtersOpen })}
        width={width}
      >
        <CollapsedBar
          {...getFilterBarTestId('collapsable')}
          className={cx({ open: !filtersOpen })}
          onClick={openFiltersBar}
          role="button"
          offset={offset}
        >
          <Icons.VerticalAlignTopOutlined
            iconSize="l"
            css={{
              transform: 'rotate(90deg)',
              marginBottom: `${theme.sizeUnit * 3}px`,
            }}
            className="collapse-icon"
            iconColor={theme.colorPrimary}
            {...getFilterBarTestId('expand-button')}
          />
          <Icons.FilterOutlined
            {...getFilterBarTestId('filter-icon')}
            iconColor={theme.colorTextTertiary}
            iconSize="l"
          />
        </CollapsedBar>
        <Bar className={cx({ open: filtersOpen })} width={width}>
          <Header toggleFiltersBar={toggleFiltersBar} />
          {!isInitialized ? (
            <div
              css={{
                height,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Loading position="inline-centered" size="s" muted />
            </div>
          ) : (
            <div css={tabPaneStyle} onScroll={onScroll}>
              <>
                <CrossFiltersVertical hideHeader={hasOnlyOneSectionType} />
                {filterControls}
              </>
            </div>
          )}
          {actions}
        </Bar>
      </BarWrapper>
    </FilterBarScrollContext.Provider>
  );
};
export default memo(VerticalFilterBar);
