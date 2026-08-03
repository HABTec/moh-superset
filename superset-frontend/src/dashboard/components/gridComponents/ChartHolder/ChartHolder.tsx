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
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
  memo,
  useLayoutEffect,
} from 'react';

import { ResizeCallback, ResizeStartCallback } from 're-resizable';
import cx from 'classnames';
import { useSelector } from 'react-redux';
import { css, useTheme } from '@apache-superset/core/theme';
import { LayoutItem, RootState } from 'src/dashboard/types';
import AnchorLink from 'src/dashboard/components/AnchorLink';
import Chart from 'src/dashboard/components/gridComponents/Chart';
import DeleteComponentButton from 'src/dashboard/components/DeleteComponentButton';
import { Draggable } from 'src/dashboard/components/dnd/DragDroppable';
import { ConnectDragSource } from 'react-dnd';
import HoverMenu from 'src/dashboard/components/menu/HoverMenu';
import ResizableContainer from 'src/dashboard/components/resizable/ResizableContainer';
import getChartAndLabelComponentIdFromPath from 'src/dashboard/util/getChartAndLabelComponentIdFromPath';
import useFilterFocusHighlightStyles from 'src/dashboard/util/useFilterFocusHighlightStyles';
import { AntdThemeProvider } from '@superset-ui/core/components';
import { COLUMN_TYPE, ROW_TYPE } from 'src/dashboard/util/componentTypes';
import {
  GRID_BASE_UNIT,
  GRID_GUTTER_SIZE,
  GRID_MIN_COLUMN_COUNT,
  GRID_MIN_ROW_UNITS,
} from 'src/dashboard/util/constants';
import {
  RESPONSIVE_DASHBOARD_BREAKPOINTS,
  RESPONSIVE_DASHBOARD_BODY_CLASS,
  getResponsiveChartHeight,
  getResponsiveKpiChartHeight,
  getResponsiveChartWidth,
} from 'src/dashboard/util/responsiveDashboard';

export const CHART_MARGIN = 32;
const PHEM_FILL_HEIGHT_CHART_IDS = new Set([153, 154]);
const PHEM_TALL_VIEWPORT_CHART_OFFSET = 470;
const CHART_INTERACTION_HOLDER_CLASS =
  'dashboard-component-chart-holder--interaction-active';
const CHART_INTERACTION_LAYOUT_CLASS =
  'dashboard-component-chart-layout--interaction-active';
const RESPONSIVE_KPI_CARD_CLASS =
  'dashboard-component-chart-holder--compact-kpi';
const RESPONSIVE_KPI_SELECTOR =
  '.superset-legacy-chart-big-number.no-trendline';

export interface ChartHolderProps {
  id: string;
  parentId: string;
  dashboardId: number;
  component: LayoutItem;
  parentComponent: LayoutItem;
  getComponentById?: (id?: string) => LayoutItem | undefined;
  index: number;
  depth: number;
  editMode: boolean;
  directPathLastUpdated?: number;
  fullSizeChartId: number | null;
  isComponentVisible: boolean;

  // grid related
  availableColumnCount: number;
  columnWidth: number;
  onResizeStart: ResizeStartCallback;
  onResize: ResizeCallback;
  onResizeStop: ResizeCallback;

  // dnd
  deleteComponent: (id: string, parentId: string) => void;
  updateComponents: Function;
  handleComponentDrop: (...args: unknown[]) => unknown;
  setFullSizeChartId: (chartId: number | null) => void;
  isInView: boolean;
  responsiveDashboardEnabled?: boolean;
  responsiveLayout?: boolean;
}

const ChartHolder = ({
  id,
  parentId,
  component,
  parentComponent,
  index,
  depth,
  availableColumnCount,
  columnWidth,
  onResizeStart,
  onResize,
  onResizeStop,
  editMode,
  isComponentVisible,
  dashboardId,
  fullSizeChartId,
  getComponentById = () => undefined,
  deleteComponent,
  updateComponents,
  handleComponentDrop,
  setFullSizeChartId,
  isInView,
  responsiveDashboardEnabled = false,
  responsiveLayout = false,
}: ChartHolderProps) => {
  const theme = useTheme();
  const fullSizeStyle = css`
    && {
      position: fixed !important;
      z-index: 3000;
      left: 0;
      top: 0;
      right: 0;
      width: 100%;
      height: 100%;
      padding: ${theme.sizeUnit * 4}px;
    }
  `;
  const { chartId } = component.meta;
  const isFullSize = fullSizeChartId === chartId;
  const chartHolderRef = useRef<HTMLDivElement | null>(null);
  const [responsiveChartWidth, setResponsiveChartWidth] = useState<
    number | undefined
  >();
  const [responsiveKpiCard, setResponsiveKpiCard] = useState(false);
  const responsiveDashboardActive =
    responsiveDashboardEnabled ||
    (typeof document !== 'undefined' &&
      document.body.classList.contains(RESPONSIVE_DASHBOARD_BODY_CLASS));

  const focusHighlightStyles = useFilterFocusHighlightStyles(chartId ?? 0);
  const directPathToChild = useSelector(
    (state: RootState) => state.dashboardState.directPathToChild,
  );
  const directPathLastUpdated = useSelector(
    (state: RootState) => state.dashboardState.directPathLastUpdated ?? 0,
  );

  const [extraControls, setExtraControls] = useState<Record<string, unknown>>(
    {},
  );
  const [outlinedComponentId, setOutlinedComponentId] = useState<string>();
  const [outlinedColumnName, setOutlinedColumnName] = useState<string>();
  const [currentDirectPathLastUpdated, setCurrentDirectPathLastUpdated] =
    useState(0);

  const infoFromPath = useMemo(
    () => getChartAndLabelComponentIdFromPath(directPathToChild ?? []) as any,
    [directPathToChild],
  );

  // Calculate if the chart should be outlined
  useEffect(() => {
    const { label: columnName, chart: chartComponentId } = infoFromPath;

    if (
      directPathLastUpdated !== currentDirectPathLastUpdated &&
      component.id === chartComponentId
    ) {
      setCurrentDirectPathLastUpdated(directPathLastUpdated);
      setOutlinedComponentId(component.id);
      setOutlinedColumnName(columnName);
    }
  }, [
    component,
    currentDirectPathLastUpdated,
    directPathLastUpdated,
    infoFromPath,
  ]);

  // Remove the chart outline after a defined time
  useEffect(() => {
    let timerId: NodeJS.Timeout | undefined;
    if (outlinedComponentId) {
      timerId = setTimeout(() => {
        setOutlinedComponentId(undefined);
        setOutlinedColumnName(undefined);
      }, 2000);
    }

    return () => {
      if (timerId) {
        clearTimeout(timerId);
      }
    };
  }, [outlinedComponentId]);

  const widthMultiple = useMemo(() => {
    const columnParentWidth = getComponentById(
      parentComponent.parents?.find(parent => parent.startsWith(COLUMN_TYPE)),
    )?.meta?.width;

    let widthMultiple = component.meta.width || GRID_MIN_COLUMN_COUNT;
    if (parentComponent.type === COLUMN_TYPE) {
      widthMultiple = parentComponent.meta.width || GRID_MIN_COLUMN_COUNT;
    } else if (columnParentWidth && widthMultiple > columnParentWidth) {
      widthMultiple = columnParentWidth;
    }

    return widthMultiple;
  }, [
    component,
    getComponentById,
    parentComponent.meta.width,
    parentComponent.parents,
    parentComponent.type,
  ]);

  const effectiveWidthMultiple = responsiveLayout ? 1 : widthMultiple;
  const measureResponsiveChartWidth = useCallback(() => {
    const holder = chartHolderRef.current;
    if (
      !responsiveDashboardActive ||
      !holder ||
      typeof window === 'undefined'
    ) {
      return;
    }

    const style = window.getComputedStyle(holder);
    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const paddingRight = parseFloat(style.paddingRight) || 0;
    const horizontalPadding = paddingLeft + paddingRight;
    const holderRect = holder.getBoundingClientRect();
    const measuredWidth =
      Math.min(holder.clientWidth, holderRect.width) - horizontalPadding;
    const viewportWidth =
      window.innerWidth - Math.max(holderRect.left, 0) - horizontalPadding - 2;
    const nextWidth = getResponsiveChartWidth(measuredWidth, viewportWidth);

    setResponsiveChartWidth(current =>
      current === nextWidth ? current : nextWidth,
    );
  }, [responsiveDashboardActive]);

  useLayoutEffect(() => {
    if (!responsiveDashboardActive || typeof window === 'undefined') {
      setResponsiveChartWidth(undefined);
      return undefined;
    }

    measureResponsiveChartWidth();

    const holder = chartHolderRef.current;
    const observedElements: Element[] = [];
    if (holder) {
      observedElements.push(holder);
    }
    if (holder?.parentElement) {
      observedElements.push(holder.parentElement);
    }

    let resizeObserver: ResizeObserver | undefined;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(measureResponsiveChartWidth);
      observedElements.forEach(element => resizeObserver?.observe(element));
    }

    window.addEventListener('resize', measureResponsiveChartWidth);
    window.addEventListener('orientationchange', measureResponsiveChartWidth);

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener('resize', measureResponsiveChartWidth);
      window.removeEventListener(
        'orientationchange',
        measureResponsiveChartWidth,
      );
    };
  }, [measureResponsiveChartWidth, responsiveDashboardActive]);

  const detectResponsiveKpiCard = useCallback(() => {
    const nextResponsiveKpiCard = Boolean(
      responsiveLayout &&
        chartHolderRef.current?.querySelector(RESPONSIVE_KPI_SELECTOR),
    );

    setResponsiveKpiCard(current =>
      current === nextResponsiveKpiCard ? current : nextResponsiveKpiCard,
    );
  }, [responsiveLayout]);

  useEffect(() => {
    if (!responsiveLayout) {
      setResponsiveKpiCard(false);
      return undefined;
    }

    detectResponsiveKpiCard();

    const holder = chartHolderRef.current;
    if (!holder || typeof MutationObserver === 'undefined') {
      return undefined;
    }

    const observer = new MutationObserver(detectResponsiveKpiCard);
    observer.observe(holder, {
      attributeFilter: ['class'],
      attributes: true,
      childList: true,
      subtree: true,
    });

    return () => observer.disconnect();
  }, [chartId, detectResponsiveKpiCard, responsiveLayout]);

  const { chartWidth, chartHeight, effectiveHeightMultiple } = useMemo(() => {
    let width = 0;
    let height = 0;
    let heightMultiple = component.meta.height ?? GRID_MIN_ROW_UNITS;

    if (isFullSize) {
      width = window.innerWidth - CHART_MARGIN;
      height = window.innerHeight - CHART_MARGIN;
    } else {
      width = Math.floor(
        effectiveWidthMultiple * columnWidth +
          (effectiveWidthMultiple - 1) * GRID_GUTTER_SIZE -
          CHART_MARGIN,
      );
      height = Math.floor(
        (component.meta.height ?? 0) * GRID_BASE_UNIT - CHART_MARGIN,
      );
      if (responsiveLayout) {
        width = responsiveChartWidth ?? width;
        height = responsiveKpiCard
          ? getResponsiveKpiChartHeight(height)
          : getResponsiveChartHeight(height);
        heightMultiple = Math.max(
          GRID_MIN_ROW_UNITS,
          Math.ceil((height + CHART_MARGIN) / GRID_BASE_UNIT),
        );
      } else if (responsiveDashboardActive) {
        width = responsiveChartWidth ?? width;
        if (
          chartId != null &&
          PHEM_FILL_HEIGHT_CHART_IDS.has(chartId) &&
          window.innerWidth > RESPONSIVE_DASHBOARD_BREAKPOINTS.compact
        ) {
          height = Math.max(
            height,
            window.innerHeight - PHEM_TALL_VIEWPORT_CHART_OFFSET,
          );
          heightMultiple = Math.max(
            GRID_MIN_ROW_UNITS,
            Math.ceil((height + CHART_MARGIN) / GRID_BASE_UNIT),
          );
        }
      }
    }

    return {
      chartWidth: width,
      chartHeight: height,
      effectiveHeightMultiple: heightMultiple,
    };
  }, [
    columnWidth,
    component.meta.height,
    chartId,
    effectiveWidthMultiple,
    isFullSize,
    responsiveDashboardActive,
    responsiveChartWidth,
    responsiveKpiCard,
    responsiveLayout,
  ]);

  const handleDeleteComponent = useCallback(() => {
    deleteComponent(id, parentId);
  }, [deleteComponent, id, parentId]);

  const handleUpdateSliceName = useCallback(
    (nextName: string) => {
      updateComponents({
        [component.id]: {
          ...component,
          meta: {
            ...component.meta,
            sliceNameOverride: nextName,
          },
        },
      });
    },
    [component, updateComponents],
  );

  const handleToggleFullSize = useCallback(() => {
    setFullSizeChartId(isFullSize ? null : (chartId ?? null));
  }, [chartId, isFullSize, setFullSizeChartId]);

  const handleExtraControl = useCallback((name: string, value: unknown) => {
    setExtraControls(current => ({
      ...current,
      [name]: value,
    }));
  }, []);

  const setChartInteractionLayer = useCallback(
    (active: boolean) => {
      const holder = chartHolderRef.current;
      if (!responsiveDashboardActive || !holder) return;

      holder.classList.toggle(CHART_INTERACTION_HOLDER_CLASS, active);

      [
        holder.closest('.resizable-container'),
        holder.closest('.dragdroppable-column'),
        holder.closest('.dragdroppable-row'),
        holder.closest('.grid-row'),
        holder.closest('.grid-column'),
      ].forEach(element => {
        if (element instanceof HTMLElement) {
          element.classList.toggle(CHART_INTERACTION_LAYOUT_CLASS, active);
        }
      });
    },
    [responsiveDashboardActive],
  );

  useEffect(
    () => () => setChartInteractionLayer(false),
    [setChartInteractionLayer],
  );

  const shouldRenderChart =
    !responsiveLayout || isFullSize || responsiveChartWidth !== undefined;

  const renderChild = useCallback(
    ({ dragSourceRef }: { dragSourceRef?: ConnectDragSource }) => (
      <ResizableContainer
        id={component.id}
        adjustableWidth={parentComponent.type === ROW_TYPE}
        adjustableHeight
        widthStep={columnWidth}
        widthMultiple={effectiveWidthMultiple}
        heightStep={GRID_BASE_UNIT}
        heightMultiple={effectiveHeightMultiple}
        minWidthMultiple={GRID_MIN_COLUMN_COUNT}
        minHeightMultiple={GRID_MIN_ROW_UNITS}
        maxWidthMultiple={availableColumnCount + effectiveWidthMultiple}
        onResizeStart={onResizeStart}
        onResize={onResize}
        onResizeStop={onResizeStop}
        editMode={editMode}
      >
        <div
          ref={el => {
            if (typeof dragSourceRef === 'function') {
              dragSourceRef(el);
            } else if (
              dragSourceRef &&
              Object.prototype.hasOwnProperty.call(dragSourceRef, 'current')
            ) {
              (
                dragSourceRef as React.MutableRefObject<HTMLDivElement | null>
              ).current = el;
            }
            chartHolderRef.current = el;
          }}
          data-test="dashboard-component-chart-holder"
          style={focusHighlightStyles}
          css={isFullSize ? fullSizeStyle : undefined}
          onMouseEnter={() => setChartInteractionLayer(true)}
          onMouseLeave={() => setChartInteractionLayer(false)}
          onFocus={() => setChartInteractionLayer(true)}
          onBlur={event => {
            const nextTarget = event.relatedTarget;
            if (
              !(nextTarget instanceof Node) ||
              !event.currentTarget.contains(nextTarget)
            ) {
              setChartInteractionLayer(false);
            }
          }}
          className={cx(
            'dashboard-component',
            'dashboard-component-chart-holder',
            // The following class is added to support custom dashboard styling via the CSS editor
            `dashboard-chart-id-${chartId}`,
            responsiveKpiCard && RESPONSIVE_KPI_CARD_CLASS,
            outlinedComponentId ? 'fade-in' : 'fade-out',
          )}
        >
          <AntdThemeProvider
            getPopupContainer={(triggerNode: HTMLElement) =>
              document.fullscreenElement
                ? (triggerNode?.closest?.(
                    '[data-test="dashboard-component-chart-holder"]',
                  ) as HTMLElement) || document.body
                : document.body
            }
          >
            {!editMode && (
              <AnchorLink
                id={component.id}
                scrollIntoView={outlinedComponentId === component.id}
              />
            )}
            {!!outlinedComponentId && (
              <style>
                {`label[for=${outlinedColumnName}] + .Select .Select__control {
                      border-color: ${theme.colorPrimary};
                      transition: border-color 1s ease-in-out;
                    }`}
              </style>
            )}
            {shouldRenderChart && (
              <Chart
                componentId={component.id}
                id={component.meta.chartId ?? 0}
                dashboardId={dashboardId}
                width={chartWidth}
                height={chartHeight}
                sliceName={
                  component.meta.sliceNameOverride ||
                  component.meta.sliceName ||
                  ''
                }
                updateSliceName={(_sliceId: number, name: string) =>
                  handleUpdateSliceName(name)
                }
                isComponentVisible={isComponentVisible}
                handleToggleFullSize={handleToggleFullSize}
                isFullSize={isFullSize}
                setControlValue={handleExtraControl}
                extraControls={extraControls}
                isInView={isInView}
                chartHolderRef={chartHolderRef}
                responsiveLayout={responsiveLayout}
              />
            )}
            {editMode && (
              <HoverMenu position="top">
                <div data-test="dashboard-delete-component-button">
                  <DeleteComponentButton onDelete={handleDeleteComponent} />
                </div>
              </HoverMenu>
            )}
          </AntdThemeProvider>
        </div>
      </ResizableContainer>
    ),
    [
      component.id,
      component.meta.height,
      component.meta.chartId,
      component.meta.sliceNameOverride,
      component.meta.sliceName,
      parentComponent.type,
      columnWidth,
      widthMultiple,
      effectiveWidthMultiple,
      availableColumnCount,
      onResizeStart,
      onResize,
      onResizeStop,
      editMode,
      focusHighlightStyles,
      isFullSize,
      fullSizeStyle,
      chartId,
      outlinedComponentId,
      outlinedColumnName,
      dashboardId,
      chartWidth,
      chartHeight,
      effectiveHeightMultiple,
      handleUpdateSliceName,
      isComponentVisible,
      handleToggleFullSize,
      handleExtraControl,
      extraControls,
      isInView,
      responsiveLayout,
      setChartInteractionLayer,
      shouldRenderChart,
      handleDeleteComponent,
    ],
  );

  return (
    <Draggable
      component={component}
      parentComponent={parentComponent}
      orientation={parentComponent.type === ROW_TYPE ? 'column' : 'row'}
      index={index}
      depth={depth}
      onDrop={handleComponentDrop}
      disableDragDrop={false}
      editMode={editMode}
    >
      {renderChild}
    </Draggable>
  );
};

export default memo(ChartHolder);
