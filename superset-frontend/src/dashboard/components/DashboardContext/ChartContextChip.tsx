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
import { css, styled } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import { useChartSourceContext, useGlobalContext } from './useGlobalContext';

const Chip = styled.div`
  ${({ theme }) => css`
    display: inline-flex;
    flex: 0 0 100%;
    order: 3;
    align-items: center;
    gap: ${theme.sizeUnit}px;
    max-width: 100%;
    margin-top: ${theme.sizeUnit}px;
    padding: 0 ${theme.sizeUnit * 2}px;
    border-radius: ${theme.borderRadiusLG}px;
    font-size: ${theme.fontSizeSM}px;
    font-weight: ${theme.fontWeightNormal};
    color: ${theme.colorTextSecondary};
    background: ${theme.colorFillQuaternary};
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  `}
`;

/**
 * Shows the Period and Organisation unit a chart is filtered by, followed by
 * its data source and data-as-of when the chart's tab has a known source.
 * The chip sits inside the chart box, so image exports carry it too.
 * Renders nothing when neither filter reaches this chart — that source has
 * no period or org unit dimension to report.
 */
const ChartContextChip = ({ chartId }: { chartId: number }) => {
  const { period, orgUnit } = useGlobalContext(chartId);
  const { source, dataAsOf } = useChartSourceContext(chartId);

  const parts = [period, orgUnit].filter((part): part is string =>
    Boolean(part),
  );
  if (parts.length === 0) {
    return null;
  }
  if (source) {
    parts.push(dataAsOf ? t('%s · data as of %s', source, dataAsOf) : source);
  }
  const text = parts.join(' | ');

  // The chip truncates on narrow charts; the tooltip keeps the full text.
  return (
    <Chip data-test="chart-context-chip" title={text}>
      {text}
    </Chip>
  );
};

export default ChartContextChip;
