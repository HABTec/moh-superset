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
import { getMetricLabel, QueryFormMetric } from '@superset-ui/core';

// Words that mark a label as a percentage (coverage, "(%)", "_pct", ...).
const PERCENT_PATTERN = /%|percent|coverage|\bpct\b|_pct\b/i;
// Measures that may exceed 100% legitimately, for reasons other than a
// population estimate (target achievement, spending against plan, bed
// occupancy, service use), never trigger the denominator note.
const EXCLUDED_PATTERN =
  /achievement|disburs|budget|fund|expenditure|spend|occupancy|utili[sz]ation/i;
// Columns that hold counts even on a percentage-titled chart
// (e.g. "Woredas with CBHI" on "CBHI Coverage by region").
const COUNT_PATTERN =
  /\b(number|count|cases|deaths|doses?|woredas?|facilities|population|births)\b/i;

const PERCENT_LIMIT = 100;

type Classification = 'percent' | 'count' | 'neutral';

const classify = (label: string): Classification => {
  if (EXCLUDED_PATTERN.test(label)) return 'count';
  if (PERCENT_PATTERN.test(label)) return 'percent';
  if (COUNT_PATTERN.test(label)) return 'count';
  return 'neutral';
};

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const asArray = (value: unknown): unknown[] => {
  if (value === undefined || value === null || value === '') return [];
  return Array.isArray(value) ? value : [value];
};

const safeMetricLabel = (metric: unknown): string | null => {
  try {
    return getMetricLabel(metric as QueryFormMetric);
  } catch {
    return null;
  }
};

export type PercentCheckInput = {
  sliceName?: string | null;
  formData: Record<string, unknown>;
  queriesResponse?: ({ data?: unknown } | null)[] | null;
};

/**
 * True when a percentage-type column on the chart holds a value above 100%.
 *
 * A column counts as a percentage when its own label says so, or, for
 * neutral labels such as "Performance" or "Value", when the chart title
 * does. Labels that name a count, and target-achievement measures, never
 * count. Only tabular query results are inspected; map features are skipped.
 */
export function findPercentOverHundred({
  sliceName,
  formData,
  queriesResponse,
}: PercentCheckInput): boolean {
  const titleIsPercent = classify(sliceName ?? '') === 'percent';
  if (EXCLUDED_PATTERN.test(sliceName ?? '')) {
    return false;
  }

  const metricLabels = [
    ...asArray(formData.metrics),
    ...asArray(formData.metrics_b),
    ...asArray(formData.metric),
    ...asArray(formData.percent_metrics),
  ]
    .map(safeMetricLabel)
    .filter((label): label is string => !!label);

  const dimensionNames = new Set(
    [
      ...asArray(formData.x_axis),
      ...asArray(formData.groupby),
      ...asArray(formData.groupby_b),
      ...asArray(formData.columns),
      '__timestamp',
    ].map(column =>
      typeof column === 'string'
        ? column
        : String((column as { label?: string })?.label ?? ''),
    ),
  );

  // Pivoted series are named "<metric>" or "<metric>, <group>"; with a single
  // metric they may be named after the group alone.
  const metricForColumn = (column: string): string | null => {
    const match = metricLabels.find(
      label => column === label || column.startsWith(`${label}, `),
    );
    if (match) return match;
    return metricLabels.length === 1 ? metricLabels[0] : null;
  };

  const isPercentColumn = (column: string): boolean => {
    const own = classify(column);
    if (own !== 'neutral') return own === 'percent';
    const metric = metricForColumn(column);
    const metricClass = metric ? classify(metric) : 'neutral';
    if (metricClass !== 'neutral') return metricClass === 'percent';
    return titleIsPercent;
  };

  return (queriesResponse ?? []).some(response => {
    const rows = response?.data;
    if (!Array.isArray(rows)) return false;
    const percentColumns = new Map<string, boolean>();
    return rows.some(row => {
      if (!row || typeof row !== 'object') return false;
      return Object.entries(row as Record<string, unknown>).some(
        ([column, value]) => {
          if (dimensionNames.has(column)) return false;
          const numeric = toNumber(value);
          if (numeric === null || numeric <= PERCENT_LIMIT) return false;
          if (!percentColumns.has(column)) {
            percentColumns.set(column, isPercentColumn(column));
          }
          return percentColumns.get(column) === true;
        },
      );
    });
  });
}
