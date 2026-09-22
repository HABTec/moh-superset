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
import { Tooltip } from '@superset-ui/core/components';
import { useGlobalContext } from './useGlobalContext';

const Chip = styled.div<{ $isOverride: boolean }>`
  ${({ theme, $isOverride }) => css`
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
    color: ${$isOverride ? theme.colorWarningText : theme.colorTextSecondary};
    background: ${$isOverride
      ? theme.colorWarningBg
      : theme.colorFillQuaternary};
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  `}
`;

/**
 * Shows the Period and Organisation unit a chart shows, and warns when the
 * chart does not follow a selection the user made.
 */
const ChartContextChip = ({ chartId }: { chartId: number }) => {
  const { period, orgUnit, periodOverridden, orgUnitOverridden } =
    useGlobalContext(chartId);

  const parts = [period, orgUnit].filter((part): part is string =>
    Boolean(part),
  );
  if (parts.length === 0) {
    return null;
  }

  const isOverride = periodOverridden || orgUnitOverridden;
  const chip = (
    <Chip data-test="chart-context-chip" $isOverride={isOverride}>
      {parts.join(' | ')}
    </Chip>
  );
  return isOverride ? (
    <Tooltip
      title={t(
        'This chart always shows the latest period and your own area, so it does not follow the Period or Organisation unit you selected.',
      )}
    >
      {chip}
    </Tooltip>
  ) : (
    chip
  );
};

export default ChartContextChip;
