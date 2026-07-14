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
/* eslint-env browser */
import cx from 'classnames';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { t } from '@apache-superset/core/translation';
import { addAlpha, JsonObject, useElementOnScreen } from '@superset-ui/core';
import { css, styled, useTheme } from '@apache-superset/core/theme';
import { useDispatch, useSelector } from 'react-redux';
import { EmptyState, Loading } from '@superset-ui/core/components';
import { ErrorBoundary, BasicErrorAlert } from 'src/components';
import BuilderComponentPane from 'src/dashboard/components/BuilderComponentPane';
import DashboardHeader from 'src/dashboard/components/Header';
import { Icons } from '@superset-ui/core/components/Icons';
import IconButton from 'src/dashboard/components/IconButton';
import { Droppable } from 'src/dashboard/components/dnd/DragDroppable';
import DashboardComponent from 'src/dashboard/containers/DashboardComponent';
import WithPopoverMenu from 'src/dashboard/components/menu/WithPopoverMenu';
import getDirectPathToTabIndex from 'src/dashboard/util/getDirectPathToTabIndex';
import { URL_PARAMS } from 'src/constants';
import { getUrlParam } from 'src/utils/urlUtils';
import {
  DashboardLayout,
  DashboardInfo,
  FilterBarOrientation,
  RootState,
} from 'src/dashboard/types';
import {
  setDirectPathToChild,
  setEditMode,
} from 'src/dashboard/actions/dashboardState';
import {
  deleteTopLevelTabs,
  handleComponentDrop,
  clearDashboardHistory,
} from 'src/dashboard/actions/dashboardLayout';
import { DropResult } from 'src/dashboard/components/dnd/dragDroppableConfig';
import {
  DASHBOARD_GRID_ID,
  DASHBOARD_ROOT_DEPTH,
  DASHBOARD_ROOT_ID,
  DashboardStandaloneMode,
} from 'src/dashboard/util/constants';
import FilterBar from 'src/dashboard/components/nativeFilters/FilterBar';
import { useUiConfig } from 'src/components/UiConfigContext';
import ResizableSidebar from 'src/components/ResizableSidebar';
import {
  BUILDER_SIDEPANEL_WIDTH,
  CLOSED_FILTER_BAR_SHELL_WIDTH,
  CLOSED_FILTER_BAR_WIDTH,
  FILTER_BAR_SHELL_PADDING,
  FILTER_BAR_SHELL_WIDTH_OFFSET,
  FILTER_BAR_HEADER_HEIGHT,
  MAIN_HEADER_HEIGHT,
  OPEN_FILTER_BAR_SHELL_MAX_WIDTH,
  OPEN_FILTER_BAR_SHELL_WIDTH,
  EMPTY_CONTAINER_Z_INDEX,
} from 'src/dashboard/constants';
import {
  RESPONSIVE_DASHBOARD_BREAKPOINTS,
  RESPONSIVE_DASHBOARD_BODY_CLASS,
  RESPONSIVE_DASHBOARD_CLASS,
  RESPONSIVE_DASHBOARD_MOBILE_BODY_CLASS,
  RESPONSIVE_DASHBOARD_MOBILE_CLASS,
  isResponsiveDashboardEnabled,
  isResponsiveDashboardMobileViewport,
} from 'src/dashboard/util/responsiveDashboard';
import { getRootLevelTabsComponent, shouldFocusTabs } from './utils';
import DashboardContainer from './DashboardContainer';
import { useNativeFilters } from './state';
import DashboardWrapper from './DashboardWrapper';

// @z-index-above-dashboard-charts + 1 = 11
const FiltersPanel = styled.div<{ width: number; hidden: boolean }>`
  background-color: #e8f2fb;
  border-right: 2px solid #2893b3;
  box-sizing: border-box;
  grid-column: 1;
  grid-row: 1 / span 2;
  padding: ${FILTER_BAR_SHELL_PADDING}px;
  z-index: 11;
  width: ${({ width }) => width}px;
  ${({ hidden }) => hidden && `display: none;`}
`;

const StickyPanel = styled.div<{ width: number }>`
  position: sticky;
  top: -1px;
  width: ${({ width }) => width}px;
  flex: 0 0 ${({ width }) => width}px;
`;

// @z-index-above-dashboard-popovers (99) + 1 = 100
const StyledHeader = styled.div<{ filterBarWidth: number }>`
  ${({ theme, filterBarWidth }) => {
    const hasVerticalFilterBar = filterBarWidth > 0;
    const compactGridColumn = hasVerticalFilterBar ? '2' : '1 / -1';
    const compactHeaderWidth = `calc(100vw - ${filterBarWidth}px)`;
    const headerInsetWidth = hasVerticalFilterBar
      ? '100%'
      : `calc(100vw - ${theme.sizeUnit * 4}px)`;
    const headerInsetMarginLeft = hasVerticalFilterBar
      ? '0'
      : `${theme.sizeUnit * 2}px`;

    return css`
    grid-column: 2;
    grid-row: 1;
    position: sticky;
    top: 0;
    z-index: 99;
    box-sizing: border-box;
    max-width: calc(100vw - ${filterBarWidth}px);
    min-width: 0;
    width: calc(100vw - ${filterBarWidth}px);

    .empty-droptarget {
      min-height: ${theme.sizeUnit * 4}px;
    }

    .empty-droptarget:before {
      position: absolute;
      content: '';
      display: none;
      width: calc(100% - ${theme.sizeUnit * 2}px);
      height: calc(100% - ${theme.sizeUnit * 2}px);
      left: ${theme.sizeUnit}px;
      top: ${theme.sizeUnit}px;
      border: 1px dashed transparent;
      border-radius: ${theme.borderRadius}px;
      opacity: 0.5;
    }

    body.${RESPONSIVE_DASHBOARD_BODY_CLASS}
      &
      > [data-test='dragdroppable-object'] {
      margin-left: ${headerInsetMarginLeft} !important;
      max-width: ${headerInsetWidth} !important;
      min-width: 0 !important;
      width: ${headerInsetWidth} !important;
    }

    body.${RESPONSIVE_DASHBOARD_BODY_CLASS}
      &
      > [data-test='dragdroppable-object']
      .dashboard-component-tabs,
    body.${RESPONSIVE_DASHBOARD_BODY_CLASS}
      &
      > [data-test='dragdroppable-object']
      .dashboard-component-tabs
      > .ant-tabs,
    body.${RESPONSIVE_DASHBOARD_BODY_CLASS}
      &
      > [data-test='dragdroppable-object']
      .dashboard-component-tabs
      .ant-tabs-content-holder,
    body.${RESPONSIVE_DASHBOARD_BODY_CLASS}
      &
      > [data-test='dragdroppable-object']
      .dashboard-component-tabs
      .ant-tabs-content,
    body.${RESPONSIVE_DASHBOARD_BODY_CLASS}
      &
      > [data-test='dragdroppable-object']
      .dashboard-component-tabs
      .ant-tabs-tabpane {
      box-sizing: border-box;
      max-width: 100% !important;
      min-width: 0 !important;
      width: 100% !important;
    }

    @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
      body.${RESPONSIVE_DASHBOARD_BODY_CLASS} & {
        box-sizing: border-box;
        grid-column: ${compactGridColumn};
        max-width: ${compactHeaderWidth};
        min-width: 0;
        overflow-x: hidden;
        padding-inline: ${hasVerticalFilterBar
          ? 0
          : `${theme.sizeUnit * 2}px`};
        width: ${compactHeaderWidth};

        & > [data-test='dragdroppable-object'] {
          margin-left: 0 !important;
          max-width: 100% !important;
          min-width: 0 !important;
          width: 100% !important;
        }

        .dashboard-component-tabs,
        .dashboard-component-tabs > .ant-tabs,
        .dashboard-component-tabs .ant-tabs-content-holder,
        .dashboard-component-tabs .ant-tabs-content,
        .dashboard-component-tabs .ant-tabs-tabpane {
          box-sizing: border-box;
          max-width: 100% !important;
          min-width: 0 !important;
          width: 100% !important;
        }

        .dashboard-component-tabs > .ant-tabs > .ant-tabs-nav {
          max-width: 100%;
          overflow-x: auto;
        }
      }
    }
  `;
  }}
`;

const StyledContent = styled.div<{
  fullSizeChartId: number | null;
  filterBarWidth: number;
}>`
  ${({ filterBarWidth }) => css`
  grid-column: 2;
  grid-row: 2;
  box-sizing: border-box;
  max-width: calc(100vw - ${filterBarWidth}px);
  min-width: 0;
  width: calc(100vw - ${filterBarWidth}px);
  // @z-index-above-dashboard-header (100) + 1 = 101
  `}

  ${({ fullSizeChartId }) => fullSizeChartId && `z-index: 101;`}

  @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
    body.${RESPONSIVE_DASHBOARD_BODY_CLASS} & {
      grid-column: ${({ filterBarWidth }) =>
        filterBarWidth > 0 ? '2' : '1 / -1'};
      max-width: calc(100vw - ${({ filterBarWidth }) => filterBarWidth}px);
      min-width: 0;
      overflow-x: hidden;
      width: calc(100vw - ${({ filterBarWidth }) => filterBarWidth}px);
    }
  }

  body.${RESPONSIVE_DASHBOARD_MOBILE_BODY_CLASS} & {
    grid-column: 1 / -1;
    max-width: 100%;
    min-width: 0;
    overflow-x: hidden;
    width: 100%;
  }
`;

const DashboardContentWrapper = styled.div`
  ${({ theme }) => css`
    &.dashboard {
      position: relative;
      flex-grow: 1;
      display: flex;
      flex-direction: column;
      height: 100%;

      /* drop shadow for top-level tabs only */
      & .dashboard-component-tabs {
        box-shadow: 0 ${theme.sizeUnit}px ${theme.sizeUnit}px 0
          ${addAlpha(theme.colorBorderSecondary, 0.1)};
        padding-left: ${theme.sizeUnit *
        2}px; /* note this is added to tab-level padding, to match header */
      }

      .dropdown-toggle.btn.btn-primary .caret {
        color: ${theme.colorText};
      }

      .background--transparent {
        background-color: transparent;
      }

      .background--white {
        background-color: ${theme.colorBgContainer};
      }
    }

    &.${RESPONSIVE_DASHBOARD_MOBILE_CLASS} {
      box-sizing: border-box;
      max-width: 100vw;
      min-width: 0;
      overflow-x: hidden;
      width: 100vw;
    }

    &.dashboard--editing {
      .grid-row:after,
      .dashboard-component-tabs > .hover-menu:hover + div:after {
        border: 1px dashed transparent;
        content: '';
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        z-index: 1;
        pointer-events: none;
      }

      .grid-row.grid-row--hovered:after,
      .dashboard-component-tabs > .grid-row--hovered:after {
        border: 2px dashed ${theme.colorPrimary};
      }

      .resizable-container {
        & .dashboard-component-chart-holder {
          .dashboard-chart {
            .chart-container {
              cursor: move;
              opacity: 0.2;
            }

            .slice_container {
              /* disable chart interactions in edit mode */
              pointer-events: none;
            }
          }

          &:hover .dashboard-chart .chart-container {
            opacity: 0.7;
          }
        }

        &:hover,
        &.resizable-container--resizing:hover {
          & > .dashboard-component-chart-holder:after {
            border: 1px dashed ${theme.colorPrimary};
          }
        }
      }

      .resizable-container--resizing:hover > .grid-row:after,
      .hover-menu:hover + .grid-row:after,
      .dashboard-component-tabs > .hover-menu:hover + div:after {
        border: 1px dashed ${theme.colorPrimary};
        z-index: 2;
      }

      .grid-row:after,
      .dashboard-component-tabs > .hover-menu + div:after {
        border: 1px dashed ${theme.colorBorder};
      }

      /* provide hit area in case row contents is edge to edge */
      .dashboard-component-tabs-content {
        > .dragdroppable-row {
          padding-top: ${theme.sizeUnit * 4}px;
        }
      }

      .dashboard-component-chart-holder {
        &:after {
          content: '';
          position: absolute;
          width: 100%;
          height: 100%;
          top: 0;
          left: 0;
          z-index: 1;
          pointer-events: none;
          border: 1px solid transparent;
        }

        &:hover:after {
          border: 1px dashed ${theme.colorPrimary};
          z-index: 2;
        }
      }

      .contract-trigger:before {
        display: none;
      }
    }

    & .dashboard-component-tabs-content {
      & > div:not(:last-child):not(.empty-droptarget) {
        margin-bottom: ${theme.sizeUnit * 4}px;
      }

      & > .empty-droptarget {
        z-index: ${EMPTY_CONTAINER_Z_INDEX};
        position: absolute;
        width: 100%;
      }

      & > .empty-droptarget:first-of-type:not(.empty-droptarget--full) {
        height: ${theme.sizeUnit * 4}px;
        top: 0;
      }

      & > .empty-droptarget:last-child {
        height: ${theme.sizeUnit * 4}px;
        bottom: ${-theme.sizeUnit * 4}px;
      }
    }
  `}
`;

const StyledDashboardContent = styled.div<{
  editMode: boolean;
  marginLeft: number;
}>`
  ${({ theme, editMode, marginLeft }) => css`
    background-color: ${theme.colorBgLayout};
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    height: auto;
    flex: 1;

    .grid-container .dashboard-component-tabs {
      box-shadow: none;
      padding-left: 0;
    }

    .grid-container {
      /* without this, the grid will not get smaller upon toggling the builder panel on */
      width: 0;
      flex: 1;
      position: relative;
      margin: ${theme.sizeUnit * 4}px;
      margin-left: ${marginLeft}px;

      ${editMode &&
      `
      max-width: calc(100% - ${
        BUILDER_SIDEPANEL_WIDTH + theme.sizeUnit * 16
      }px);
    `}

      /* this is the ParentSize wrapper */
    & > div:first-of-type {
        height: 100% !important;
      }
    }

    .dashboard-builder-sidepane {
      width: ${BUILDER_SIDEPANEL_WIDTH}px;
      z-index: 1;
    }

    .${RESPONSIVE_DASHBOARD_CLASS} & {
      .dragdroppable-column,
      .grid-column,
      .resizable-container,
      .dashboard-component-chart-holder {
        z-index: 0;
      }

      .dragdroppable:hover,
      .dragdroppable:focus-within,
      .grid-row:hover,
      .grid-row:focus-within,
      .grid-column:hover,
      .grid-column:focus-within,
      .resizable-container:hover,
      .resizable-container:focus-within,
      .dashboard-component-chart-layout--interaction-active {
        z-index: 30;
      }

      .dashboard-component-chart-holder:hover,
      .dashboard-component-chart-holder:focus-within,
      .dashboard-component-chart-holder--interaction-active {
        z-index: 31;
      }

      .dragdroppable-column.dashboard-component-chart-layout--interaction-active {
        transform: none !important;
      }

      .dashboard-component-chart-holder .chart-tooltip,
      .dashboard-component-chart-holder [class*='tooltip'] {
        z-index: 32 !important;
      }

      .superset-legacy-chart-big-number .text-container,
      .superset-legacy-chart-big-number .header-line {
        max-width: 100% !important;
      }

      .superset-legacy-chart-big-number .header-line {
        font-size: clamp(42px, 3.75vw, 80px) !important;
        white-space: nowrap !important;
      }

      .dashboard-component-chart-holder .pivot_table_v_2,
      .dashboard-component-chart-holder .ant-table-wrapper,
      .dashboard-component-chart-holder .table-condensed,
      .dashboard-component-chart-holder .pvtTable,
      .dashboard-component-chart-holder .ag-root-wrapper {
        max-width: 100% !important;
      }

      .dashboard-component-chart-holder .pvtTable {
        display: block !important;
        table-layout: auto !important;
        width: 100% !important;
      }

      .dashboard-component-chart-holder .pvtTable th,
      .dashboard-component-chart-holder .pvtTable td {
        overflow-wrap: anywhere !important;
        white-space: normal !important;
      }

      .dashboard-component-chart-holder .pivot_table_v_2,
      .dashboard-component-chart-holder .ant-table-wrapper,
      .dashboard-component-chart-holder .pvtTable,
      .dashboard-component-chart-holder .ag-root-wrapper {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
      }
    }

    @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
      .${RESPONSIVE_DASHBOARD_CLASS} & {
        min-width: 0;
        overflow-x: hidden;
        width: 100%;

        .grid-container {
          margin: ${theme.sizeUnit * 2}px;
          margin-left: ${theme.sizeUnit * 2}px;
          max-width: calc(100% - ${theme.sizeUnit * 4}px);
          min-width: 0;
          width: calc(100% - ${theme.sizeUnit * 4}px) !important;
        }

        .dashboard-grid,
        .grid-content,
        .dragdroppable,
        .dragdroppable-row,
        .dragdroppable-column,
        .grid-row,
        .grid-column,
        .resizable-container,
        .dashboard-component-tabs,
        .dashboard-component-tabs-content,
        .ant-tabs,
        .ant-tabs-content,
        .ant-tabs-tabpane {
          max-width: 100% !important;
          min-width: 0 !important;
          width: 100% !important;
        }

        .dashboard-component-chart-holder {
          margin-inline: ${theme.sizeUnit}px !important;
          max-width: calc(100% - ${theme.sizeUnit * 2}px) !important;
          min-width: 0;
          overflow: visible !important;
          padding: ${theme.sizeUnit * 2}px !important;
          width: calc(100% - ${theme.sizeUnit * 2}px) !important;
        }

        .dashboard-component-chart-holder .dashboard-chart,
        .dashboard-component-chart-holder
          .dashboard-chart.dashboard-chart--overflowable,
        .dashboard-component-chart-holder [data-test='chart-container'],
        .dashboard-component-chart-holder [data-test='slice-container'],
        .dashboard-component-chart-holder .slice_container,
        .dashboard-component-chart-holder [data-test='slice-container'] > div {
          padding-left: 0 !important;
          padding-right: 0 !important;
          overflow: visible !important;
        }

        .dashboard-component-chart-holder [data-test='chart-container'] svg {
          max-width: 100% !important;
        }

        .dashboard-component-chart-holder .slice-header,
        .dashboard-component-chart-holder [data-test='slice-header'] {
          height: max-content !important;
          margin-bottom: ${theme.sizeUnit * 2}px !important;
          min-height: max-content !important;
          overflow: visible !important;
        }

        .dashboard-component-chart-holder .header-title {
          display: block !important;
          max-width: calc(100% - ${theme.sizeUnit * 12}px) !important;
          overflow: visible !important;
          text-overflow: clip !important;
          white-space: normal !important;
          -webkit-line-clamp: unset !important;
        }
      }
    }

    .${RESPONSIVE_DASHBOARD_MOBILE_CLASS} & {
      box-sizing: border-box;
      flex-direction: column;
      width: 100%;
      min-width: 0;
      overflow-x: hidden;
      padding-bottom: calc(
        ${theme.sizeUnit * 16}px + env(safe-area-inset-bottom)
      );

      .grid-container {
        box-sizing: border-box;
        width: calc(100% - ${theme.sizeUnit * 4}px) !important;
        min-width: 0;
        max-width: calc(100% - ${theme.sizeUnit * 4}px);
        margin: ${theme.sizeUnit * 2}px;
        margin-left: ${theme.sizeUnit * 2}px;
      }

      .dashboard-grid,
      .grid-content,
      .dragdroppable,
      .dragdroppable-row,
      .dragdroppable-column,
      .grid-row,
      .grid-column,
      .resizable-container,
      .dashboard-component-tabs,
      .dashboard-component-tabs-content,
      .ant-tabs,
      .ant-tabs-content,
      .ant-tabs-tabpane {
        box-sizing: border-box !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
      }

      .dashboard-component-chart-holder {
        box-sizing: border-box !important;
        width: calc(100% - ${theme.sizeUnit * 2}px) !important;
        max-width: calc(100% - ${theme.sizeUnit * 2}px) !important;
        margin-inline: ${theme.sizeUnit}px !important;
        padding: ${theme.sizeUnit * 2}px !important;
        min-width: 0;
        overflow-x: hidden !important;
        overflow-y: hidden !important;
      }

      .chart-slice {
        box-sizing: border-box;
        width: 100%;
        min-width: 0;
        max-width: 100%;
      }

      .dashboard-chart,
      .dashboard-component-chart-holder
        .dashboard-chart.dashboard-chart--overflowable,
      [data-test='chart-container'],
      [data-test='chart-grid-component'],
      [data-test='slice-container'],
      [data-test='slice-container'] > div {
        box-sizing: border-box !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
        overflow-y: hidden !important;
      }

      [data-test='slice-container'] > div {
        flex-shrink: 1 !important;
      }

      [data-test='chart-container'] svg {
        max-width: 100% !important;
      }

      .dashboard-component-chart-holder .slice-header,
      .dashboard-component-chart-holder [data-test='slice-header'] {
        height: max-content !important;
        margin-bottom: ${theme.sizeUnit * 2}px !important;
        min-height: max-content !important;
        overflow: visible !important;
      }

      .dashboard-component-chart-holder .header-title {
        display: block !important;
        max-width: calc(100% - ${theme.sizeUnit * 12}px) !important;
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: normal !important;
        -webkit-line-clamp: unset !important;
      }

      .superset-legacy-chart-big-number .text-container,
      .superset-legacy-chart-big-number .header-line {
        max-width: 100% !important;
      }

      .superset-legacy-chart-big-number .header-line {
        font-size: clamp(42px, 13vw, 80px) !important;
        white-space: nowrap !important;
      }

      .dashboard-component-chart-holder--compact-kpi
        .superset-legacy-chart-big-number,
      .dashboard-component-chart-holder--compact-kpi
        .superset-legacy-chart-big-number
        .text-container {
        align-items: center !important;
        display: flex !important;
        justify-content: center !important;
        text-align: center !important;
        width: 100% !important;
      }

      .dashboard-component-chart-holder--compact-kpi
        .superset-legacy-chart-big-number {
        height: 100% !important;
      }

      .dashboard-component-chart-holder--compact-kpi
        .superset-legacy-chart-big-number
        .text-container {
        min-height: 100% !important;
      }

      .dashboard-component-chart-holder--compact-kpi
        .superset-legacy-chart-big-number
        .header-line {
        justify-content: center !important;
        margin-bottom: 0 !important;
        text-align: center !important;
        width: 100% !important;
      }

      [data-test='slice-container'] table,
      .ant-table-wrapper,
      .table-condensed,
      .pvtTable,
      .ag-root-wrapper {
        max-width: 100%;
      }

      .ant-table-wrapper,
      .pvtTable,
      .ag-root-wrapper {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
      }

      canvas,
      svg {
        max-width: 100%;
      }

      .slice-header,
      .header-title {
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .ant-btn {
        min-height: 44px;
        min-width: 44px;
      }
    }

    .dashboard-component-chart-holder {
      width: 100%;
      height: 100%;
      background-color: ${theme.colorBgContainer};
      position: relative;
      padding: ${theme.sizeUnit * 4}px;
      box-sizing: border-box;
      overflow-y: visible;

      // transitionable traits to show filter relevance
      transition:
        opacity ${theme.motionDurationMid} ease-in-out,
        border-color ${theme.motionDurationMid} ease-in-out,
        box-shadow ${theme.motionDurationMid} ease-in-out;

      &.fade-in {
        border-radius: ${theme.borderRadius}px;
        box-shadow:
          inset 0 0 0 2px ${theme.colorPrimary},
          0 0 0 3px ${addAlpha(theme.colorPrimary, 0.1)};
      }

      &.fade-out {
        border-radius: ${theme.borderRadius}px;
        box-shadow: 0 0 0 1px ${addAlpha(theme.colorBorder, 0.5)};
      }

      & .missing-chart-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        overflow-y: auto;
        justify-content: center;

        .missing-chart-body {
          font-size: ${theme.fontSizeSM}px;
          position: relative;
          display: flex;
        }
      }
    }

    @media (min-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact + 1}px) {
      .${RESPONSIVE_DASHBOARD_CLASS} & {
        .dashboard-component-chart-holder {
          max-width: 100% !important;
          overflow: visible !important;
          padding: ${theme.sizeUnit * 4}px !important;
          width: 100% !important;
        }

        .dashboard-component-chart-holder .dashboard-chart,
        .dashboard-component-chart-holder
          .dashboard-chart.dashboard-chart--overflowable,
        .dashboard-component-chart-holder [data-test='chart-container'],
        .dashboard-component-chart-holder [data-test='slice-container'],
        .dashboard-component-chart-holder .slice_container,
        .dashboard-component-chart-holder [data-test='slice-container'] > div {
          overflow: visible !important;
        }

        .dashboard-component-chart-holder [data-test='chart-container'] svg {
          max-width: 100% !important;
        }

        .dashboard-component-chart-holder .slice-header,
        .dashboard-component-chart-holder [data-test='slice-header'] {
          height: max-content !important;
          margin-bottom: ${theme.sizeUnit * 2}px !important;
          min-height: max-content !important;
          overflow: visible !important;
        }

        .dashboard-component-chart-holder .header-title {
          display: block !important;
          max-width: calc(100% - ${theme.sizeUnit * 12}px) !important;
          overflow: visible !important;
          text-overflow: clip !important;
          white-space: normal !important;
          -webkit-line-clamp: unset !important;
        }
      }
    }
  `}
`;

const ELEMENT_ON_SCREEN_OPTIONS = {
  threshold: [1],
};

const getViewportSize = () => ({
  width: typeof window === 'undefined' ? 0 : window.innerWidth,
  height: typeof window === 'undefined' ? 0 : window.innerHeight,
});

const DashboardBuilder = () => {
  const dispatch = useDispatch();
  const uiConfig = useUiConfig();
  const theme = useTheme();
  const [viewportSize, setViewportSize] = useState(getViewportSize);

  const dashboardInfo = useSelector<RootState, DashboardInfo>(
    state => state.dashboardInfo,
  );
  const dashboardId = `${dashboardInfo.id}`;
  const responsiveDashboardEnabled =
    isResponsiveDashboardEnabled(dashboardInfo);
  const dashboardLayout = useSelector<RootState, DashboardLayout>(
    state => state.dashboardLayout.present,
  );
  const editMode = useSelector<RootState, boolean>(
    state => state.dashboardState.editMode,
  );
  const canEdit = useSelector<RootState, boolean>(
    ({ dashboardInfo }) => dashboardInfo.dash_edit_perm,
  );
  const dashboardIsSaving = useSelector<RootState, boolean>(
    ({ dashboardState }) => dashboardState.dashboardIsSaving,
  );
  const fullSizeChartId = useSelector<RootState, number | null>(
    state => state.dashboardState.fullSizeChartId,
  );
  const filterBarOrientation = useSelector<RootState, FilterBarOrientation>(
    ({ dashboardInfo }) => dashboardInfo.filterBarOrientation,
  );
  const responsiveDashboardMobile =
    responsiveDashboardEnabled &&
    !editMode &&
    isResponsiveDashboardMobileViewport(
      viewportSize.width,
      viewportSize.height,
    );

  useEffect(() => {
    const syncViewportSize = () => {
      setViewportSize(getViewportSize());
    };

    syncViewportSize();
    window.addEventListener('resize', syncViewportSize);
    window.addEventListener('orientationchange', syncViewportSize);

    return () => {
      window.removeEventListener('resize', syncViewportSize);
      window.removeEventListener('orientationchange', syncViewportSize);
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle(
      RESPONSIVE_DASHBOARD_BODY_CLASS,
      responsiveDashboardEnabled,
    );
    document.body.classList.toggle(
      RESPONSIVE_DASHBOARD_MOBILE_BODY_CLASS,
      responsiveDashboardMobile,
    );

    return () => {
      document.body.classList.remove(RESPONSIVE_DASHBOARD_BODY_CLASS);
      document.body.classList.remove(RESPONSIVE_DASHBOARD_MOBILE_BODY_CLASS);
    };
  }, [responsiveDashboardEnabled, responsiveDashboardMobile]);

  useEffect(() => {
    if (!responsiveDashboardEnabled) return undefined;

    const targets = [
      document.documentElement,
      document.body,
      document.getElementById('app'),
    ].filter((element): element is HTMLElement => Boolean(element));
    const previousStyles = targets.map(element => ({
      element,
      maxWidth: element.style.maxWidth,
      maxWidthPriority: element.style.getPropertyPriority('max-width'),
      overflowX: element.style.overflowX,
      overflowXPriority: element.style.getPropertyPriority('overflow-x'),
    }));

    targets.forEach(element => {
      element.style.setProperty('max-width', '100vw', 'important');
      element.style.setProperty('overflow-x', 'hidden', 'important');
    });

    return () => {
      previousStyles.forEach(
        ({
          element,
          maxWidth,
          maxWidthPriority,
          overflowX,
          overflowXPriority,
        }) => {
          element.style.setProperty(
            'max-width',
            maxWidth,
            maxWidthPriority,
          );
          element.style.setProperty(
            'overflow-x',
            overflowX,
            overflowXPriority,
          );
        },
      );
    };
  }, [responsiveDashboardEnabled]);

  useEffect(() => {
    if (!responsiveDashboardMobile) return undefined;

    const dismissRotateOverlay = () => {
      const overlay = document.getElementById('moh-rotate-overlay');
      if (!overlay) return;
      overlay.classList.add('moh-dismissed');
      overlay.setAttribute('aria-hidden', 'true');
    };

    dismissRotateOverlay();

    const observer = new MutationObserver(dismissRotateOverlay);
    observer.observe(document.body, { childList: true });
    window.addEventListener('resize', dismissRotateOverlay);
    window.addEventListener('orientationchange', dismissRotateOverlay);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', dismissRotateOverlay);
      window.removeEventListener('orientationchange', dismissRotateOverlay);
    };
  }, [responsiveDashboardMobile]);

  const handleChangeTab = useCallback(
    ({ pathToTabIndex }: { pathToTabIndex: string[] }) => {
      dispatch(setDirectPathToChild(pathToTabIndex));
      window.scrollTo(0, 0);
    },
    [dispatch],
  );

  const handleDeleteTopLevelTabs = useCallback(() => {
    dispatch(deleteTopLevelTabs());

    const firstTab = getDirectPathToTabIndex(
      getRootLevelTabsComponent(dashboardLayout),
      0,
    );
    dispatch(setDirectPathToChild(firstTab));
  }, [dashboardLayout, dispatch]);

  const handleDrop = useCallback(
    (dropResult: DropResult) => dispatch(handleComponentDrop(dropResult)),
    [dispatch],
  );

  const headerRef = useRef<HTMLDivElement>(null);
  const dashboardRoot = dashboardLayout[DASHBOARD_ROOT_ID];
  const rootChildId = dashboardRoot?.children[0];
  const topLevelTabs =
    rootChildId !== DASHBOARD_GRID_ID
      ? dashboardLayout[rootChildId]
      : undefined;
  const standaloneMode = getUrlParam(URL_PARAMS.standalone);
  const isReport = standaloneMode === DashboardStandaloneMode.Report;
  const hideDashboardHeader =
    uiConfig.hideTitle ||
    standaloneMode === DashboardStandaloneMode.HideNavAndTitle ||
    isReport;

  const [barTopOffset, setBarTopOffset] = useState(0);
  const [currentFilterBarWidth, setCurrentFilterBarWidth] = useState(
    CLOSED_FILTER_BAR_SHELL_WIDTH,
  );

  useEffect(() => {
    setBarTopOffset(headerRef.current?.getBoundingClientRect()?.height || 0);

    let observer: ResizeObserver;
    if (global.hasOwnProperty('ResizeObserver') && headerRef.current) {
      observer = new ResizeObserver(entries => {
        setBarTopOffset(
          current => entries?.[0]?.contentRect?.height || current,
        );
      });

      observer.observe(headerRef.current);
    }

    return () => {
      observer?.disconnect();
    };
  }, []);

  const {
    showDashboard,
    missingInitialFilters,
    dashboardFiltersOpen,
    toggleDashboardFiltersOpen,
    nativeFiltersEnabled,
  } = useNativeFilters();

  const [containerRef, isSticky] = useElementOnScreen<HTMLDivElement>(
    ELEMENT_ON_SCREEN_OPTIONS,
  );

  const showFilterBar = !editMode && nativeFiltersEnabled;

  const offset =
    FILTER_BAR_HEADER_HEIGHT +
    (isSticky || standaloneMode ? 0 : MAIN_HEADER_HEIGHT);

  const filterBarHeight = `calc(100vh - ${offset}px)`;
  const filterBarOffset = dashboardFiltersOpen ? 0 : barTopOffset + 20;

  const draggableStyle = useMemo(
    () => ({
      marginLeft:
        dashboardFiltersOpen ||
        editMode ||
        responsiveDashboardEnabled ||
        responsiveDashboardMobile ||
        !nativeFiltersEnabled ||
        filterBarOrientation === FilterBarOrientation.Horizontal
          ? 0
          : -32,
    }),
    [
      dashboardFiltersOpen,
      editMode,
      responsiveDashboardEnabled,
      responsiveDashboardMobile,
      filterBarOrientation,
      nativeFiltersEnabled,
    ],
  );

  // If a new tab was added, update the directPathToChild to reflect it
  const currentTopLevelTabs = useRef(topLevelTabs);
  useEffect(() => {
    const currentTabsLength = currentTopLevelTabs.current?.children?.length;
    const newTabsLength = topLevelTabs?.children?.length;

    if (
      currentTabsLength !== undefined &&
      newTabsLength !== undefined &&
      newTabsLength > currentTabsLength
    ) {
      const lastTab = getDirectPathToTabIndex(
        getRootLevelTabsComponent(dashboardLayout),
        newTabsLength - 1,
      );
      dispatch(setDirectPathToChild(lastTab));
    }

    currentTopLevelTabs.current = topLevelTabs;
  }, [topLevelTabs]);

  const headerContent = useMemo(
    () => (
      <>
        {!hideDashboardHeader && <DashboardHeader />}
        {showFilterBar &&
          !responsiveDashboardMobile &&
          filterBarOrientation === FilterBarOrientation.Horizontal && (
            <FilterBar
              orientation={FilterBarOrientation.Horizontal}
              hidden={isReport}
            />
          )}
      </>
    ),
    [
      hideDashboardHeader,
      showFilterBar,
      responsiveDashboardMobile,
      filterBarOrientation,
      isReport,
    ],
  );

  const renderDraggableContent = useCallback(
    ({ dropIndicatorProps }: { dropIndicatorProps: JsonObject }) => (
      <div>
        {dropIndicatorProps && <div {...dropIndicatorProps} />}
        {!isReport &&
          topLevelTabs &&
          !uiConfig.hideTab &&
          !uiConfig.hideNav && (
            <WithPopoverMenu
              shouldFocus={shouldFocusTabs}
              menuItems={[
                <IconButton
                  key="collapse-tabs"
                  icon={<Icons.FallOutlined iconSize="xl" />}
                  label={t('Collapse tab content')}
                  onClick={handleDeleteTopLevelTabs}
                />,
              ]}
              editMode={editMode}
            >
              <DashboardComponent
                id={topLevelTabs?.id}
                parentId={DASHBOARD_ROOT_ID}
                depth={DASHBOARD_ROOT_DEPTH + 1}
                index={0}
                renderTabContent={false}
                renderHoverMenu={false}
                onChangeTab={handleChangeTab}
                responsiveLayout={responsiveDashboardEnabled && !editMode}
              />
            </WithPopoverMenu>
          )}
      </div>
    ),
    [
      editMode,
      handleChangeTab,
      handleDeleteTopLevelTabs,
      isReport,
      responsiveDashboardEnabled,
      topLevelTabs,
      uiConfig.hideTab,
      uiConfig.hideNav,
    ],
  );

  const dashboardContentMarginLeft = !editMode
    ? theme.sizeUnit * 4
    : theme.sizeUnit * 8;

  const renderChild = useCallback(
    (adjustedWidth: number) => {
      const filterBarShellWidth = dashboardFiltersOpen
        ? Math.max(adjustedWidth, OPEN_FILTER_BAR_SHELL_WIDTH)
        : CLOSED_FILTER_BAR_SHELL_WIDTH;
      const filterBarContentWidth = Math.max(
        CLOSED_FILTER_BAR_WIDTH,
        filterBarShellWidth - FILTER_BAR_SHELL_WIDTH_OFFSET,
      );
      if (filterBarShellWidth !== currentFilterBarWidth) {
        setCurrentFilterBarWidth(filterBarShellWidth);
      }
      return (
        <FiltersPanel
          width={filterBarShellWidth}
          hidden={isReport}
          data-test="dashboard-filters-panel"
        >
          <StickyPanel ref={containerRef} width={filterBarContentWidth}>
            <ErrorBoundary>
              <FilterBar
                orientation={FilterBarOrientation.Vertical}
                verticalConfig={{
                  filtersOpen: dashboardFiltersOpen,
                  toggleFiltersBar: toggleDashboardFiltersOpen,
                  width: filterBarContentWidth,
                  height: filterBarHeight,
                  offset: filterBarOffset,
                }}
              />
            </ErrorBoundary>
          </StickyPanel>
        </FiltersPanel>
      );
    },
    [
      dashboardFiltersOpen,
      toggleDashboardFiltersOpen,
      filterBarHeight,
      filterBarOffset,
      isReport,
    ],
  );

  const isVerticalFilterBarVisible =
    showFilterBar &&
    !responsiveDashboardMobile &&
    filterBarOrientation === FilterBarOrientation.Vertical;
  const headerFilterBarWidth = isVerticalFilterBarVisible
    ? currentFilterBarWidth
    : 0;

  return (
    <DashboardWrapper>
      {isVerticalFilterBarVisible && (
        <ResizableSidebar
          id={`dashboard:${dashboardId}:filter-shell`}
          enable={dashboardFiltersOpen}
          minWidth={OPEN_FILTER_BAR_SHELL_WIDTH}
          maxWidth={OPEN_FILTER_BAR_SHELL_MAX_WIDTH}
          initialWidth={OPEN_FILTER_BAR_SHELL_WIDTH}
        >
          {renderChild}
        </ResizableSidebar>
      )}
      <StyledHeader
        data-test="dashboard-header-wrapper"
        ref={headerRef}
        filterBarWidth={headerFilterBarWidth}
      >
        {headerContent}
        <Droppable
          data-test="top-level-tabs"
          className={cx(!topLevelTabs && editMode && 'empty-droptarget')}
          component={dashboardRoot}
          parentComponent={null}
          depth={DASHBOARD_ROOT_DEPTH}
          index={0}
          orientation="column"
          onDrop={handleDrop}
          editMode={editMode}
          // you cannot drop on/displace tabs if they already exist
          disableDragDrop={!!topLevelTabs}
          style={draggableStyle}
        >
          {renderDraggableContent}
        </Droppable>
      </StyledHeader>
      <StyledContent
        fullSizeChartId={fullSizeChartId}
        filterBarWidth={headerFilterBarWidth}
      >
        {!editMode &&
          !topLevelTabs &&
          dashboardLayout[DASHBOARD_GRID_ID]?.children?.length === 0 && (
            <EmptyState
              title={t('There are no charts added to this dashboard')}
              size="large"
              description={
                canEdit &&
                t(
                  'Go to the edit mode to configure the dashboard and add charts',
                )
              }
              buttonText={canEdit && t('Edit the dashboard')}
              buttonAction={() => {
                dispatch(setEditMode(true));
                dispatch(clearDashboardHistory());
              }}
              image="dashboard.svg"
            />
          )}
        <DashboardContentWrapper
          data-test="dashboard-content-wrapper"
          className={cx(
            'dashboard',
            editMode && 'dashboard--editing',
            responsiveDashboardEnabled && RESPONSIVE_DASHBOARD_CLASS,
            responsiveDashboardMobile && RESPONSIVE_DASHBOARD_MOBILE_CLASS,
          )}
        >
          <StyledDashboardContent
            className="dashboard-content"
            editMode={editMode}
            marginLeft={dashboardContentMarginLeft}
          >
            {showDashboard ? (
              missingInitialFilters.length > 0 ? (
                <div
                  css={css`
                    display: flex;
                    flex-direction: row;
                    align-items: center;
                    justify-content: center;
                    flex: 1;
                    & div {
                      width: 500px;
                    }
                  `}
                >
                  <BasicErrorAlert
                    title={t('Unable to load dashboard')}
                    body={t(
                      `The following filters have the 'Select first filter value by default'
                    option checked and could not be loaded, which is preventing the dashboard
                    from rendering: %s`,
                      missingInitialFilters.join(', '),
                    )}
                  />
                </div>
              ) : (
                <DashboardContainer topLevelTabs={topLevelTabs} />
              )
            ) : (
              <Loading />
            )}
            {editMode && <BuilderComponentPane topOffset={barTopOffset} />}
          </StyledDashboardContent>
        </DashboardContentWrapper>
      </StyledContent>
      {showFilterBar && responsiveDashboardMobile && !isReport && (
        <FilterBar orientation={filterBarOrientation} mobile />
      )}
      {dashboardIsSaving && (
        <Loading
          css={css`
            && {
              position: fixed;
            }
          `}
        />
      )}
    </DashboardWrapper>
  );
};

export default memo(DashboardBuilder);
