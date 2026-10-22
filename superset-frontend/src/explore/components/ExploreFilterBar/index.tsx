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
import { FC, useMemo } from 'react';
import { useSelector } from 'react-redux';
import { css, styled } from '@apache-superset/core/theme';
import { Divider, Filter } from '@superset-ui/core';
import FilterBar from 'src/dashboard/components/nativeFilters/FilterBar';
import { FilterBarOrientation } from 'src/dashboard/types';
import { isNativeFilter } from 'src/dashboard/components/nativeFilters/FiltersConfigModal/utils';
import { useExploreFullscreen } from '../ExploreFullscreen';
import { EXPLORE_FILTER_BAR_TEST_ID } from '../ExploreFullscreen/Styles';

type StateWithExploreFilters = {
  explore?: {
    nativeFilterConfiguration?: (Filter | Divider)[];
  };
};

const FilterBarContainer = styled.div<{ $isFullscreen: boolean }>`
  ${({ theme, $isFullscreen }) => css`
    display: flex;
    flex: 0 0 auto;
    width: 100%;
    border-bottom: 1px solid ${theme.colorSplit};
    background: ${theme.colorBgContainer};
  `}

  /* Pin the bar to the top of the fullscreen Explore so filters stay
     reachable while scrolling a large chart. */
  ${({ $isFullscreen }) =>
    $isFullscreen &&
    css`
      position: sticky;
      top: 0;
    `}
`;

/**
 * Native filters of the dashboard the chart was opened from, rendered inside
 * Explore so the chart can be narrowed down the same way it was on the
 * dashboard. Changing a value writes to the data mask, which the Explore query
 * reads, so the chart re-runs with the new selection.
 *
 * Renders nothing when the chart was not opened from a dashboard, or that
 * dashboard has no native filters, so Explore looks exactly as before in the
 * common case.
 */
const ExploreFilterBar: FC = () => {
  const { isFullscreen } = useExploreFullscreen();

  const configuration = useSelector<
    StateWithExploreFilters,
    (Filter | Divider)[] | undefined
  >(state => state.explore?.nativeFilterConfiguration);

  const hasFilters = useMemo(
    () =>
      Boolean(configuration?.length) &&
      configuration!.some(
        filter => 'targets' in filter && isNativeFilter(filter.id),
      ),
    [configuration],
  );

  if (!hasFilters) {
    return null;
  }

  return (
    <FilterBarContainer
      $isFullscreen={isFullscreen}
      data-test={EXPLORE_FILTER_BAR_TEST_ID}
    >
      <FilterBar
        orientation={FilterBarOrientation.Horizontal}
        // Explore has no dashboard charts to wait for, and no permission to
        // edit the filter configuration the bar was inherited from.
        waitForCharts={false}
      />
    </FilterBarContainer>
  );
};

export default ExploreFilterBar;
