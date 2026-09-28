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
import { forwardRef, MouseEvent, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { t } from '@apache-superset/core/translation';
import { css, styled } from '@apache-superset/core/theme';
import { Icons } from '@superset-ui/core/components';
import { setDirectPathToChild } from 'src/dashboard/actions/dashboardState';
import { RootState } from 'src/dashboard/types';

/**
 * Where the denominator explanation lives: the "Adjusted Denominator" tab of
 * the MOH Performance Monitoring dashboard.
 */
export const ADJUSTED_DENOMINATOR_DASHBOARD_ID = 3;
export const ADJUSTED_DENOMINATOR_TAB_ID = 'TAB-CQ5zK7H3f00PK4e-ASH7M';
export const ADJUSTED_DENOMINATOR_URL = `/superset/dashboard/${ADJUSTED_DENOMINATOR_DASHBOARD_ID}/#${ADJUSTED_DENOMINATOR_TAB_ID}`;

const Footer = styled.div`
  ${({ theme }) => css`
    display: flex;
    align-items: flex-start;
    gap: ${theme.sizeUnit}px;
    margin-top: ${theme.sizeUnit}px;
    padding: ${theme.sizeUnit}px ${theme.sizeUnit * 2}px;
    border-radius: ${theme.borderRadiusLG}px;
    font-size: ${theme.fontSizeSM}px;
    line-height: ${theme.lineHeightSM};
    color: ${theme.colorTextSecondary};
    background: ${theme.colorFillQuaternary};

    .anticon {
      margin-top: 2px;
      color: ${theme.colorInfo};
    }
  `}
`;

/**
 * Explains coverage values above 100% under a chart: they come from
 * population estimates (denominators) lower than the number of people
 * actually served. Links to the Adjusted Denominator tab; when that tab is
 * on the open dashboard it is switched to in place.
 */
const ChartFooter = forwardRef<HTMLDivElement>((_, ref) => {
  const dispatch = useDispatch();
  const dashboardId = useSelector(
    (state: RootState) => state.dashboardInfo?.id,
  );
  const layout = useSelector(
    (state: RootState) => state.dashboardLayout?.present,
  );

  const handleClick = useCallback(
    (event: MouseEvent<HTMLAnchorElement>) => {
      if (dashboardId !== ADJUSTED_DENOMINATOR_DASHBOARD_ID) return;
      const tab = layout?.[ADJUSTED_DENOMINATOR_TAB_ID];
      if (!tab) return;
      event.preventDefault();
      dispatch(
        setDirectPathToChild([
          ...(tab.parents ?? []),
          ADJUSTED_DENOMINATOR_TAB_ID,
        ]),
      );
    },
    [dashboardId, dispatch, layout],
  );

  return (
    <Footer ref={ref} data-test="chart-footer" role="note">
      <Icons.InfoCircleOutlined iconSize="s" aria-hidden />
      <span>
        {t(
          'Some values exceed 100%. Population estimates (denominators) can be lower than the number of people served.',
        )}{' '}
        <a href={ADJUSTED_DENOMINATOR_URL} onClick={handleClick}>
          {t('See Adjusted Denominator')}
        </a>
      </span>
    </Footer>
  );
});

export default ChartFooter;
export { findPercentOverHundred } from './findPercentOverHundred';
