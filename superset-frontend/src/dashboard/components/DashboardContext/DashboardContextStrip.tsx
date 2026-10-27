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
import { css, styled } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import { DashboardLayout, RootState } from 'src/dashboard/types';
import { TAB_TYPE } from 'src/dashboard/util/componentTypes';
import { useDataFreshness } from 'src/filters/components/OrgUnitTree/useDataFreshness';
import {
  formatFreshnessPeriod,
  getFreshnessGrain,
  getFreshnessSource,
} from './dataFreshness';
import { useGlobalContext } from './useGlobalContext';
import { useTabContext } from './useTabContext';
import {
  formatCompletenessPeriod,
  formatContextMonth,
  formatSourceAsOf,
  TabContext,
} from './tabContext';

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

const Completeness = styled.span<{ $meetsTarget: boolean }>`
  ${({ theme, $meetsTarget }) => css`
    display: inline-flex;
    align-items: baseline;
    gap: ${theme.sizeUnit}px;
    padding: 0 ${theme.sizeUnit * 2}px;
    border-radius: ${theme.borderRadiusLG}px;
    font-size: ${theme.fontSizeSM}px;
    color: ${$meetsTarget ? theme.colorSuccessText : theme.colorWarningText};
    background: ${$meetsTarget ? theme.colorSuccessBg : theme.colorWarningBg};

    & > strong {
      font-weight: ${theme.fontWeightStrong};
    }
  `}
`;

const NOT_AVAILABLE = () => t('Not available');

/** "DHIS2 2019 EFY · Nehase · EDHS 2024" — the label only when there are several. */
function describeAsOf(context: TabContext): string {
  const { sources } = context;
  const parts = sources.map(source => {
    const asOf = formatSourceAsOf(source) ?? NOT_AVAILABLE();
    return sources.length > 1 ? `${source.label} ${asOf}` : asOf;
  });
  return parts.join(' · ');
}

function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? '–' : `${value}%`;
}

type LayoutItem = DashboardLayout[string];

/** Orders tabs outermost first. */
const byDepth = (a: LayoutItem, b: LayoutItem) =>
  (a.parents?.length ?? 0) - (b.parents?.length ?? 0);

/**
 * Header for each dashboard tab: where the user is, how fresh the data is,
 * and whether the filters are on their default view.
 *
 * "Data as of" shows when the tab's data source was last updated, and
 * "Not available" for sources without an agreed update time.
 */
const DashboardContextStrip = () => {
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

  const activeTabItems = useMemo(
    () =>
      activeTabs
        .map(id => layout[id])
        .filter(item => item?.type === TAB_TYPE && item.meta?.text)
        .sort(byDepth),
    [activeTabs, layout],
  );
  const tabTitles = useMemo(
    () => activeTabItems.map(item => item.meta?.text?.trim() ?? ''),
    [activeTabItems],
  );
  const title = tabTitles.join(' · ');
  const tabContext = useTabContext(
    tabTitles,
    activeTabItems[activeTabItems.length - 1]?.id,
  );

  const freshness = useDataFreshness();
  const source = getFreshnessSource(tabTitles[0]);
  const grain = getFreshnessGrain(tabTitles);
  const dataAsOf = source
    ? formatFreshnessPeriod(freshness?.[source]?.[grain], grain)
    : null;

  if (editMode) {
    return null;
  }

  const view = [period, orgUnit].filter(Boolean).join(' · ');
  const dhis2 = tabContext?.sources.find(source => source.kind === 'dhis2');
  const inProgress = dhis2?.inProgress;
  const completeness = tabContext?.completeness;

  return (
    <Strip data-test="dashboard-context-strip">
      {title && <Title data-test="context-strip-title">{title}</Title>}
      {tabContext ? (
        <>
          <Meta data-test="context-source">
            {t('Source')}{' '}
            <strong>
              {tabContext.sources.map(source => source.label).join(' · ')}
            </strong>
          </Meta>
          <Meta data-test="data-as-of">
            {t('Data as of')} <strong>{describeAsOf(tabContext)}</strong>
          </Meta>
          {inProgress && inProgress.completeness !== null && (
            <Meta data-test="in-progress-month">
              {t(
                '%s: %s received so far',
                formatContextMonth(inProgress) ?? inProgress.period,
                formatPercent(inProgress.completeness),
              )}
            </Meta>
          )}
          {completeness && completeness.value !== null && (
            <Completeness
              data-test="reporting-completeness"
              $meetsTarget={completeness.meetsTarget}
              title={t(
                'Reports received ÷ reports expected for the forms behind this tab, %s. On time: received by the deadline ÷ expected.',
                formatCompletenessPeriod(completeness) ?? '',
              )}
            >
              {t('Reporting completeness')}{' '}
              <strong>{formatPercent(completeness.value)}</strong>
              {' · '}
              {t('on time %s', formatPercent(completeness.timeliness))}
              {' · '}
              {formatCompletenessPeriod(completeness)}
              {' · '}
              {completeness.meetsTarget
                ? t('on target')
                : t('below %s target', `${completeness.target}%`)}
            </Completeness>
          )}
        </>
      ) : (
        <Meta data-test="data-as-of">
          {t('Data as of')} <strong>{dataAsOf ?? NOT_AVAILABLE()}</strong>
        </Meta>
      )}
      {view && (
        <ViewChip data-test="default-view-chip" $isDefault={isDefault}>
          {isDefault ? t('Default view') : t('Custom view')}: {view}
        </ViewChip>
      )}
    </Strip>
  );
};

export default DashboardContextStrip;
