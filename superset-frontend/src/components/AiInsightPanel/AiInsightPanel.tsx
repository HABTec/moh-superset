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
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  FeatureFlag,
  isFeatureEnabled,
  SupersetClient,
} from '@superset-ui/core';
import {
  Button,
  Flex,
  Icons,
  List,
  Loading,
  Tooltip,
  Typography,
} from '@superset-ui/core/components';
import { css, useTheme } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import type { RootState } from 'src/dashboard/types';
import { summarizeQueryData } from './summarizeQueryData';

const MOH_AI_INSIGHTS_FLAG = 'MOH_AI_INSIGHTS' as FeatureFlag;

interface InsightResponse {
  summary: string;
  recommendation?: string;
  bullets: string[];
  provider: string;
  generated_at: string;
}

interface AiInsightPanelProps {
  chartId: number;
  dashboardId: number;
  sliceName: string;
  width: number;
  height: number;
  inView: boolean;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onOpenPopup?: () => void;
  onClose?: () => void;
  showCollapseToggle?: boolean;
}

type InsightStatus = 'idle' | 'loading' | 'error' | 'no-data';

// Chart types that render a single number/trend card (KPI "card" and
// "slider" cards) or a custom template with no narrative to summarize —
// AI insights are skipped for these.
const AI_INSIGHT_EXCLUDED_VIZ_TYPES = new Set([
  'big_number',
  'big_number_total',
  'handlebars',
]);

export const AiInsightPanel = memo(
  ({
    chartId,
    dashboardId,
    sliceName,
    width,
    height,
    inView,
    collapsed = false,
    onToggleCollapsed = () => {},
    onOpenPopup = () => {},
    onClose,
    showCollapseToggle = true,
  }: AiInsightPanelProps) => {
    const theme = useTheme();
    const [status, setStatus] = useState<InsightStatus>('loading');
    const [insight, setInsight] = useState<InsightResponse | null>(null);

    const queriesResponse = useSelector(
      (state: RootState) => state.charts[chartId]?.queriesResponse,
    );
    const vizType =
      useSelector(
        (state: RootState) => state.sliceEntities.slices[chartId]?.viz_type,
      ) || 'chart';

    const summary = useMemo(
      () => summarizeQueryData(queriesResponse),
      [queriesResponse],
    );

    const loadInsight = useCallback(async () => {
      if (!summary) {
        setInsight(null);
        setStatus('no-data');
        return;
      }
      setStatus('loading');
      try {
        const { sampleRows, ...summaryPayload } = summary;
        const { json } = await SupersetClient.post({
          endpoint: `/ai-insights/chart/${chartId}/`,
          jsonPayload: {
            chart_id: chartId,
            chart_name: sliceName || summary.columns[0] || t('Chart'),
            viz_type: vizType,
            dashboard_id: dashboardId,
            summary: summaryPayload,
            sample_rows: sampleRows,
          },
        });
        setInsight(json as InsightResponse);
        setStatus('idle');
      } catch {
        setStatus('error');
      }
    }, [chartId, dashboardId, sliceName, summary, vizType]);

    useEffect(() => {
      if (AI_INSIGHT_EXCLUDED_VIZ_TYPES.has(vizType)) {
        setStatus('no-data');
        setInsight(null);
        return;
      }
      if (!isFeatureEnabled(MOH_AI_INSIGHTS_FLAG)) {
        setStatus('no-data');
        setInsight(null);
        return;
      }
      if (!inView) {
        return;
      }
      loadInsight();
    }, [inView, loadInsight, vizType]);

    if (AI_INSIGHT_EXCLUDED_VIZ_TYPES.has(vizType)) {
      return null;
    }

    if (collapsed) {
      return (
        <Flex
          vertical
          align="center"
          data-test="ai-insight-panel"
          css={css`
            width: ${width}px;
            height: ${height}px;
            flex-shrink: 0;
            border-left: 1px solid ${theme.colorBorderSecondary};
            padding-top: ${theme.sizeUnit}px;
          `}
        >
          <Icons.BulbOutlined
            css={css`
              color: ${theme.colorPrimary};
              margin-bottom: ${theme.sizeUnit / 2}px;
            `}
          />
          <Tooltip title={t('Expand')} placement="left">
            <Button
              buttonStyle="link"
              onClick={onToggleCollapsed}
              icon={<Icons.MenuUnfoldOutlined />}
              aria-label={t('Expand AI insight panel')}
            />
          </Tooltip>
          <Tooltip title={t('Pop out chart and AI insight')} placement="left">
            <Button
              buttonStyle="link"
              onClick={onOpenPopup}
              icon={<Icons.ExpandOutlined />}
              aria-label={t('Pop out chart and AI insight')}
            />
          </Tooltip>
        </Flex>
      );
    }

    const body =
      status === 'loading' ? (
        <Flex
          justify="center"
          align="center"
          css={css`
            position: relative;
            flex: 1;
          `}
        >
          <Loading size="s" position="floating" />
        </Flex>
      ) : status === 'no-data' ? (
        <Typography.Text type="secondary">
          {t('No data available for an AI insight yet.')}
        </Typography.Text>
      ) : status === 'error' ? (
        <Flex vertical gap={8}>
          <Typography.Text type="secondary">
            {t('Could not generate the AI insight.')}
          </Typography.Text>
          <Button buttonStyle="secondary" onClick={loadInsight}>
            {t('Retry')}
          </Button>
        </Flex>
      ) : (
        <Flex vertical gap={8}>
          <Typography.Paragraph className="ai-insight-text">
            {insight?.summary}
          </Typography.Paragraph>
          {insight?.bullets?.length ? (
            <List
              size="small"
              split={false}
              dataSource={insight.bullets}
              renderItem={(item: string) => (
                <List.Item>
                  <Flex align="flex-start" gap={6}>
                    <Typography.Text
                      css={css`
                        color: ${theme.colorPrimary};
                        line-height: inherit;
                      `}
                    >
                      •
                    </Typography.Text>
                    <Typography.Text>{item}</Typography.Text>
                  </Flex>
                </List.Item>
              )}
            />
          ) : null}
          {insight?.recommendation && (
            <Typography.Paragraph className="ai-insight-text">
              <strong>{t('Recommendation')}:</strong>{' '}
              {insight.recommendation}
            </Typography.Paragraph>
          )}
          {insight?.generated_at && (
            <Typography.Text
              type="secondary"
              css={css`
                font-size: ${theme.fontSizeSM}px;
              `}
            >
              {t('Generated')}:{' '}
              {new Date(insight.generated_at).toLocaleString()}
            </Typography.Text>
          )}
        </Flex>
      );

    return (
      <Flex
        vertical
        data-test="ai-insight-panel"
        css={css`
          width: ${width}px;
          height: ${height}px;
          flex-shrink: 0;
          border-left: 1px solid ${theme.colorBorderSecondary};
          padding: ${theme.sizeUnit}px;
          overflow: auto;
        `}
      >
        <Flex
          justify="space-between"
          align="center"
          css={css`
            margin-bottom: ${theme.sizeUnit / 2}px;
          `}
        >
          <Flex align="center" gap={4}>
            <Icons.BulbOutlined
              css={css`
                color: ${theme.colorPrimary};
              `}
            />
            <Typography.Text strong>{t('AI Insight')}</Typography.Text>
          </Flex>
          <Flex align="center" gap={4}>
            {showCollapseToggle && (
              <Tooltip title={t('Collapse')}>
                <Button
                  buttonStyle="link"
                  onClick={onToggleCollapsed}
                  icon={<Icons.MenuFoldOutlined />}
                  aria-label={t('Collapse AI insight panel')}
                />
              </Tooltip>
            )}
            <Tooltip title={t('Regenerate')}>
              <Button
                buttonStyle="link"
                disabled={status !== 'idle' && status !== 'error'}
                onClick={loadInsight}
                icon={<Icons.SyncOutlined />}
                aria-label={t('Regenerate AI insight')}
              />
            </Tooltip>
            {onClose && (
              <Tooltip title={t('Close')}>
                <Button
                  buttonStyle="link"
                  onClick={onClose}
                  icon={<Icons.CloseOutlined />}
                  aria-label={t('Close AI insight popup')}
                />
              </Tooltip>
            )}
          </Flex>
        </Flex>
        {body}
      </Flex>
    );
  },
);
