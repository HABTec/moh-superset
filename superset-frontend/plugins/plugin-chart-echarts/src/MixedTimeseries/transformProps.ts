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
/* eslint-disable camelcase */
import { invert } from 'lodash';
import {
  AnnotationLayer,
  AxisType,
  buildCustomFormatters,
  CategoricalColorNamespace,
  CurrencyFormatter,
  ensureIsArray,
  getCustomFormatter,
  getNumberFormatter,
  getXAxisLabel,
  isDefined,
  isEventAnnotationLayer,
  isFormulaAnnotationLayer,
  isIntervalAnnotationLayer,
  isPhysicalColumn,
  isTimeseriesAnnotationLayer,
  QueryFormData,
  QueryFormMetric,
  resolveAutoCurrency,
  TimeseriesChartDataResponseResult,
  TimeseriesDataRecord,
  tooltipHtml,
  ValueFormatter,
} from '@superset-ui/core';
import { GenericDataType } from '@apache-superset/core/common';
import { getOriginalSeries } from '@superset-ui/chart-controls';
import type { EChartsCoreOption } from 'echarts/core';
import type { SeriesOption } from 'echarts';
import {
  DEFAULT_FORM_DATA,
  EchartsMixedTimeseriesChartTransformedProps,
  EchartsMixedTimeseriesFormData,
  EchartsMixedTimeseriesProps,
} from './types';
import {
  EchartsTimeseriesSeriesType,
  ForecastSeriesEnum,
  LegendOrientation,
  Refs,
} from '../types';
import { parseAxisBound } from '../utils/controls';
import { safeParseEChartOptions } from '../utils/safeEChartOptionsParser';
import {
  dedupSeries,
  extractDataTotalValues,
  extractSeries,
  extractShowValueIndexes,
  extractTooltipKeys,
  getAxisType,
  getColtypesMapping,
  getHorizontalLegendAvailableWidth,
  getLegendDataWithTooltip,
  getLegendProps,
  getMinAndMaxFromBounds,
  getOverMaxHiddenFormatter,
} from '../utils/series';
import { resolveLegendLayout } from '../utils/legendLayout';
import {
  extractAnnotationLabels,
  getAnnotationData,
} from '../utils/annotation';
import {
  extractForecastSeriesContext,
  extractForecastValuesFromTooltipParams,
  formatForecastTooltipSeries,
  rebaseForecastDatum,
  reorderForecastSeries,
} from '../utils/forecast';
import { convertInteger } from '../utils/convertInteger';
import { defaultGrid, defaultYAxis } from '../defaults';
import {
  getPadding,
  transformEventAnnotation,
  transformFormulaAnnotation,
  transformIntervalAnnotation,
  transformSeries,
  transformTimeseriesAnnotation,
} from '../Timeseries/transformers';
import { TIMEGRAIN_TO_TIMESTAMP, TIMESERIES_CONSTANTS } from '../constants';
import { getDefaultTooltip } from '../utils/tooltip';
import {
  getTooltipTimeFormatter,
  getXAxisFormatter,
  getYAxisFormatter,
} from '../utils/formatters';
import { getMetricDisplayName } from '../utils/metricDisplayName';
import { mergeCustomEChartOptions } from '../utils/mergeCustomEChartOptions';

const getFormatter = (
  customFormatters: Record<string, ValueFormatter>,
  defaultFormatter: ValueFormatter,
  metrics: QueryFormMetric[],
  formatterKey: string,
  forcePercentFormat: boolean,
) => {
  if (forcePercentFormat) {
    return getNumberFormatter(',.0%');
  }
  return (
    getCustomFormatter(customFormatters, metrics, formatterKey) ??
    defaultFormatter
  );
};

const COMPACT_MIXED_CHART_WIDTH = 420;
const CROWDED_BAR_LABEL_THRESHOLD = 10;
const COMPACT_BAR_LABEL_GRID_GUTTER = 48;
const COMPACT_BAR_LABEL_WIDTH_PER_CHAR = 7;
const COMPACT_BAR_LABEL_GAP = 2;

const getMaxSeriesDataLength = (chartSeries: SeriesOption[]) =>
  chartSeries.reduce(
    (maxLength, entry) =>
      Math.max(maxLength, Array.isArray(entry.data) ? entry.data.length : 0),
    0,
  );

const getNumericDatumValue = (
  datum: unknown,
  valueIndex: number,
): number | undefined => {
  const getNumericValue = (value: unknown) => {
    const numericValue = Array.isArray(value) ? value[valueIndex] : value;
    return typeof numericValue === 'number' && Number.isFinite(numericValue)
      ? numericValue
      : undefined;
  };

  if (Array.isArray(datum)) {
    return getNumericValue(datum);
  }

  if (datum && typeof datum === 'object' && 'value' in datum) {
    return getNumericValue((datum as { value?: unknown }).value);
  }

  return getNumericValue(datum);
};

const getCompactBarValueLabelLength = (value: number) => {
  const roundedValue = Number.isInteger(value)
    ? value
    : Number(value.toFixed(Math.abs(value) >= 100 ? 1 : 2));
  return String(roundedValue).length;
};

const getMaxCompactBarValueLabelLength = (
  chartSeries: SeriesOption[],
  valueIndex: number,
) =>
  chartSeries.reduce((maxLength, entry) => {
    if (!Array.isArray(entry.data)) {
      return maxLength;
    }

    return entry.data.reduce((seriesMaxLength, datum) => {
      const value = getNumericDatumValue(datum, valueIndex);
      return value === undefined
        ? seriesMaxLength
        : Math.max(seriesMaxLength, getCompactBarValueLabelLength(value));
    }, maxLength);
  }, 0);

const shouldRotateCompactBarValueLabels = (
  chartWidth: number,
  categoryCount: number,
  seriesCount: number,
  maxLabelLength: number,
) => {
  const labelCount = categoryCount * Math.max(seriesCount, 1);
  if (labelCount < CROWDED_BAR_LABEL_THRESHOLD || maxLabelLength === 0) {
    return false;
  }

  const availableWidth = Math.max(
    1,
    chartWidth - COMPACT_BAR_LABEL_GRID_GUTTER,
  );
  const labelSlotWidth = availableWidth / labelCount;
  const estimatedLabelWidth = maxLabelLength * COMPACT_BAR_LABEL_WIDTH_PER_CHAR;

  return estimatedLabelWidth + COMPACT_BAR_LABEL_GAP > labelSlotWidth;
};

export default function transformProps(
  chartProps: EchartsMixedTimeseriesProps,
): EchartsMixedTimeseriesChartTransformedProps {
  const {
    width,
    height,
    formData: { echartOptions: _echartOptions, ...formData },
    queriesData,
    hooks,
    filterState,
    datasource,
    theme,
    inContextMenu,
    emitCrossFilters,
    legendState,
  } = chartProps;

  let focusedSeries: string | null = null;

  const {
    verboseMap = {},
    currencyFormats = {},
    columnFormats = {},
    currencyCodeColumn,
  } = datasource;
  const { label_map: labelMap, detected_currency: backendDetectedCurrency } =
    queriesData[0] as TimeseriesChartDataResponseResult;
  const { label_map: labelMapB, detected_currency: backendDetectedCurrencyB } =
    queriesData[1] as TimeseriesChartDataResponseResult;
  const data1 = (queriesData[0].data || []) as TimeseriesDataRecord[];
  const data2 = (queriesData[1].data || []) as TimeseriesDataRecord[];
  const annotationData = getAnnotationData(chartProps);
  const coltypeMapping = {
    ...getColtypesMapping(queriesData[0]),
    ...getColtypesMapping(queriesData[1]),
  };
  const {
    area,
    areaB,
    annotationLayers,
    colorScheme,
    timeShiftColor,
    contributionMode,
    legendOrientation,
    legendMargin,
    legendType,
    legendSort,
    logAxis,
    logAxisSecondary,
    markerEnabled,
    markerEnabledB,
    markerSize,
    markerSizeB,
    opacity,
    opacityB,
    minorSplitLine,
    minorTicks,
    seriesType,
    seriesTypeB,
    showLegend,
    showValue,
    showValueB,
    onlyTotal,
    onlyTotalB,
    stack,
    stackB,
    truncateXAxis,
    truncateYAxis,
    tooltipTimeFormat,
    yAxisFormat,
    currencyFormat,
    yAxisFormatSecondary,
    currencyFormatSecondary,
    xAxisTimeFormat,
    yAxisBounds,
    yAxisBoundsSecondary,
    yAxisIndex,
    yAxisIndexB,
    yAxisTitleSecondary,
    zoomable,
    richTooltip,
    tooltipSortByMetric,
    xAxisBounds,
    xAxisLabelRotation,
    xAxisLabelInterval,
    groupby,
    groupbyB,
    xAxis: xAxisOrig,
    xAxisForceCategorical,
    xAxisTitle,
    yAxisTitle,
    xAxisTitleMargin,
    yAxisTitleMargin,
    yAxisTitlePosition,
    sliceId,
    sortSeriesType,
    sortSeriesTypeB,
    sortSeriesAscending,
    sortSeriesAscendingB,
    timeGrainSqla,
    forceMaxInterval,
    percentageThreshold,
    showQueryIdentifiers = false,
    metrics = [],
    metricsB = [],
  }: EchartsMixedTimeseriesFormData = { ...DEFAULT_FORM_DATA, ...formData };

  const refs: Refs = {};
  const colorScale = CategoricalColorNamespace.getScale(colorScheme as string);

  let xAxisLabel = getXAxisLabel(
    chartProps.rawFormData as QueryFormData,
  ) as string;
  if (
    isPhysicalColumn(chartProps.rawFormData?.x_axis) &&
    isDefined(verboseMap[xAxisLabel])
  ) {
    xAxisLabel = verboseMap[xAxisLabel];
  }

  const rebasedDataA = rebaseForecastDatum(data1, verboseMap);
  const { totalStackedValues, thresholdValues } = extractDataTotalValues(
    rebasedDataA,
    {
      stack,
      percentageThreshold,
      xAxisCol: xAxisLabel,
    },
  );

  const MetricDisplayNameA: string =
    getMetricDisplayName(metrics[0], verboseMap) || '';
  const MetricDisplayNameB: string =
    getMetricDisplayName(metricsB[0], verboseMap) || '';

  const dataTypes = getColtypesMapping(queriesData[0]);
  const xAxisDataType = dataTypes?.[xAxisLabel] ?? dataTypes?.[xAxisOrig];
  const xAxisType = getAxisType(
    stack,
    xAxisForceCategorical,
    xAxisDataType,
    seriesType === EchartsTimeseriesSeriesType.Bar ||
      seriesTypeB === EchartsTimeseriesSeriesType.Bar
      ? EchartsTimeseriesSeriesType.Bar
      : seriesType,
  );

  const [rawSeriesA, sortedTotalValuesA] = extractSeries(rebasedDataA, {
    fillNeighborValue: stack ? 0 : undefined,
    xAxis: xAxisLabel,
    sortSeriesType,
    sortSeriesAscending,
    stack,
    totalStackedValues,
    xAxisType,
  });
  const rebasedDataB = rebaseForecastDatum(data2, verboseMap);
  const {
    totalStackedValues: totalStackedValuesB,
    thresholdValues: thresholdValuesB,
  } = extractDataTotalValues(rebasedDataB, {
    stack: Boolean(stackB),
    percentageThreshold,
    xAxisCol: xAxisLabel,
  });
  const [rawSeriesB, sortedTotalValuesB] = extractSeries(rebasedDataB, {
    fillNeighborValue: stackB ? 0 : undefined,
    xAxis: xAxisLabel,
    sortSeriesType: sortSeriesTypeB,
    sortSeriesAscending: sortSeriesAscendingB,
    stack: Boolean(stackB),
    totalStackedValues: totalStackedValuesB,
    xAxisType,
  });
  const series: SeriesOption[] = [];
  const barSeriesCount =
    Number(seriesType === EchartsTimeseriesSeriesType.Bar) +
    Number(seriesTypeB === EchartsTimeseriesSeriesType.Bar);
  const categoryCount = Math.max(
    getMaxSeriesDataLength(rawSeriesA),
    getMaxSeriesDataLength(rawSeriesB),
  );
  const compactMobileMixedChart = width <= COMPACT_MIXED_CHART_WIDTH;
  const useAxisTooltip = richTooltip || compactMobileMixedChart;
  const compactMobileMixedBarChart =
    compactMobileMixedChart && barSeriesCount > 0;
  const compactMobileMixedLineChart =
    compactMobileMixedChart && barSeriesCount === 0;
  const hideCompactSecondaryAxisLabels =
    compactMobileMixedChart && !yAxisTitleSecondary;
  const barValueLabelSeriesCount =
    (seriesType === EchartsTimeseriesSeriesType.Bar ? rawSeriesA.length : 0) +
    (seriesTypeB === EchartsTimeseriesSeriesType.Bar ? rawSeriesB.length : 0);
  const maxBarValueLabelLength = Math.max(
    seriesType === EchartsTimeseriesSeriesType.Bar
      ? getMaxCompactBarValueLabelLength(rawSeriesA, 1)
      : 0,
    seriesTypeB === EchartsTimeseriesSeriesType.Bar
      ? getMaxCompactBarValueLabelLength(rawSeriesB, 1)
      : 0,
  );
  const rotateCrowdedBarLabels =
    compactMobileMixedBarChart &&
    shouldRotateCompactBarValueLabels(
      width,
      categoryCount,
      Math.max(barValueLabelSeriesCount, barSeriesCount),
      maxBarValueLabelLength,
    );
  const crowdedBarValueLabel = rotateCrowdedBarLabels
    ? {
        rotate: 90,
        align: 'left' as const,
        verticalAlign: 'middle' as const,
        distance: 4,
        fontSize: 10,
      }
    : undefined;
  const crowdedBarValueLabelLayout = rotateCrowdedBarLabels
    ? {
        rotate: 90,
        align: 'left' as const,
        verticalAlign: 'middle' as const,
        dy: -2,
      }
    : undefined;

  const resolvedCurrency = resolveAutoCurrency(
    currencyFormat,
    backendDetectedCurrency,
    data1,
    currencyCodeColumn,
  );
  const resolvedCurrencySecondary = resolveAutoCurrency(
    currencyFormatSecondary,
    backendDetectedCurrencyB,
    data2,
    currencyCodeColumn,
  );

  const formatter = contributionMode
    ? getNumberFormatter(',.0%')
    : resolvedCurrency?.symbol
      ? new CurrencyFormatter({
          d3Format: yAxisFormat,
          currency: resolvedCurrency,
        })
      : getNumberFormatter(yAxisFormat);
  const formatterSecondary = contributionMode
    ? getNumberFormatter(',.0%')
    : resolvedCurrencySecondary?.symbol
      ? new CurrencyFormatter({
          d3Format: yAxisFormatSecondary,
          currency: resolvedCurrencySecondary,
        })
      : getNumberFormatter(yAxisFormatSecondary);
  const customFormatters = buildCustomFormatters(
    [...ensureIsArray(metrics), ...ensureIsArray(metricsB)],
    currencyFormats,
    columnFormats,
    yAxisFormat,
    resolvedCurrency,
    data1,
    currencyCodeColumn,
  );
  const customFormattersSecondary = buildCustomFormatters(
    [...ensureIsArray(metrics), ...ensureIsArray(metricsB)],
    currencyFormats,
    columnFormats,
    yAxisFormatSecondary,
    resolvedCurrencySecondary,
    data2,
    currencyCodeColumn,
  );

  const primarySeries = new Set<string>();
  const secondarySeries = new Set<string>();
  const mapSeriesIdToAxis = (
    seriesOption: SeriesOption,
    index?: number,
  ): void => {
    if (index === 1) {
      secondarySeries.add(seriesOption.id as string);
    } else {
      primarySeries.add(seriesOption.id as string);
    }
  };
  const showValueIndexesA = extractShowValueIndexes(rawSeriesA, {
    stack,
    onlyTotal,
  });
  const showValueIndexesB = extractShowValueIndexes(rawSeriesB, {
    stack,
    onlyTotal,
  });

  annotationLayers
    .filter((layer: AnnotationLayer) => layer.show)
    .forEach((layer: AnnotationLayer) => {
      if (isFormulaAnnotationLayer(layer))
        series.push(
          transformFormulaAnnotation(
            layer,
            rebasedDataA as TimeseriesDataRecord[],
            xAxisLabel,
            xAxisType,
            colorScale,
            sliceId,
          ),
        );
      else if (isIntervalAnnotationLayer(layer)) {
        series.push(
          ...transformIntervalAnnotation(
            layer,
            data1,
            annotationData,
            colorScale,
            theme,
            sliceId,
          ),
        );
      } else if (isEventAnnotationLayer(layer)) {
        series.push(
          ...transformEventAnnotation(
            layer,
            data1,
            annotationData,
            colorScale,
            theme,
            sliceId,
          ),
        );
      } else if (isTimeseriesAnnotationLayer(layer)) {
        series.push(
          ...transformTimeseriesAnnotation(
            layer,
            markerSize,
            data1,
            annotationData,
            colorScale,
            sliceId,
          ),
        );
      }
    });

  // yAxisBounds need to be parsed to replace incompatible values with undefined
  const [xAxisMin, xAxisMax] = (xAxisBounds || []).map(parseAxisBound);
  let [yAxisMin, yAxisMax] = (yAxisBounds || []).map(parseAxisBound);
  let [minSecondary, maxSecondary] = (yAxisBoundsSecondary || []).map(
    parseAxisBound,
  );

  const array = ensureIsArray(chartProps.rawFormData?.time_compare);
  const inverted = invert(verboseMap);

  rawSeriesA.forEach(entry => {
    const entryName = String(entry.name || '');
    const seriesName = inverted[entryName] || entryName;
    const colorScaleKey = getOriginalSeries(seriesName, array);

    let displayName: string;

    if (groupby.length > 0) {
      // When we have groupby, format as "metric, dimension"
      const metricPart: string = showQueryIdentifiers
        ? `${MetricDisplayNameA} (Query A)`
        : MetricDisplayNameA;
      displayName = entryName.includes(metricPart)
        ? entryName
        : `${metricPart}, ${entryName}`;
    } else {
      // When no groupby, format as just the entry name with optional query identifier
      displayName = showQueryIdentifiers ? `${entryName} (Query A)` : entryName;
    }

    const seriesFormatter = getFormatter(
      customFormatters,
      formatter,
      metrics,
      labelMap?.[seriesName]?.[0],
      !!contributionMode,
    );

    const transformedSeries = transformSeries(
      {
        ...entry,
        id: `${displayName || ''}`,
        name: `${displayName || ''}`,
      },
      colorScale,
      colorScaleKey,
      {
        area,
        markerEnabled,
        markerSize,
        areaOpacity: opacity,
        seriesType,
        showValue,
        onlyTotal,
        stack: Boolean(stack),
        stackIdSuffix: '\na',
        yAxisIndex,
        filterState,
        seriesKey: entry.name,
        sliceId,
        queryIndex: 0,
        formatter:
          seriesType === EchartsTimeseriesSeriesType.Bar
            ? getOverMaxHiddenFormatter({
                max: yAxisMax,
                formatter: seriesFormatter,
              })
            : seriesFormatter,
        valueLabel:
          seriesType === EchartsTimeseriesSeriesType.Bar
            ? crowdedBarValueLabel
            : undefined,
        valueLabelLayout:
          seriesType === EchartsTimeseriesSeriesType.Bar
            ? crowdedBarValueLabelLayout
            : undefined,
        totalStackedValues: sortedTotalValuesA,
        showValueIndexes: showValueIndexesA,
        thresholdValues,
        timeShiftColor,
        theme,
      },
    );

    if (transformedSeries) {
      series.push(transformedSeries);
      mapSeriesIdToAxis(transformedSeries, yAxisIndex);
    }
  });

  rawSeriesB.forEach(entry => {
    const entryName = String(entry.name || '');
    const seriesEntry = inverted[entryName] || entryName;
    const seriesName = `${seriesEntry} (1)`;
    const colorScaleKey = getOriginalSeries(seriesEntry, array);

    let displayName: string;

    if (groupbyB.length > 0) {
      // When we have groupby, format as "metric, dimension"
      const metricPart: string = showQueryIdentifiers
        ? `${MetricDisplayNameB} (Query B)`
        : MetricDisplayNameB;
      displayName = entryName.includes(metricPart)
        ? entryName
        : `${metricPart}, ${entryName}`;
    } else {
      // When no groupby, format as just the entry name with optional query identifier
      displayName = showQueryIdentifiers ? `${entryName} (Query B)` : entryName;
    }

    const seriesFormatter = getFormatter(
      customFormattersSecondary,
      formatterSecondary,
      metricsB,
      labelMapB?.[seriesName]?.[0],
      !!contributionMode,
    );

    const transformedSeries = transformSeries(
      {
        ...entry,
        id: `${displayName || ''}`,
        name: `${displayName || ''}`,
      },

      colorScale,
      colorScaleKey,
      {
        area: areaB,
        markerEnabled: markerEnabledB,
        markerSize: markerSizeB,
        areaOpacity: opacityB,
        seriesType: seriesTypeB,
        showValue: showValueB,
        onlyTotal: onlyTotalB,
        stack: Boolean(stackB),
        stackIdSuffix: '\nb',
        yAxisIndex: yAxisIndexB,
        filterState,
        seriesKey: entry.name,
        sliceId,
        queryIndex: 1,
        formatter:
          seriesTypeB === EchartsTimeseriesSeriesType.Bar
            ? getOverMaxHiddenFormatter({
                max: maxSecondary,
                formatter: seriesFormatter,
              })
            : seriesFormatter,
        valueLabel:
          seriesTypeB === EchartsTimeseriesSeriesType.Bar
            ? crowdedBarValueLabel
            : undefined,
        valueLabelLayout:
          seriesTypeB === EchartsTimeseriesSeriesType.Bar
            ? crowdedBarValueLabelLayout
            : undefined,
        totalStackedValues: sortedTotalValuesB,
        showValueIndexes: showValueIndexesB,
        thresholdValues: thresholdValuesB,
        timeShiftColor,
        theme,
      },
    );

    if (transformedSeries) {
      series.push(transformedSeries);
      mapSeriesIdToAxis(transformedSeries, yAxisIndexB);
    }
  });

  // default to 0-100% range when doing row-level contribution chart
  if (contributionMode === 'row' && stack) {
    if (yAxisMin === undefined) yAxisMin = 0;
    if (yAxisMax === undefined) yAxisMax = 1;
    if (minSecondary === undefined) minSecondary = 0;
    if (maxSecondary === undefined) maxSecondary = 1;
  }

  const tooltipFormatter =
    xAxisDataType === GenericDataType.Temporal
      ? getTooltipTimeFormatter(tooltipTimeFormat)
      : String;
  const xAxisFormatter =
    xAxisDataType === GenericDataType.Temporal
      ? getXAxisFormatter(xAxisTimeFormat, timeGrainSqla)
      : String;

  const showMaxLabel =
    xAxisType === AxisType.Time && xAxisLabelRotation === 0 && !!timeGrainSqla;
  const deduplicatedFormatter = showMaxLabel
    ? (() => {
        let lastLabel: string | undefined;
        const wrapper = (value: number | string) => {
          const label =
            typeof xAxisFormatter === 'function'
              ? (xAxisFormatter as Function)(value)
              : String(value);
          if (label === lastLabel) {
            return '';
          }
          lastLabel = label;
          return label;
        };
        if (typeof xAxisFormatter === 'function' && 'id' in xAxisFormatter) {
          (wrapper as any).id = (xAxisFormatter as any).id;
        }
        return wrapper;
      })()
    : xAxisFormatter;

  const addYAxisTitleOffset =
    !!(yAxisTitle || yAxisTitleSecondary) &&
    convertInteger(yAxisTitleMargin) !== 0;
  const addXAxisTitleOffset =
    !!xAxisTitle && convertInteger(xAxisTitleMargin) !== 0;
  const baseChartPadding = getPadding(
    showLegend,
    legendOrientation,
    addYAxisTitleOffset,
    zoomable,
    legendMargin,
    addXAxisTitleOffset,
    yAxisTitlePosition,
    convertInteger(yAxisTitleMargin),
    convertInteger(xAxisTitleMargin),
  );
  const legendData = series
    .filter(
      entry =>
        extractForecastSeriesContext((entry.name || '') as string).type ===
        ForecastSeriesEnum.Observation,
    )
    .map(entry => entry.name)
    .filter((name): name is string => Boolean(name))
    .concat(extractAnnotationLabels(annotationLayers))
    .sort((a: string, b: string) => {
      if (!legendSort) return 0;
      return legendSort === 'asc' ? a.localeCompare(b) : b.localeCompare(a);
    });
  const { effectiveLegendMargin, effectiveLegendType } = resolveLegendLayout({
    availableWidth:
      legendOrientation === LegendOrientation.Top ||
      legendOrientation === LegendOrientation.Bottom
        ? getHorizontalLegendAvailableWidth({
            chartWidth: width,
            orientation: legendOrientation,
            padding: baseChartPadding,
            zoomable,
          })
        : undefined,
    chartHeight: height,
    chartWidth: width,
    legendItems: legendData,
    legendMargin,
    orientation: legendOrientation,
    show: showLegend,
    theme,
    type: legendType,
  });

  const chartPadding = getPadding(
    showLegend,
    legendOrientation,
    addYAxisTitleOffset,
    zoomable,
    effectiveLegendMargin,
    addXAxisTitleOffset,
    yAxisTitlePosition,
    convertInteger(yAxisTitleMargin),
    convertInteger(xAxisTitleMargin),
  );
  let responsiveChartPadding = chartPadding;
  if (compactMobileMixedLineChart) {
    responsiveChartPadding = {
      ...chartPadding,
      left: Math.min(chartPadding.left, 28),
      right: Math.min(
        chartPadding.right,
        hideCompactSecondaryAxisLabels ? 4 : 28,
      ),
      ...(!zoomable
        ? {
            bottom: Math.max(
              chartPadding.bottom,
              xAxisLabelRotation === 0 ? 28 : 56,
            ),
          }
        : {}),
    };
  } else if (compactMobileMixedBarChart) {
    responsiveChartPadding = {
      ...chartPadding,
      left: Math.min(chartPadding.left, 4),
      right: Math.min(chartPadding.right, 4),
    };
  }

  const { setDataMask = () => {}, onContextMenu } = hooks;
  const alignTicks = yAxisIndex !== yAxisIndexB;

  const echartOptions: EChartsCoreOption = {
    useUTC: true,
    grid: {
      ...defaultGrid,
      ...(compactMobileMixedLineChart ? { containLabel: false } : {}),
      ...responsiveChartPadding,
    },
    xAxis: {
      type: xAxisType,
      name: xAxisTitle,
      nameGap: convertInteger(xAxisTitleMargin),
      nameLocation: 'middle',
      axisLabel: {
        hideOverlap: !(xAxisType === AxisType.Time && xAxisLabelRotation !== 0),
        formatter: deduplicatedFormatter,
        rotate: xAxisLabelRotation,
        interval: xAxisLabelInterval,
        ...(showMaxLabel && {
          showMaxLabel: true,
          alignMaxLabel: 'right',
        }),
      },
      minorTick: { show: minorTicks },
      minInterval:
        xAxisType === AxisType.Time && timeGrainSqla && !forceMaxInterval
          ? TIMEGRAIN_TO_TIMESTAMP[
              timeGrainSqla as keyof typeof TIMEGRAIN_TO_TIMESTAMP
            ]
          : 0,
      maxInterval:
        xAxisType === AxisType.Time && timeGrainSqla && forceMaxInterval
          ? TIMEGRAIN_TO_TIMESTAMP[
              timeGrainSqla as keyof typeof TIMEGRAIN_TO_TIMESTAMP
            ]
          : undefined,
      ...getMinAndMaxFromBounds(
        xAxisType,
        truncateXAxis,
        xAxisMin,
        xAxisMax,
        seriesType === EchartsTimeseriesSeriesType.Bar ||
          seriesTypeB === EchartsTimeseriesSeriesType.Bar
          ? EchartsTimeseriesSeriesType.Bar
          : undefined,
      ),
    },
    yAxis: [
      {
        ...defaultYAxis,
        type: logAxis ? 'log' : 'value',
        min: yAxisMin,
        max: yAxisMax,
        minorTick: { show: minorTicks },
        minorSplitLine: { show: minorSplitLine },
        axisLabel: {
          formatter: getYAxisFormatter(
            metrics,
            !!contributionMode,
            customFormatters,
            formatter,
            yAxisFormat,
          ),
        },
        scale: truncateYAxis,
        name: yAxisTitle,
        nameGap: convertInteger(yAxisTitleMargin),
        nameLocation: yAxisTitlePosition === 'Left' ? 'middle' : 'end',
        alignTicks,
      },
      {
        ...defaultYAxis,
        type: logAxisSecondary ? 'log' : 'value',
        min: minSecondary,
        max: maxSecondary,
        minorTick: { show: minorTicks },
        splitLine: { show: false },
        minorSplitLine: { show: minorSplitLine },
        axisLabel: {
          ...(hideCompactSecondaryAxisLabels ? { show: false } : {}),
          formatter: getYAxisFormatter(
            metricsB,
            !!contributionMode,
            customFormattersSecondary,
            formatterSecondary,
            yAxisFormatSecondary,
          ),
        },
        scale: truncateYAxis,
        name: yAxisTitleSecondary,
        alignTicks,
      },
    ],
    tooltip: {
      ...getDefaultTooltip(refs),
      show: !inContextMenu,
      trigger: useAxisTooltip ? 'axis' : 'item',
      ...(compactMobileMixedChart
        ? { appendToBody: false, confine: true, hideDelay: 3000 }
        : {}),
      formatter: (params: any) => {
        const xValue: number = useAxisTooltip
          ? params[0].value[0]
          : params.value[0];
        const forecastValue: any[] = useAxisTooltip ? params : [params];

        const sortedKeys = extractTooltipKeys(
          forecastValue,
          // horizontal mode is not supported in mixed series chart
          1,
          useAxisTooltip,
          tooltipSortByMetric,
        );

        const rows: string[][] = [];
        const forecastValues =
          extractForecastValuesFromTooltipParams(forecastValue);

        const keys = Object.keys(forecastValues);
        let focusedRow;
        sortedKeys
          .filter(key => keys.includes(key))
          .forEach(key => {
            const value = forecastValues[key];
            // if there are no dimensions, key is a verbose name of a metric,
            // otherwise it is a comma separated string where the first part is metric name
            let formatterKey;
            if (primarySeries.has(key)) {
              formatterKey =
                groupby.length === 0 ? inverted[key] : labelMap[key]?.[0];
            } else {
              formatterKey =
                groupbyB.length === 0 ? inverted[key] : labelMapB[key]?.[0];
            }
            const tooltipFormatter = getFormatter(
              customFormatters,
              formatter,
              metrics,
              formatterKey,
              !!contributionMode,
            );
            const tooltipFormatterSecondary = getFormatter(
              customFormattersSecondary,
              formatterSecondary,
              metricsB,
              formatterKey,
              !!contributionMode,
            );
            const row = formatForecastTooltipSeries({
              ...value,
              seriesName: key,
              formatter: primarySeries.has(key)
                ? tooltipFormatter
                : tooltipFormatterSecondary,
            });
            rows.push(row);
            if (key === focusedSeries) {
              focusedRow = rows.length - 1;
            }
          });
        return tooltipHtml(rows, tooltipFormatter(xValue), focusedRow);
      },
    },
    legend: {
      ...getLegendProps(
        effectiveLegendType,
        legendOrientation,
        showLegend,
        theme,
        zoomable,
        legendState,
        responsiveChartPadding,
        !compactMobileMixedChart,
      ),
      data: getLegendDataWithTooltip(legendData),
    },
    series: dedupSeries(reorderForecastSeries(series) as SeriesOption[]),
    toolbox: {
      show: zoomable,
      top: TIMESERIES_CONSTANTS.toolboxTop,
      right: TIMESERIES_CONSTANTS.toolboxRight,
      feature: {
        dataZoom: {
          yAxisIndex: false,
          title: {
            zoom: 'zoom area',
            back: 'restore zoom',
          },
        },
      },
    },
    dataZoom: zoomable
      ? [
          {
            type: 'slider',
            start: TIMESERIES_CONSTANTS.dataZoomStart,
            end: TIMESERIES_CONSTANTS.dataZoomEnd,
            bottom: TIMESERIES_CONSTANTS.zoomBottom,
          },
        ]
      : [],
  };

  const onFocusedSeries = (seriesName: string | null) => {
    focusedSeries = seriesName;
  };

  let customEchartOptions;
  try {
    // Parse custom EChart options safely using AST analysis
    // This replaces the unsafe `new Function()` approach with a secure parser
    // that only allows static data structures (no function callbacks)
    customEchartOptions = safeParseEChartOptions(_echartOptions);
  } catch (_) {
    customEchartOptions = undefined;
  }

  const mergedEchartOptions = customEchartOptions
    ? mergeCustomEChartOptions(echartOptions, customEchartOptions)
    : echartOptions;

  return {
    formData,
    width,
    height,
    echartOptions: mergedEchartOptions,
    setDataMask,
    emitCrossFilters,
    labelMap,
    labelMapB,
    groupby,
    groupbyB,
    seriesBreakdown: rawSeriesA.length,
    selectedValues: filterState.selectedValues || [],
    onContextMenu,
    onFocusedSeries,
    xValueFormatter: tooltipFormatter,
    xAxis: {
      label: xAxisLabel,
      type: xAxisType,
    },
    refs,
    coltypeMapping,
  };
}
