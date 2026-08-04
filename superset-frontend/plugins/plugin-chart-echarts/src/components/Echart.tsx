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
  useRef,
  useEffect,
  useMemo,
  forwardRef,
  useImperativeHandle,
  useLayoutEffect,
  useCallback,
  Ref,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { useSelector } from 'react-redux';

import { styled, useTheme } from '@apache-superset/core/theme';
import { use, init, EChartsType, registerLocale } from 'echarts/core';
import {
  SankeyChart,
  PieChart,
  BarChart,
  FunnelChart,
  GaugeChart,
  GraphChart,
  LineChart,
  ScatterChart,
  RadarChart,
  BoxplotChart,
  TreeChart,
  TreemapChart,
  HeatmapChart,
  SunburstChart,
  CustomChart,
} from 'echarts/charts';
import { CanvasRenderer } from 'echarts/renderers';
import {
  TooltipComponent,
  TitleComponent,
  GridComponent,
  VisualMapComponent,
  LegendComponent,
  DataZoomComponent,
  type DataZoomComponentOption,
  ToolboxComponent,
  GraphicComponent,
  AriaComponent,
  MarkAreaComponent,
  MarkLineComponent,
} from 'echarts/components';
import { LabelLayout } from 'echarts/features';
import {
  EchartsHandler,
  EchartsProps,
  EchartsStylesProps,
  EventHandlers,
} from '../types';
import { DEFAULT_LOCALE } from '../constants';
import { mergeEchartsThemeOverrides } from '../utils/themeOverrides';

// Define this interface here to avoid creating a dependency back to superset-frontend,
// TODO: to move the type to @superset-ui/core
interface ExplorePageState {
  common?: {
    locale?: string;
  };
  dashboardState?: {
    isRefreshing?: boolean;
  };
}

const toCssPixels = (value: number) => `${value}px`;
const LEGEND_TOOLTIP_HIDE_DELAY = 5000;
const LEGEND_TOOLTIP_OFFSET = 12;
const LEGEND_TOOLTIP_MAX_WIDTH = 320;
const LEGEND_TOOLTIP_SCREEN_GUTTER = 8;
const CHART_TOOLTIP_CLICK_GRID_SIZE = 8;
const REPEATED_CHART_TOOLTIP_HIDE_DELAY = 80;
const RECENT_DOM_POINTER_WINDOW = 250;
const EXCLUSIVE_ITEM_EMPHASIS_SERIES_TYPES = ['heatmap', 'pie'];

const Styles = styled.div<EchartsStylesProps>`
  height: ${({ height }) => toCssPixels(height)};
  max-width: 100%;
  overflow: hidden;
  width: ${({ width }) => toCssPixels(width)};
`;

const LegendTooltip = styled.div`
  background: ${({ theme }) => theme.colorBgContainer};
  border-radius: ${({ theme }) => theme.borderRadiusSM}px;
  box-shadow: ${({ theme }) => theme.boxShadowSecondary};
  color: ${({ theme }) => theme.colorText};
  font-size: ${({ theme }) => theme.fontSize}px;
  line-height: ${({ theme }) => theme.lineHeight};
  max-width: calc(100vw - ${LEGEND_TOOLTIP_SCREEN_GUTTER * 2}px);
  overflow-wrap: anywhere;
  padding: ${({ theme }) => theme.sizeXXS}px ${({ theme }) => theme.sizeXS}px;
  pointer-events: auto;
  position: fixed;
  z-index: ${({ theme }) => theme.zIndexPopupBase + 1};
`;

type LegendTooltipState = {
  label: string;
  x: number;
  y: number;
};

type ChartTooltipClickState = {
  key: string;
};

type DomPointerEvent = MouseEvent | PointerEvent | TouchEvent;

type DomChartPointerState = {
  key: string;
  time: number;
};

type EchartsPointerEvent = {
  offsetX?: number;
  offsetY?: number;
  event?: {
    clientX?: number;
    clientY?: number;
  };
};

type EchartsEventPayload = {
  componentType?: string;
  dataIndex?: unknown;
  name?: unknown;
  event?: EchartsPointerEvent;
  seriesIndex?: unknown;
  seriesType?: string;
};

type ZrenderElement = {
  parent?: ZrenderElement | null;
  __legendDataIndex?: number;
};

type ZrenderEventPayload = EchartsPointerEvent & {
  target?: ZrenderElement | null;
};

type LegendOptionWithData = {
  data?: unknown[];
};

type EchartSeriesOptionWithType = {
  type?: unknown;
};

type EchartOptionWithSeries = {
  series?: EchartSeriesOptionWithType | EchartSeriesOptionWithType[];
};

const getLegendTooltipLabel = (params: EchartsEventPayload) => {
  if (params.componentType !== 'legend' || params.name == null) {
    return null;
  }
  return String(params.name);
};

const getExclusiveItemEmphasisPayload = (params: EchartsEventPayload) => {
  if (
    params.componentType !== 'series' ||
    !params.seriesType ||
    !EXCLUSIVE_ITEM_EMPHASIS_SERIES_TYPES.includes(params.seriesType) ||
    typeof params.dataIndex !== 'number'
  ) {
    return null;
  }

  return {
    dataIndex: params.dataIndex,
    ...(typeof params.seriesIndex === 'number'
      ? { seriesIndex: params.seriesIndex }
      : {}),
  };
};

const getLegendDataIndex = (target?: ZrenderElement | null) => {
  let element = target;
  while (element) {
    if (typeof element.__legendDataIndex === 'number') {
      return element.__legendDataIndex;
    }
    element = element.parent;
  }
  return null;
};

const getLegendItemLabel = (item: unknown) => {
  if (typeof item === 'string') {
    return item;
  }
  if (item && typeof item === 'object' && 'name' in item) {
    const name = (item as { name?: unknown }).name;
    return name == null ? null : String(name);
  }
  return null;
};

const getDomEventPoint = (event: DomPointerEvent) => {
  if ('clientX' in event) {
    return {
      clientX: event.clientX,
      clientY: event.clientY,
    };
  }

  const touch = event.touches[0] ?? event.changedTouches[0];
  return touch
    ? {
        clientX: touch.clientX,
        clientY: touch.clientY,
      }
    : null;
};

const getChartTooltipClickKey = (clientX: number, clientY: number) =>
  [
    'chart',
    Math.round(clientX / CHART_TOOLTIP_CLICK_GRID_SIZE),
    Math.round(clientY / CHART_TOOLTIP_CLICK_GRID_SIZE),
  ].join(':');

const getDomTooltipClickKey = (
  event: DomPointerEvent,
  element?: HTMLDivElement | null,
) => {
  const rect = element?.getBoundingClientRect();
  const point = getDomEventPoint(event);
  if (!rect || !point) {
    return null;
  }

  return getChartTooltipClickKey(
    point.clientX - rect.left,
    point.clientY - rect.top,
  );
};

const getEchartsTooltipClickKey = (
  event?: EchartsPointerEvent,
  element?: HTMLDivElement | null,
) => {
  const rect = element?.getBoundingClientRect();
  if (!rect) {
    return null;
  }

  const clientX =
    event?.event?.clientX ??
    (event?.offsetX == null ? undefined : rect.left + event.offsetX);
  const clientY =
    event?.event?.clientY ??
    (event?.offsetY == null ? undefined : rect.top + event.offsetY);

  if (clientX == null || clientY == null) {
    return null;
  }

  return getChartTooltipClickKey(clientX - rect.left, clientY - rect.top);
};

const hideRenderedEchartTooltips = () => {
  if (typeof document === 'undefined') {
    return;
  }

  document.querySelectorAll<HTMLElement>('.echarts-tooltip').forEach(node => {
    node.style.removeProperty('display');
    node.style.visibility = 'hidden';
    node.style.opacity = '0';
    node.style.pointerEvents = 'none';
    node.style.left = '0px';
    node.style.top = '0px';
    node.style.transform = 'translate3d(0px, 0px, 0px)';
  });
};

const restoreRenderedEchartTooltipDisplay = () => {
  if (typeof document === 'undefined') {
    return;
  }

  document.querySelectorAll<HTMLElement>('.echarts-tooltip').forEach(node => {
    node.style.removeProperty('display');
    node.style.removeProperty('visibility');
    node.style.removeProperty('opacity');
    node.style.removeProperty('pointer-events');
    node.style.removeProperty('left');
    node.style.removeProperty('top');
    node.style.removeProperty('transform');
  });
};

const hasExclusiveItemEmphasisSeries = (chart?: EChartsType) => {
  const option = chart?.getOption() as EchartOptionWithSeries | undefined;
  const series = option?.series
    ? Array.isArray(option.series)
      ? option.series
      : [option.series]
    : [];
  return series.some(
    item =>
      typeof item.type === 'string' &&
      EXCLUSIVE_ITEM_EMPHASIS_SERIES_TYPES.includes(item.type),
  );
};

// eslint-disable-next-line react-hooks/rules-of-hooks -- This is ECharts' use function, not a React hook
use([
  CanvasRenderer,
  BarChart,
  BoxplotChart,
  CustomChart,
  FunnelChart,
  GaugeChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  PieChart,
  RadarChart,
  SankeyChart,
  ScatterChart,
  SunburstChart,
  TreeChart,
  TreemapChart,
  AriaComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
  TitleComponent,
  VisualMapComponent,
  LabelLayout,
]);

const loadLocale = async (locale: string) => {
  let lang;
  try {
    lang = await import(`echarts/lib/i18n/lang${locale}`);
  } catch {
    // Locale not supported in ECharts
  }
  return lang?.default;
};

function Echart(
  {
    width,
    height,
    echartOptions,
    eventHandlers,
    zrEventHandlers,
    selectedValues = {},
    refs,
    vizType,
  }: EchartsProps,
  ref: Ref<EchartsHandler>,
) {
  const theme = useTheme();
  const divRef = useRef<HTMLDivElement>(null);
  if (refs) {
    // eslint-disable-next-line no-param-reassign
    refs.divRef = divRef;
  }
  const [didMount, setDidMount] = useState(false);
  const chartRef = useRef<EChartsType>();
  const currentSelection = useMemo(
    () => Object.keys(selectedValues) || [],
    [selectedValues],
  );
  const previousSelection = useRef<string[]>([]);
  const legendTooltipHideTimer = useRef<ReturnType<typeof setTimeout>>();
  const chartTooltipClickRef = useRef<ChartTooltipClickState | null>(null);
  const lastDomChartPointerRef = useRef<DomChartPointerState | null>(null);
  const [legendTooltip, setLegendTooltip] = useState<LegendTooltipState | null>(
    null,
  );

  useImperativeHandle(ref, () => ({
    getEchartInstance: () => chartRef.current,
  }));

  const locale = useSelector(
    (state: ExplorePageState) => state?.common?.locale ?? DEFAULT_LOCALE,
  ).toUpperCase();
  const isDashboardRefreshing = useSelector((state: ExplorePageState) =>
    Boolean(state?.dashboardState?.isRefreshing),
  );

  const handleSizeChange = useCallback(
    ({ width, height }: { width: number; height: number }) => {
      if (chartRef.current) {
        chartRef.current.resize({ width, height });
      }
    },
    [],
  );

  const clearLegendTooltipTimer = useCallback(() => {
    if (legendTooltipHideTimer.current) {
      clearTimeout(legendTooltipHideTimer.current);
      legendTooltipHideTimer.current = undefined;
    }
  }, []);

  const hideLegendTooltip = useCallback(
    (delay = 0) => {
      clearLegendTooltipTimer();
      if (delay > 0) {
        legendTooltipHideTimer.current = setTimeout(() => {
          setLegendTooltip(null);
        }, delay);
        return;
      }
      setLegendTooltip(null);
    },
    [clearLegendTooltipTimer],
  );

  const clearExclusiveItemEmphasisState = useCallback(() => {
    const chart = chartRef.current;
    if (!hasExclusiveItemEmphasisSeries(chart)) {
      return;
    }

    chart?.dispatchAction({ type: 'downplay' });
  }, []);

  const showOnlyItemEmphasis = useCallback((params: EchartsEventPayload) => {
    const payload = getExclusiveItemEmphasisPayload(params);
    const chart = chartRef.current;
    if (!payload || !hasExclusiveItemEmphasisSeries(chart)) {
      return;
    }

    chart?.dispatchAction({ type: 'downplay' });
    chart?.dispatchAction({
      type: 'highlight',
      ...payload,
    });
  }, []);

  const hideEchartTooltip = useCallback(() => {
    chartTooltipClickRef.current = null;
    chartRef.current?.dispatchAction({ type: 'hideTip' });
    chartRef.current?.dispatchAction({
      type: 'updateAxisPointer',
      currTrigger: 'leave',
    });
    clearExclusiveItemEmphasisState();
    hideRenderedEchartTooltips();
  }, [clearExclusiveItemEmphasisState]);

  const hideAllTooltips = useCallback(() => {
    hideLegendTooltip();
    hideEchartTooltip();
  }, [hideEchartTooltip, hideLegendTooltip]);

  const showLegendTooltipAt = useCallback(
    (label: string, event?: EchartsPointerEvent, toggleIfSame = false) => {
      if (toggleIfSame && legendTooltip?.label === label) {
        hideLegendTooltip();
        return false;
      }

      clearLegendTooltipTimer();
      const pointerEvent = event?.event;
      const chartRect = divRef.current?.getBoundingClientRect();
      const rawX =
        pointerEvent?.clientX ??
        (chartRect && event?.offsetX != null
          ? chartRect.left + event.offsetX
          : undefined);
      const rawY =
        pointerEvent?.clientY ??
        (chartRect && event?.offsetY != null
          ? chartRect.top + event.offsetY
          : undefined);

      if (rawX == null || rawY == null) {
        return false;
      }

      const maxLeft =
        typeof window === 'undefined'
          ? rawX
          : window.innerWidth -
            LEGEND_TOOLTIP_MAX_WIDTH -
            LEGEND_TOOLTIP_SCREEN_GUTTER;

      setLegendTooltip({
        label,
        x: Math.max(
          LEGEND_TOOLTIP_SCREEN_GUTTER,
          Math.min(rawX + LEGEND_TOOLTIP_OFFSET, maxLeft),
        ),
        y: Math.max(LEGEND_TOOLTIP_SCREEN_GUTTER, rawY + LEGEND_TOOLTIP_OFFSET),
      });
      return true;
    },
    [clearLegendTooltipTimer, hideLegendTooltip, legendTooltip?.label],
  );

  const showLegendTooltip = useCallback(
    (params: EchartsEventPayload, toggleIfSame = false) => {
      const label = getLegendTooltipLabel(params);
      return label
        ? showLegendTooltipAt(label, params.event, toggleIfSame)
        : false;
    },
    [showLegendTooltipAt],
  );

  const getLegendLabelFromZrenderEvent = useCallback(
    (params: ZrenderEventPayload) => {
      const dataIndex = getLegendDataIndex(params.target);
      if (dataIndex == null) {
        return null;
      }
      const option = chartRef.current?.getOption() as
        | { legend?: LegendOptionWithData | LegendOptionWithData[] }
        | undefined;
      const legend = Array.isArray(option?.legend)
        ? option.legend[0]
        : option?.legend;
      return getLegendItemLabel(legend?.data?.[dataIndex]);
    },
    [],
  );

  const showLegendTooltipFromZrenderEvent = useCallback(
    (params: ZrenderEventPayload, toggleIfSame = false) => {
      const label = getLegendLabelFromZrenderEvent(params);
      return label ? showLegendTooltipAt(label, params, toggleIfSame) : false;
    },
    [getLegendLabelFromZrenderEvent, showLegendTooltipAt],
  );

  const toggleEchartTooltipForKey = useCallback(
    (key: string) => {
      hideLegendTooltip();
      if (chartTooltipClickRef.current?.key === key) {
        window.setTimeout(hideEchartTooltip, REPEATED_CHART_TOOLTIP_HIDE_DELAY);
        return true;
      }

      clearExclusiveItemEmphasisState();
      restoreRenderedEchartTooltipDisplay();
      chartTooltipClickRef.current = { key };
      return false;
    },
    [clearExclusiveItemEmphasisState, hideEchartTooltip, hideLegendTooltip],
  );

  const toggleEchartTooltipOnRepeatedChartClick = useCallback(
    (event?: EchartsPointerEvent) => {
      const key = getEchartsTooltipClickKey(event, divRef.current);
      if (!key) {
        return false;
      }

      const lastDomPointer = lastDomChartPointerRef.current;
      if (
        lastDomPointer?.key === key &&
        Date.now() - lastDomPointer.time < RECENT_DOM_POINTER_WINDOW
      ) {
        return false;
      }

      return toggleEchartTooltipForKey(key);
    },
    [toggleEchartTooltipForKey],
  );

  const toggleEchartTooltipOnRepeatedDomPointer = useCallback(
    (event: DomPointerEvent) => {
      const element = divRef.current;
      const target = event.target;
      if (!element || !(target instanceof Node) || !element.contains(target)) {
        return false;
      }

      const key = getDomTooltipClickKey(event, element);
      if (!key) {
        return false;
      }

      lastDomChartPointerRef.current = {
        key,
        time: Date.now(),
      };
      return toggleEchartTooltipForKey(key);
    },
    [toggleEchartTooltipForKey],
  );

  useEffect(() => {
    loadLocale(locale).then(localeObj => {
      if (localeObj) {
        registerLocale(locale, localeObj);
      }
      if (!divRef.current) return;
      if (!chartRef.current) {
        // Pass width and height to init to avoid "Can't get DOM width or height" warning
        // since the DOM element may not have its dimensions yet when init is called
        chartRef.current = init(divRef.current, null, {
          locale,
          width,
          height,
        });
      }
      // did mount
      handleSizeChange({ width, height });
      setDidMount(true);
    });
  }, [locale, width, height, handleSizeChange]);

  useEffect(() => {
    if (didMount) {
      const internalEventHandlers: EventHandlers = {
        mouseover: params => {
          showLegendTooltip(params);
        },
        click: params => {
          if (showLegendTooltip(params, true)) {
            hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY);
          } else {
            showOnlyItemEmphasis(params);
          }
        },
        mouseout: params => {
          if (getLegendTooltipLabel(params)) {
            hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY);
          }
        },
      };
      const eventNames = new Set([
        ...Object.keys(eventHandlers || {}),
        ...Object.keys(internalEventHandlers),
      ]);
      eventNames.forEach(name => {
        const userHandler = eventHandlers?.[name];
        const internalHandler = internalEventHandlers[name];
        chartRef.current?.off(name);
        chartRef.current?.on(name, params => {
          internalHandler?.(params);
          userHandler?.(params);
        });
      });

      const internalZrEventHandlers: EventHandlers = {
        mousemove: params => {
          if (!showLegendTooltipFromZrenderEvent(params)) {
            hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY);
          }
        },
        click: params => {
          if (showLegendTooltipFromZrenderEvent(params, true)) {
            hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY);
          } else {
            toggleEchartTooltipOnRepeatedChartClick(params);
          }
        },
        mouseout: params => {
          if (getLegendLabelFromZrenderEvent(params)) {
            hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY);
          }
        },
        mousewheel: () => {
          hideAllTooltips();
        },
        globalout: () => {
          hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY);
        },
      };
      const zrEventNames = new Set([
        ...Object.keys(zrEventHandlers || {}),
        ...Object.keys(internalZrEventHandlers),
      ]);
      zrEventNames.forEach(name => {
        const userHandler = zrEventHandlers?.[name];
        const internalHandler = internalZrEventHandlers[name];
        chartRef.current?.getZr().off(name);
        chartRef.current?.getZr().on(name, params => {
          internalHandler?.(params);
          userHandler?.(params);
        });
      });

      const getEchartsTheme = (options: any) => {
        const antdTheme = theme;
        const echartsTheme = {
          textStyle: {
            color: antdTheme.colorText,
            fontFamily: antdTheme.fontFamily,
          },
          title: {
            textStyle: { color: antdTheme.colorText },
          },
          legend: {
            textStyle: { color: antdTheme.colorTextSecondary },
            pageTextStyle: {
              color: antdTheme.colorTextSecondary,
            },
            pageIconColor: antdTheme.colorTextSecondary,
            pageIconInactiveColor: antdTheme.colorTextDisabled,
            inactiveColor: antdTheme.colorTextDisabled,
          },
          tooltip: {
            backgroundColor: antdTheme.colorBgContainer,
            textStyle: { color: antdTheme.colorText },
          },
          axisPointer: {
            lineStyle: { color: antdTheme.colorPrimary },
            label: { color: antdTheme.colorText },
          },
        } as any;
        if (options?.xAxis) {
          echartsTheme.xAxis = {
            axisLine: { lineStyle: { color: antdTheme.colorSplit } },
            axisLabel: { color: antdTheme.colorTextSecondary },
            splitLine: { lineStyle: { color: antdTheme.colorSplit } },
            minorSplitLine: {
              lineStyle: { color: antdTheme.colorBorderSecondary },
            },
          };
        }
        if (options?.yAxis) {
          echartsTheme.yAxis = {
            axisLine: { lineStyle: { color: antdTheme.colorSplit } },
            axisLabel: { color: antdTheme.colorTextSecondary },
            splitLine: { lineStyle: { color: antdTheme.colorSplit } },
            minorSplitLine: {
              lineStyle: { color: antdTheme.colorBorderSecondary },
            },
          };
        }
        return echartsTheme;
      };

      const baseTheme = getEchartsTheme(echartOptions);
      const globalOverrides = theme.echartsOptionsOverrides || {};
      const chartOverrides = vizType
        ? theme.echartsOptionsOverridesByChartType?.[vizType] || {}
        : {};

      // Disable animations during auto-refresh to reduce visual noise
      const animationOverride = isDashboardRefreshing
        ? {
            animation: false,
            animationDuration: 0,
          }
        : {};

      const themedEchartOptions = mergeEchartsThemeOverrides(
        baseTheme,
        echartOptions,
        globalOverrides,
        chartOverrides,
        animationOverride,
      );

      const notMerge = !isDashboardRefreshing;
      chartRef.current?.dispatchAction({ type: 'hideTip' });
      // setOption(notMerge:true) replaces the dataZoom config, dropping any
      // range the user has engaged. Preserve it across the call.
      const previousZoom = notMerge
        ? (
            chartRef.current?.getOption() as {
              dataZoom?: DataZoomComponentOption[];
            }
          )?.dataZoom
        : undefined;
      chartRef.current?.setOption(themedEchartOptions, {
        notMerge,
        replaceMerge: notMerge ? undefined : ['series'],
        // lazyUpdate defers render, causing tooltip crashes on stale shapes (#39247)
        lazyUpdate: false,
      });
      if (previousZoom?.length) {
        // Skip restore when the new option reshapes dataZoom (different count
        // means index-based restore could land on the wrong component).
        const newZoom = (
          chartRef.current?.getOption() as {
            dataZoom?: DataZoomComponentOption[];
          }
        )?.dataZoom;
        if (newZoom?.length === previousZoom.length) {
          const batch = previousZoom
            .map((dz, dataZoomIndex) => ({
              dataZoomIndex,
              start: dz.start,
              end: dz.end,
              startValue: dz.startValue,
              endValue: dz.endValue,
            }))
            .filter(b => {
              const hasAny =
                b.start !== undefined ||
                b.end !== undefined ||
                b.startValue !== undefined ||
                b.endValue !== undefined;
              if (!hasAny) return false;
              // Default full-range zoom is functionally identical to the
              // fresh state setOption already produces — skip the dispatch.
              const isDefaultRange =
                b.start === 0 &&
                b.end === 100 &&
                b.startValue === undefined &&
                b.endValue === undefined;
              return !isDefaultRange;
            });
          if (batch.length) {
            chartRef.current?.dispatchAction({ type: 'dataZoom', batch });
          }
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- isDashboardRefreshing intentionally excluded to prevent extra setOption calls
  }, [
    didMount,
    echartOptions,
    eventHandlers,
    getLegendLabelFromZrenderEvent,
    hideLegendTooltip,
    hideAllTooltips,
    showOnlyItemEmphasis,
    showLegendTooltip,
    showLegendTooltipFromZrenderEvent,
    toggleEchartTooltipOnRepeatedChartClick,
    zrEventHandlers,
    theme,
    vizType,
  ]);

  // Clear tooltip on refresh start to avoid stale content (#39247)
  useEffect(() => {
    if (didMount && isDashboardRefreshing && chartRef.current) {
      hideAllTooltips();
    }
  }, [didMount, hideAllTooltips, isDashboardRefreshing]);

  useEffect(() => {
    if (!didMount || typeof window === 'undefined') {
      return undefined;
    }

    const handleViewportChange = () => {
      hideAllTooltips();
    };

    window.addEventListener('scroll', handleViewportChange, true);
    window.addEventListener('resize', handleViewportChange);
    document.addEventListener('scroll', handleViewportChange, true);

    const element = divRef.current;
    const observer =
      typeof IntersectionObserver === 'function' && element
        ? new IntersectionObserver(entries => {
            if (entries.some(entry => !entry.isIntersecting)) {
              hideAllTooltips();
            }
          })
        : null;

    if (observer && element) {
      observer.observe(element);
    }

    return () => {
      window.removeEventListener('scroll', handleViewportChange, true);
      window.removeEventListener('resize', handleViewportChange);
      document.removeEventListener('scroll', handleViewportChange, true);
      observer?.disconnect();
    };
  }, [didMount, hideAllTooltips]);

  useEffect(() => {
    if (!didMount || typeof document === 'undefined') {
      return undefined;
    }

    const pointerEventNames =
      typeof PointerEvent === 'undefined'
        ? (['mousedown', 'touchstart'] as const)
        : (['pointerdown'] as const);
    const handleDomPointer = (event: Event) => {
      toggleEchartTooltipOnRepeatedDomPointer(event as DomPointerEvent);
    };

    pointerEventNames.forEach(eventName => {
      document.addEventListener(eventName, handleDomPointer, true);
    });

    return () => {
      pointerEventNames.forEach(eventName => {
        document.removeEventListener(eventName, handleDomPointer, true);
      });
    };
  }, [didMount, toggleEchartTooltipOnRepeatedDomPointer]);

  useEffect(
    () => () => {
      clearLegendTooltipTimer();
      chartRef.current?.dispose();
    },
    [clearLegendTooltipTimer],
  );

  // highlighting
  useEffect(() => {
    if (!chartRef.current) return;
    chartRef.current.dispatchAction({
      type: 'downplay',
      dataIndex: previousSelection.current.filter(
        value => !currentSelection.includes(value),
      ),
    });
    if (currentSelection.length) {
      chartRef.current.dispatchAction({
        type: 'highlight',
        dataIndex: currentSelection,
      });
    }
    previousSelection.current = currentSelection;
  }, [currentSelection]);

  useLayoutEffect(() => {
    handleSizeChange({ width, height });
  }, [width, height, handleSizeChange]);

  return (
    <>
      <Styles ref={divRef} height={height} width={width} />
      {legendTooltip &&
        typeof document !== 'undefined' &&
        createPortal(
          <LegendTooltip
            style={{
              left: legendTooltip.x,
              top: legendTooltip.y,
              maxWidth: LEGEND_TOOLTIP_MAX_WIDTH,
            }}
            onMouseEnter={clearLegendTooltipTimer}
            onMouseLeave={() => hideLegendTooltip(LEGEND_TOOLTIP_HIDE_DELAY)}
          >
            {legendTooltip.label}
          </LegendTooltip>,
          document.body,
        )}
    </>
  );
}

export default forwardRef(Echart);
