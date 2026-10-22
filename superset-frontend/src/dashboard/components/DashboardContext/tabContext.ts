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
import { t } from '@apache-superset/core/translation';
import {
  DataMaskStateWithId,
  ensureIsArray,
  Filter,
  JsonObject,
} from '@superset-ui/core';
import { DashboardLayout } from 'src/dashboard/types';
import { CHART_TYPE } from 'src/dashboard/util/componentTypes';
import { FreshnessPeriod } from 'src/filters/components/OrgUnitTree/useDataFreshness';
import { formatFreshnessPeriod } from './dataFreshness';

/** Org Unit tree filter columns (see OrgUnitTreeFilter's LEVEL_TO_DIM). */
const ORG_UNIT_COLUMNS = ['region', 'zone', 'woreda', 'phcu', 'health_post'];

/** Chart filters that say which DHIS2 data a chart shows. */
const CHART_FIELDS = [
  'indicators',
  'indicatorIds',
  'dataElements',
  'dataElementIds',
] as const;
type ChartField = (typeof CHART_FIELDS)[number];

const isChartField = (field: string | undefined): field is ChartField =>
  (CHART_FIELDS as readonly string[]).includes(field ?? '');

/** Filter column → request field the context endpoint understands. */
const FILTER_FIELDS: Record<string, keyof TabContextSelections> = {
  indicator: 'indicators',
  indicator_id: 'indicatorIds',
  data_element: 'dataElements',
  data_element_id: 'dataElementIds',
  data_set_name: 'dataSets',
  fiscal_year: 'fiscalYears',
  quarter: 'quarters',
  quarter_name: 'quarters',
  month_name: 'months',
};

export type TabContextSelections = {
  indicators: string[];
  indicatorIds: string[];
  dataElements: string[];
  dataElementIds: string[];
  dataSets: string[];
  fiscalYears: string[];
  quarters: string[];
  months: string[];
  orgUnits: Record<string, string[]>;
};

export type TabContextPeriod = Pick<
  FreshnessPeriod,
  'period' | 'fiscalYear' | 'monthName' | 'quarterName'
>;

export type TabContextSource = {
  key: string;
  label: string;
  kind: 'dhis2' | 'annual' | 'snapshot';
  latest?: string | null;
  latestPeriod?: TabContextPeriod | null;
  inProgress?: (TabContextPeriod & { completeness: number | null }) | null;
  basis?: 'latest_data';
};

export type TabCompleteness = {
  value: number | null;
  timeliness: number | null;
  months: number;
  from: TabContextPeriod;
  to: TabContextPeriod;
  includesInProgress: boolean;
  target: number;
  meetsTarget: boolean;
};

export type TabContext = {
  sources: TabContextSource[];
  completeness: TabCompleteness | null;
};

const emptySelections = (): TabContextSelections => ({
  indicators: [],
  indicatorIds: [],
  dataElements: [],
  dataElementIds: [],
  dataSets: [],
  fiscalYears: [],
  quarters: [],
  months: [],
  orgUnits: {},
});

function addValues(target: string[], values: unknown) {
  ensureIsArray(values).forEach(value => {
    if (value === null || value === undefined) return;
    const text = String(value);
    if (text.trim() && !target.includes(text)) {
      target.push(text);
    }
  });
}

/** Ids of the charts on the innermost active tab (or every chart without tabs). */
export function getActiveTabChartIds(
  layout: DashboardLayout,
  innermostTabId: string | undefined,
): number[] {
  return Object.values(layout)
    .filter(
      item =>
        item?.type === CHART_TYPE &&
        item.meta?.chartId !== undefined &&
        (!innermostTabId || item.parents?.includes(innermostTabId)),
    )
    .map(item => item.meta.chartId as number);
}

/**
 * What the tab's charts and in-scope filters say the tab is about: the
 * indicators each chart filters on, plus the selected values of filters on
 * indicator, data element, dataset, period and org unit columns.
 */
export function collectTabSelections({
  chartFormData,
  filters,
  dataMask,
}: {
  chartFormData: (JsonObject | undefined)[];
  filters: Filter[];
  dataMask: DataMaskStateWithId;
}): TabContextSelections {
  const selections = emptySelections();

  chartFormData.forEach(formData => {
    ensureIsArray(formData?.adhoc_filters).forEach((adhoc: JsonObject) => {
      const field = FILTER_FIELDS[adhoc?.subject];
      if (
        adhoc?.expressionType === 'SIMPLE' &&
        adhoc?.clause !== 'HAVING' &&
        isChartField(field) &&
        ['IN', '=='].includes(String(adhoc.operator))
      ) {
        addValues(selections[field], adhoc.comparator);
      }
    });
  });

  filters.forEach(filter => {
    const mask = dataMask[filter.id];
    if (filter.filterType === 'filter_org_unit_tree') {
      ensureIsArray(mask?.extraFormData?.filters).forEach(clause => {
        const column = String(clause?.col ?? '');
        if (ORG_UNIT_COLUMNS.includes(column)) {
          selections.orgUnits[column] = selections.orgUnits[column] ?? [];
          addValues(
            selections.orgUnits[column],
            'val' in clause ? clause.val : undefined,
          );
        }
      });
      return;
    }
    const column = filter.targets?.[0]?.column?.name;
    const field = column ? FILTER_FIELDS[column] : undefined;
    if (field && field !== 'orgUnits') {
      addValues(selections[field] as string[], mask?.filterState?.value);
    }
  });

  return selections;
}

/** "2019 EFY · Nehase", or null when the month is unknown. */
export function formatContextMonth(
  period: TabContextPeriod | null | undefined,
): string | null {
  if (!period) return null;
  return formatFreshnessPeriod(
    { ...period, quarter: 0, quarterName: period.quarterName ?? null },
    'monthly',
  );
}

/** How current one source is, e.g. "2019 EFY · Nehase" or "2024". */
export function formatSourceAsOf(source: TabContextSource): string | null {
  if (source.kind === 'dhis2') {
    return formatContextMonth(source.latestPeriod);
  }
  if (!source.latest) return null;
  return source.kind === 'snapshot'
    ? t('updated %s', source.latest)
    : source.latest;
}

/** The months a completeness figure covers, e.g. "Hamle–Meskerem 2019 EFY". */
export function formatCompletenessPeriod(
  completeness: TabCompleteness,
): string | null {
  const { from, to, months } = completeness;
  if (months <= 1 || from.period === to.period) {
    return formatContextMonth(to);
  }
  const toLabel = formatContextMonth(to);
  if (from.fiscalYear === to.fiscalYear && from.monthName && toLabel) {
    // Same year: "2019 EFY · Hamle–Meskerem"
    return toLabel.replace(
      ` · ${to.monthName}`,
      ` · ${from.monthName}–${to.monthName}`,
    );
  }
  const fromLabel = formatContextMonth(from);
  return fromLabel && toLabel ? `${fromLabel} – ${toLabel}` : toLabel;
}
