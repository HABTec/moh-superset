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
import { useDispatch, useSelector } from 'react-redux';
import { css, styled, useTheme } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import { Button, Tooltip } from '@superset-ui/core/components';
import { setDirectPathToChild } from 'src/dashboard/actions/dashboardState';
import { DashboardLayout, RootState } from 'src/dashboard/types';
import { TAB_TYPE } from 'src/dashboard/util/componentTypes';
import { useDataFreshness } from 'src/filters/components/OrgUnitTree/useDataFreshness';
import { formatDataDate, getFreshnessSource } from './dataFreshness';
import { useGlobalContext } from './useGlobalContext';

const Strip = styled.div`
  ${({ theme }) => css`
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: ${theme.sizeUnit * 2}px ${theme.sizeUnit * 6}px;
    margin-bottom: ${theme.sizeUnit * 2}px;
    padding: ${theme.sizeUnit * 2}px ${theme.sizeUnit * 4}px;
    background: ${theme.colorBgContainer};
    border: 1px solid ${theme.colorBorderSecondary};
    border-radius: ${theme.borderRadiusLG}px;
  `}
`;

const Title = styled.span`
  ${({ theme }) => css`
    flex: 1 1 auto;
    min-width: 0;
    font-size: ${theme.fontSizeLG}px;
    font-weight: ${theme.fontWeightStrong};
    color: ${theme.colorPrimaryText};
  `}
`;

const Meta = styled.span`
  ${({ theme }) => css`
    display: inline-flex;
    align-items: baseline;
    gap: ${theme.sizeUnit}px;
    font-size: ${theme.fontSizeSM}px;
    color: ${theme.colorTextSecondary};

    & > strong {
      font-weight: ${theme.fontWeightStrong};
      color: ${theme.colorText};
    }
  `}
`;

const ViewChip = styled.span<{ $isDefault: boolean }>`
  ${({ theme, $isDefault }) => css`
    padding: 0 ${theme.sizeUnit * 2}px;
    border-radius: ${theme.borderRadiusLG}px;
    font-size: ${theme.fontSizeSM}px;
    color: ${$isDefault ? theme.colorTextSecondary : theme.colorWarningText};
    background: ${$isDefault
      ? theme.colorFillQuaternary
      : theme.colorWarningBg};
  `}
`;

const NOT_AVAILABLE = () => t('Not available');

type LayoutItem = DashboardLayout[string];

/** Orders tabs outermost first. */
const byDepth = (a: LayoutItem, b: LayoutItem) =>
  (a.parents?.length ?? 0) - (b.parents?.length ?? 0);

/**
 * Header for each dashboard tab: where the user is, how fresh and reliable
 * the data is, and whether the filters are on their default view.
 *
 * "Data as of" shows when the tab's data source was last updated, and
 * "Not available" for sources without an agreed update time. The Data Quality
 * status shows "Not available" until it is bound to agreed programme rules.
 */
const DashboardContextStrip = () => {
  const dispatch = useDispatch();
  const theme = useTheme();
  const layout = useSelector<RootState, DashboardLayout>(
    state => state.dashboardLayout.present,
  );
  const activeTabs = useSelector<RootState, string[]>(
    state => state.dashboardState?.activeTabs ?? [],
  );
  const editMode = useSelector<RootState, boolean>(
    state => state.dashboardState?.editMode,
  );
  const { period, orgUnit, isDefault } = useGlobalContext();

  const tabTitles = useMemo(
    () =>
      activeTabs
        .map(id => layout[id])
        .filter(item => item?.type === TAB_TYPE && item.meta?.text)
        .sort(byDepth)
        .map(item => item.meta?.text?.trim() ?? ''),
    [activeTabs, layout],
  );
  const title = tabTitles.join(' · ');

  const freshness = useDataFreshness();
  const source = getFreshnessSource(tabTitles[0]);
  const updatedAt = source ? freshness?.[source] : null;
  const dataDate = updatedAt ? formatDataDate(updatedAt) : null;

  const dataQualityTab = useMemo(() => {
    const tabs = Object.values(layout).filter(
      item =>
        item?.type === TAB_TYPE && /data quality/i.test(item.meta?.text ?? ''),
    );
    return tabs.sort(byDepth)[0];
  }, [layout]);

  if (editMode) {
    return null;
  }

  const view = [period, orgUnit].filter(Boolean).join(' · ');

  return (
    <Strip data-test="dashboard-context-strip">
      {title && <Title data-test="context-strip-title">{title}</Title>}
      <Meta data-test="data-as-of">
        {t('Data as of')}{' '}
        {dataDate ? (
          <Tooltip title={dataDate.dateTime}>
            <strong>{dataDate.date}</strong>
          </Tooltip>
        ) : (
          <strong>{NOT_AVAILABLE()}</strong>
        )}
      </Meta>
      <Meta>
        {t('Data Quality')} <strong>{NOT_AVAILABLE()}</strong>
        {dataQualityTab && !activeTabs.includes(dataQualityTab.id) && (
          <Tooltip title={t('Open the Data Quality tab')}>
            <Button
              buttonStyle="link"
              buttonSize="xsmall"
              css={css`
                padding: 0 ${theme.sizeUnit}px;
              `}
              onClick={() =>
                dispatch(
                  setDirectPathToChild([
                    ...(dataQualityTab.parents ?? []),
                    dataQualityTab.id,
                  ]),
                )
              }
            >
              {t('View DQ →')}
            </Button>
          </Tooltip>
        )}
      </Meta>
      {view && (
        <ViewChip data-test="default-view-chip" $isDefault={isDefault}>
          {isDefault ? t('Default view') : t('Custom view')}: {view}
        </ViewChip>
      )}
    </Strip>
  );
};

export default DashboardContextStrip;
