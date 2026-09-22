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
  Loading,
  Tag,
  Tooltip,
  Typography,
} from '@superset-ui/core/components';
import { css, useTheme } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import type { RootState } from 'src/dashboard/types';
import { summarizeQueryData } from './summarizeQueryData';

const MOH_AI_INSIGHTS_FLAG = 'MOH_AI_INSIGHTS' as FeatureFlag;

interface InsightResponse {
  insight: string;
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
}

type InsightStatus = 'idle' | 'loading' | 'error' | 'no-data';

const PROVIDER_LABELS: Record<string, string> = {
  demo: t('Demo'),
  openai: 'OpenAI',
  gemini: 'Gemini',
  claude: 'Claude',
  anthropic: 'Claude',
};

const PROVIDER_COLORS: Record<string, string> = {
  demo: 'default',
  openai: 'green',
  gemini: 'geekblue',
  claude: 'orange',
  anthropic: 'orange',
};

export const AiInsightPanel = memo(
  ({
    chartId,
    dashboardId,
    sliceName,
    width,
    height,
    inView,
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
      if (!isFeatureEnabled(MOH_AI_INSIGHTS_FLAG)) {
        setStatus('no-data');
        setInsight(null);
        return;
      }
      if (!inView) {
        return;
      }
      loadInsight();
    }, [inView, loadInsight]);

    const provider = insight?.provider ?? '';
    const providerLabel = PROVIDER_LABELS[provider] || provider || 'AI';
    const providerColor = PROVIDER_COLORS[provider] || 'default';

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
            {insight?.insight}
          </Typography.Paragraph>
          {insight?.generated_at && (
            <Typography.Text
              type="secondary"
              css={css`
                font-size: ${theme.fontSizeSM}px;
              `}
            >
              {t('Generated')}: {new Date(insight.generated_at).toLocaleString()}
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
            <Tag color={providerColor}>{providerLabel}</Tag>
          </Flex>
          <Tooltip title={t('Regenerate')}>
            <Button
              buttonStyle="link"
              disabled={status !== 'idle' && status !== 'error'}
              onClick={loadInsight}
              icon={<Icons.SyncOutlined />}
              aria-label={t('Regenerate AI insight')}
            />
          </Tooltip>
        </Flex>
        {body}
      </Flex>
    );
  },
);