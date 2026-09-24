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
import type { QueryData } from '@superset-ui/core';

export interface NumericStat {
  column: string;
  min: number;
  max: number;
  avg: number;
  count: number;
}

export interface TopValue {
  value: string;
  count: number;
}

export interface TopValues {
  column: string;
  values: TopValue[];
  total: number;
}

export type TrendDirection = 'increasing' | 'decreasing' | 'stable';

export interface Trend {
  column: string;
  direction: TrendDirection;
  start: number;
  end: number;
  firstLabel: string | null;
  lastLabel: string | null;
}

export interface ChartDataSummary {
  rowCount: number;
  columns: string[];
  numericStats: NumericStat[];
  topValues: TopValues[];
  trend: Trend | null;
  sampleRows: Record<string, unknown>[];
}

const SAMPLE_ROWS_LIMIT = 5;
const TREND_EPSILON = 0.02;
const DATE_LIKE_PATTERN = /\b(date|time|period|month|year|week)\b/i;
const NUMERIC_STRING_PATTERN = /^\s*-?\d+(\.\d+)?([eE][+-]?\d+)?\s*$/;
const LONG_VALUE_CHARS = 120;
const SAMPLE_VALUE_CHARS = 200;
const STRUCTURAL_COLUMN_PATTERN =
  /(^|[^a-z0-9])(geometry|geojson|geo_json|wkt|coordinates|shape)s?([^a-z0-9]|$)/i;

/**
 * Coerce a value to a finite number, tolerating numeric strings such as
 * `"55.0"` that some databases (e.g. ClickHouse) return for metric columns.
 * Returns null for anything that isn't a usable number.
 */
const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string' && NUMERIC_STRING_PATTERN.test(value.trim())) {
    const parsed = Number(value.trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const isStructuralColumn = (column: string): boolean =>
  STRUCTURAL_COLUMN_PATTERN.test(column);

const isDateLikeColumn = (
  column: string,
  rows: Record<string, unknown>[],
): boolean => {
  if (DATE_LIKE_PATTERN.test(column)) {
    return true;
  }
  const sample = rows
    .map(row => row[column])
    .filter(value => value !== null && value !== undefined)
    .slice(0, 20);
  if (sample.length === 0) {
    return false;
  }
  const parsed = sample.filter(
    value => typeof value === 'string' && !Number.isNaN(Date.parse(value)),
  );
  return parsed.length / sample.length >= 0.8;
};

const valueTimestamp = (value: unknown): number | null => {
  if (typeof value === 'number') {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
};

const buildTrend = (
  columns: string[],
  rows: Record<string, unknown>[],
  numericStats: NumericStat[],
): Trend | null => {
  if (rows.length < 2 || numericStats.length === 0) {
    return null;
  }
  const dateColumn = columns.find(column => isDateLikeColumn(column, rows));
  const metricColumn = numericStats[0].column;
  if (!dateColumn) {
    return null;
  }

  const ordered = rows
    .map(row => {
      const label = row[dateColumn];
      const value = toFiniteNumber(row[metricColumn]);
      if (label === null || label === undefined || value === null) {
        return null;
      }
      return {
        label: String(label),
        timestamp: valueTimestamp(label) ?? 0,
        value,
      };
    })
    .filter(
      (point): point is { label: string; timestamp: number; value: number } =>
        point !== null,
    )
    .sort((a, b) => a.timestamp - b.timestamp);

  if (ordered.length < 2) {
    return null;
  }
  const [first] = ordered;
  const last = ordered[ordered.length - 1];
  const delta = last.value - first.value;
  const magnitude = Math.max(Math.abs(first.value), Math.abs(last.value), 1);
  const direction: TrendDirection =
    delta > TREND_EPSILON * magnitude
      ? 'increasing'
      : delta < -TREND_EPSILON * magnitude
        ? 'decreasing'
        : 'stable';

  return {
    column: metricColumn,
    direction,
    start: first.value,
    end: last.value,
    firstLabel: first.label,
    lastLabel: last.label,
  };
};

const buildTopValues = (
  columns: string[],
  rows: Record<string, unknown>[],
): TopValues[] => {
  const results: TopValues[] = [];
  for (const column of columns) {
    const counts = new Map<string, number>();
    let total = 0;
    for (const row of rows) {
      const value = row[column];
      if (
        value === null ||
        value === undefined ||
        toFiniteNumber(value) !== null ||
        isDateLikeColumn(column, rows) ||
        isStructuralColumn(column) ||
        (typeof value === 'string' && value.length > LONG_VALUE_CHARS)
      ) {
        continue;
      }
      const key = String(value);
      counts.set(key, (counts.get(key) ?? 0) + 1);
      total += 1;
    }
    if (total === 0) {
      continue;
    }
    const values = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([value, count]) => ({ value, count }));
    results.push({ column, values, total });
  }
  return results.sort((a, b) => b.values[0].count - a.values[0].count);
};

/**
 * Condense `queriesResponse` (the chart's latest query results already held in
 * Redux) into a compact summary the backend can turn into an AI insight.
 * Returns null when there is nothing to summarize.
 */

const sanitizeSampleRow = (
  row: Record<string, unknown>,
): Record<string, unknown> => {
  const result: Record<string, unknown> = {};
  for (const [column, value] of Object.entries(row)) {
    if (isStructuralColumn(column)) {
      continue;
    }
    if (typeof value === 'string' && value.length > SAMPLE_VALUE_CHARS) {
      result[column] = `${value.slice(0, SAMPLE_VALUE_CHARS)}…`;
    } else {
      result[column] = value;
    }
  }
  return result;
};

export const summarizeQueryData = (
  queriesResponse: QueryData[] | null | undefined,
): ChartDataSummary | null => {
  if (!Array.isArray(queriesResponse) || queriesResponse.length === 0) {
    return null;
  }
  const [response] = queriesResponse;
  const data = response?.data;
  if (!Array.isArray(data)) {
    return null;
  }

  const rows = data as Record<string, unknown>[];
  if (rows.length === 0) {
    return null;
  }
  const columns: string[] =
    Array.isArray(response.colnames) && response.colnames.length > 0
      ? [...response.colnames]
      : rows.length > 0
        ? Object.keys(rows[0])
        : [];

  const numericStats: NumericStat[] = [];
  for (const column of columns) {
    const values = rows
      .map(row => toFiniteNumber(row[column]))
      .filter((value): value is number => value !== null);
    if (values.length === 0) {
      continue;
    }
    const total = values.reduce((sum, value) => sum + value, 0);
    numericStats.push({
      column,
      min: Math.min(...values),
      max: Math.max(...values),
      avg: total / values.length,
      count: values.length,
    });
  }

  const rowCount =
    typeof response.rowcount === 'number' && response.rowcount > 0
      ? response.rowcount
      : rows.length;
  const topValues = buildTopValues(columns, rows);
  const trend = buildTrend(columns, rows, numericStats);

  return {
    rowCount,
    columns,
    numericStats,
    topValues,
    trend,
    sampleRows: rows.slice(0, SAMPLE_ROWS_LIMIT).map(sanitizeSampleRow),
  };
};
