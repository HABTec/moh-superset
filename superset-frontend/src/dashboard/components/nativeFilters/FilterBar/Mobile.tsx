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
import { FC, memo, useEffect, useMemo, useState } from 'react';
import { DataMask, isNativeFilter } from '@superset-ui/core';
import { t } from '@apache-superset/core/translation';
import { css, styled } from '@apache-superset/core/theme';
import {
  Badge,
  Button,
  Drawer,
  Icons,
  Loading,
  Tag,
} from '@superset-ui/core/components';
import { FilterBarOrientation } from 'src/dashboard/types';
import { extractLabel } from '../selectors';
import FilterControls from './FilterControls/FilterControls';
import { getFilterBarTestId } from './utils';
import { MobileBarProps } from './types';

const MobileFiltersTrigger = styled.div`
  ${({ theme }) => css`
    position: fixed;
    left: ${theme.sizeUnit * 3}px;
    right: ${theme.sizeUnit * 3}px;
    bottom: max(${theme.sizeUnit * 3}px, env(safe-area-inset-bottom));
    z-index: 1000;
    pointer-events: none;

    .mobile-filter-trigger {
      width: 100%;
      min-height: 48px;
      border-radius: ${theme.borderRadius}px;
      box-shadow: ${theme.boxShadowSecondary};
      pointer-events: auto;
    }
  `}
`;

const MobileFilterSheetContent = styled.div`
  ${({ theme }) => css`
    --mobile-filter-sheet-padding: ${theme.sizeUnit * 5}px;

    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;

    .mobile-filter-sheet__chips {
      display: flex;
      gap: ${theme.sizeUnit}px;
      overflow-x: auto;
      padding: 0 var(--mobile-filter-sheet-padding)
        ${theme.sizeUnit * 3}px;
      -webkit-overflow-scrolling: touch;
    }

    .mobile-filter-sheet__chips .ant-tag {
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 0 0 auto;
      margin-right: 0;
    }

    .mobile-filter-sheet__controls {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      overscroll-behavior: contain;
      padding: 0 var(--mobile-filter-sheet-padding);
      -webkit-overflow-scrolling: touch;
    }

    .mobile-filter-sheet__controls [data-test='filterbar-action-buttons'] {
      background: ${theme.colorBgContainer};
      margin: 0 calc(var(--mobile-filter-sheet-padding) * -1);
      padding: ${theme.sizeUnit * 5}px var(--mobile-filter-sheet-padding)
        max(${theme.sizeUnit * 2}px, env(safe-area-inset-bottom));
    }

    .mobile-filter-sheet__controls
      [data-test='filterbar-action-buttons']
      button {
      min-height: 44px;
    }
  `}
`;

type AppliedChip = {
  id: string;
  label: string;
  value: string;
};

function hasDataMaskValue(mask?: DataMask): boolean {
  return (
    extractLabel(mask?.filterState) !== null || mask?.ownState?.column != null
  );
}

const MobileFilterBar: FC<MobileBarProps> = ({
  actions,
  dataMaskSelected,
  filterValues,
  chartCustomizationValues,
  isInitialized,
  onSelectionChange,
  onPendingCustomizationDataMaskChange,
  clearAllTriggers,
  onClearAllComplete,
}) => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return undefined;
    }

    document.body.classList.toggle('moh-mobile-filter-open', open);

    return () => {
      document.body.classList.remove('moh-mobile-filter-open');
    };
  }, [open]);

  const appliedChips = useMemo<AppliedChip[]>(
    () =>
      filterValues.filter(isNativeFilter).flatMap(filter => {
        const value = extractLabel(dataMaskSelected[filter.id]?.filterState);
        if (!value) {
          return [];
        }
        return [
          {
            id: filter.id,
            label: filter.name,
            value,
          },
        ];
      }),
    [dataMaskSelected, filterValues],
  );

  const activeCount = useMemo(() => {
    const filterCount = filterValues
      .filter(isNativeFilter)
      .filter(filter => hasDataMaskValue(dataMaskSelected[filter.id])).length;
    const customizationCount = chartCustomizationValues.filter(
      item => !item.removed && hasDataMaskValue(dataMaskSelected[item.id]),
    ).length;

    return filterCount + customizationCount;
  }, [chartCustomizationValues, dataMaskSelected, filterValues]);

  return (
    <>
      <MobileFiltersTrigger {...getFilterBarTestId('mobile-trigger')}>
        <Button
          buttonStyle="primary"
          className="mobile-filter-trigger"
          icon={<Icons.FilterOutlined iconSize="m" />}
          onClick={() => setOpen(true)}
        >
          <Badge count={activeCount} size="small">
            <span>{t('Filters')}</span>
          </Badge>
        </Button>
      </MobileFiltersTrigger>
      <Drawer
        title={t('Filters and controls')}
        placement="bottom"
        height="82vh"
        open={open}
        onClose={() => setOpen(false)}
        destroyOnClose={false}
        className="dashboard-mobile-filter-sheet"
        styles={{
          header: {
            paddingInline: 20,
          },
          body: {
            padding: 0,
          },
        }}
      >
        <MobileFilterSheetContent>
          {appliedChips.length > 0 && (
            <div className="mobile-filter-sheet__chips">
              {appliedChips.map(chip => (
                <Tag key={chip.id}>
                  {chip.label}: {chip.value}
                </Tag>
              ))}
            </div>
          )}
          {!isInitialized ? (
            <Loading position="inline-centered" size="s" muted />
          ) : (
            <div className="mobile-filter-sheet__controls">
              <FilterControls
                dataMaskSelected={dataMaskSelected}
                onFilterSelectionChange={onSelectionChange}
                onPendingCustomizationDataMaskChange={
                  onPendingCustomizationDataMaskChange
                }
                chartCustomizationValues={chartCustomizationValues}
                clearAllTriggers={clearAllTriggers}
                onClearAllComplete={onClearAllComplete}
                orientation={FilterBarOrientation.Vertical}
              />
              {actions}
            </div>
          )}
        </MobileFilterSheetContent>
      </Drawer>
    </>
  );
};

export default memo(MobileFilterBar);
