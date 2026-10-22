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
import {
  ensureIsArray,
  getMetricLabel,
  JsonObject,
  QueryFormMetric,
} from '@superset-ui/core';

/** Form-data keys that hold the measures a chart plots. */
const METRIC_KEYS = [
  'metric',
  'metrics',
  'metric_2',
  'metrics_b',
  'percent_metrics',
] as const;

function isMetric(value: unknown): value is QueryFormMetric {
  return (
    (typeof value === 'string' && value !== '') ||
    (typeof value === 'object' &&
      value !== null &&
      ('expressionType' in value || 'label' in value))
  );
}

function getMetricLabels(formData: JsonObject): string[] {
  const labels = new Set<string>();
  METRIC_KEYS.forEach(key =>
    ensureIsArray(formData[key]).forEach(metric => {
      if (isMetric(metric)) {
        labels.add(getMetricLabel(metric));
      }
    }),
  );
  return [...labels];
}

function isPresent(value: unknown): boolean {
  return (
    value !== null &&
    value !== undefined &&
    value !== '' &&
    !(typeof value === 'number' && !Number.isFinite(value))
  );
}

/**
 * A row tells the reader something when at least one measure has a value —
 * except a zero measure on a row with no category at all (e.g. COUNT(col)
 * grouped by a column that is NULL everywhere), which only draws a
 * meaningless "<NULL>" slice or bar.
 */
function isInformativeRow(row: JsonObject, metricLabels: string[]): boolean {
  const values = metricLabels.map(label => row[label]);
  if (!values.some(isPresent)) {
    return false;
  }
  const dimensionKeys = Object.keys(row).filter(
    key => !metricLabels.includes(key),
  );
  const hasNoCategory =
    dimensionKeys.length > 0 &&
    dimensionKeys.every(key => !isPresent(row[key]));
  return !(
    hasNoCategory && values.every(value => !isPresent(value) || value === 0)
  );
}

function getRows(data: unknown): JsonObject[] | null {
  if (Array.isArray(data)) {
    return data as JsonObject[];
  }
  // deck.gl layers return GeoJSON-like `{ features: [...] }`, one feature per row.
  const features = (data as JsonObject | null | undefined)?.features;
  return Array.isArray(features) ? (features as JsonObject[]) : null;
}

/**
 * True when a chart's queries returned rows but none of them carry a real
 * measure — the case where a dataset always emits rows (e.g. map shapes)
 * and the measures for the selected filters are all NULL. Such results
 * otherwise render as a "No data" figure, an empty map or a "<NULL>" slice
 * that looks like a genuine result.
 *
 * Errs towards false: anything it cannot judge (no metrics, unknown payload
 * shape, measures not found in the rows) is left to the chart to draw.
 * Queries with no rows at all are handled by SuperChart's own no-results
 * check and do not count as judged here.
 */
export default function hasNoValidData(
  queriesData: unknown,
  formData: JsonObject,
): boolean {
  const metricLabels = getMetricLabels(formData);
  if (metricLabels.length === 0) {
    return false;
  }

  let judged = false;
  for (const query of ensureIsArray(queriesData) as JsonObject[]) {
    const rows = getRows(query?.data);
    if (rows === null) {
      return false;
    }
    if (rows.length > 0) {
      const presentLabels = metricLabels.filter(label =>
        rows.some(row => row && label in row),
      );
      if (presentLabels.length === 0) {
        return false;
      }
      judged = true;
      if (rows.some(row => row && isInformativeRow(row, presentLabels))) {
        return false;
      }
    }
  }
  return judged;
}
