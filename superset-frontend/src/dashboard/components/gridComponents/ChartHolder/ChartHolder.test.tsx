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

import { useState } from 'react';
import { combineReducers, createStore, applyMiddleware, compose } from 'redux';
import { Provider } from 'react-redux';
import thunk from 'redux-thunk';
import mockState from 'spec/fixtures/mockState';
import reducerIndex from 'spec/helpers/reducerIndex';
import { sliceId as chartId } from 'spec/fixtures/mockChartQueries';
import {
  screen,
  render,
  waitFor,
  fireEvent,
  userEvent,
} from 'spec/helpers/testing-library';
import { nativeFiltersInfo } from 'src/dashboard/fixtures/mockNativeFilters';
import newComponentFactory from 'src/dashboard/util/newComponentFactory';
import { initialState } from 'src/SqlLab/fixtures';
import { SET_DIRECT_PATH } from 'src/dashboard/actions/dashboardState';
import {
  CHART_TYPE,
  COLUMN_TYPE,
  ROW_TYPE,
} from '../../../util/componentTypes';
import ChartHolder, {
  AI_POPUP_MAX_WIDTH,
  AI_POPUP_WIDTH_FRACTION,
  CHART_MARGIN,
} from './ChartHolder';
import {
  AI_INSIGHT_PANEL_GUTTER,
  AI_INSIGHT_PANEL_WIDTH,
} from 'src/components/AiInsightPanel';
import { GRID_BASE_UNIT, GRID_GUTTER_SIZE } from '../../../util/constants';

const DEFAULT_HEADER_HEIGHT = 22;

// eslint-disable-next-line no-restricted-globals -- TODO: Migrate from describe blocks
describe('ChartHolder', () => {
  const originalRequestFullscreen = HTMLElement.prototype.requestFullscreen;
  // Tests that replace requestFullscreen get it back even when they fail
  afterEach(() => {
    HTMLElement.prototype.requestFullscreen = originalRequestFullscreen;
  });

  let scrollViewBase: any;

  const defaultProps = {
    component: {
      ...newComponentFactory(CHART_TYPE),
      id: 'CHART-ID',
      parents: ['ROOT_ID', 'TABS_ID', 'TAB_ID', 'ROW_ID'],
      meta: {
        uuid: `CHART-${chartId}`,
        chartId,
        width: 3,
        height: 10,
        chartName: 'Mock chart name',
      },
    },
    parentComponent: {
      ...newComponentFactory(ROW_TYPE),
      id: 'ROW_ID',
      children: ['COLUMN_ID'],
    },
    index: 0,
    depth: 0,
    id: 'CHART-ID',
    parentId: 'ROW_ID',
    availableColumnCount: 12,
    columnWidth: 300,
    onResizeStart: () => {},
    onResize: () => {},
    onResizeStop: () => {},
    handleComponentDrop: () => {},
    deleteComponent: () => {},
    updateComponents: () => {},
    editMode: false,
    isComponentVisible: true,
    dashboardId: 123,
    nativeFilters: nativeFiltersInfo.filters,
    fullSizeChartId: chartId,
    setFullSizeChartId: () => {},
  };

  beforeAll(() => {
    scrollViewBase = window.HTMLElement.prototype.scrollIntoView;
    window.HTMLElement.prototype.scrollIntoView = () => {};
  });

  afterAll(() => {
    window.HTMLElement.prototype.scrollIntoView = scrollViewBase;
  });

  const createMockStore = (customState: any = {}) =>
    createStore(
      combineReducers(reducerIndex),
      { ...mockState, ...(initialState as any), ...customState },
      compose(applyMiddleware(thunk)),
    );

  const renderWrapper = (store = createMockStore(), props: any = {}) =>
    render(<ChartHolder {...defaultProps} {...props} />, {
      useRouter: true,
      useDnd: true,
      useRedux: true,
      store,
    });

  test('should render empty state', async () => {
    renderWrapper();

    expect(
      screen.getByText('No results were returned for this query'),
    ).toBeVisible();
    expect(
      screen.queryByText(
        'Make sure that the controls are configured properly and the datasource contains data for the selected time range',
      ),
    ).not.toBeInTheDocument(); // description should display only in Explore view
    expect(screen.getByRole('img', { name: 'empty' })).toBeVisible();
  });

  test('should render anchor link when not editing', async () => {
    const store = createMockStore();
    const { rerender } = renderWrapper(store, { editMode: false });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    expect(
      screen
        .getByTestId('dashboard-component-chart-holder')
        .getElementsByClassName('anchor-link-container').length,
    ).toEqual(1);

    rerender(
      <Provider store={store}>
        <ChartHolder {...defaultProps} editMode isInView />
      </Provider>,
    );

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    expect(
      screen
        .getByTestId('dashboard-component-chart-holder')
        .getElementsByClassName('anchor-link-container').length,
    ).toEqual(0);
  });

  test('should highlight when path matches', async () => {
    const store = createMockStore({
      dashboardState: {
        ...mockState.dashboardState,
        directPathToChild: ['CHART-ID'],
      },
    });
    renderWrapper(store);

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    expect(screen.getByTestId('dashboard-component-chart-holder')).toHaveClass(
      'fade-out',
    );

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).not.toHaveClass('fade-in');

    store.dispatch({ type: SET_DIRECT_PATH, path: ['CHART-ID'] });

    await waitFor(() => {
      expect(
        screen.getByTestId('dashboard-component-chart-holder'),
      ).not.toHaveClass('fade-out');

      expect(
        screen.getByTestId('dashboard-component-chart-holder'),
      ).toHaveClass('fade-in');
    });

    await waitFor(
      () => {
        expect(
          screen.getByTestId('dashboard-component-chart-holder'),
        ).toHaveClass('fade-out');

        expect(
          screen.getByTestId('dashboard-component-chart-holder'),
        ).not.toHaveClass('fade-in');
      },
      { timeout: 5000 },
    );
  });

  test('should calculate the default widthMultiple', async () => {
    const widthMultiple = 5;
    renderWrapper(createMockStore(), {
      editMode: true,
      component: {
        ...defaultProps.component,
        meta: {
          ...defaultProps.component.meta,
          width: widthMultiple,
        },
      },
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const resizeContainer = screen
      .getByTestId('dragdroppable-object')
      .getElementsByClassName('resizable-container')[0];

    const { width: computedWidth } = getComputedStyle(resizeContainer);
    const expectedWidth =
      (defaultProps.columnWidth + GRID_GUTTER_SIZE) * widthMultiple -
      GRID_GUTTER_SIZE;

    expect(computedWidth).toEqual(`${expectedWidth}px`);
  });

  test('should set the resizable width to auto when parent component type is column', async () => {
    renderWrapper(createMockStore(), {
      editMode: true,
      parentComponent: {
        ...newComponentFactory(COLUMN_TYPE),
        id: 'ROW_ID',
        children: ['COLUMN_ID'],
      },
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const resizeContainer = screen
      .getByTestId('dragdroppable-object')
      .getElementsByClassName('resizable-container')[0];

    const { width: computedWidth } = getComputedStyle(resizeContainer);

    // the width is only adjustable if the parent component is row type
    expect(computedWidth).toEqual('auto');
  });

  test("should override the widthMultiple if there's a column in the parent chain whose width is less than the chart", async () => {
    const widthMultiple = 10;
    const parentColumnWidth = 6;
    renderWrapper(createMockStore(), {
      editMode: true,
      component: {
        ...defaultProps.component,
        meta: {
          ...defaultProps.component.meta,
          width: widthMultiple,
        },
      },
      // Return the first column in the chain
      getComponentById: () =>
        newComponentFactory(COLUMN_TYPE, { width: parentColumnWidth }),
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const resizeContainer = screen
      .getByTestId('dragdroppable-object')
      .getElementsByClassName('resizable-container')[0];

    const { width: computedWidth } = getComputedStyle(resizeContainer);
    const expectedWidth =
      (defaultProps.columnWidth + GRID_GUTTER_SIZE) * parentColumnWidth -
      GRID_GUTTER_SIZE;

    expect(computedWidth).toEqual(`${expectedWidth}px`);
  });

  test('should calculate the chartWidth', async () => {
    const widthMultiple = 7;
    const columnWidth = 250;
    renderWrapper(createMockStore(), {
      fullSizeChartId: null,
      component: {
        ...defaultProps.component,
        meta: {
          ...defaultProps.component.meta,
          width: widthMultiple,
        },
      },
      columnWidth,
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const container = screen.getByTestId('chart-container');

    const computedWidth = parseInt(container.getAttribute('width') || '0', 10);
    const expectedWidth = Math.floor(
      widthMultiple * columnWidth +
        (widthMultiple - 1) * GRID_GUTTER_SIZE -
        CHART_MARGIN -
        AI_INSIGHT_PANEL_WIDTH -
        AI_INSIGHT_PANEL_GUTTER,
    );

    expect(computedWidth).toEqual(expectedWidth);
  });

  test('should calculate the chartWidth on full screen mode', async () => {
    const widthMultiple = 7;
    const columnWidth = 250;
    renderWrapper(createMockStore(), {
      component: {
        ...defaultProps.component,
        meta: {
          ...defaultProps.component.meta,
          width: widthMultiple,
        },
      },
      columnWidth,
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const container = screen.getByTestId('chart-container');

    const computedWidth = parseInt(container.getAttribute('width') || '0', 10);
    const popupWidth = Math.min(
      window.innerWidth * AI_POPUP_WIDTH_FRACTION,
      AI_POPUP_MAX_WIDTH,
    );
    const expectedWidth =
      Math.floor(popupWidth) -
      CHART_MARGIN -
      AI_INSIGHT_PANEL_WIDTH -
      AI_INSIGHT_PANEL_GUTTER;

    expect(computedWidth).toEqual(expectedWidth);
  });

  test('should calculate the chartHeight', async () => {
    const heightMultiple = 12;
    renderWrapper(createMockStore(), {
      fullSizeChartId: null,
      component: {
        ...defaultProps.component,
        meta: {
          ...defaultProps.component.meta,
          height: heightMultiple,
        },
      },
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const container = screen.getByTestId('chart-container');

    const computedWidth = parseInt(container.getAttribute('height') || '0', 10);
    const expectedWidth = Math.floor(
      heightMultiple * GRID_BASE_UNIT - CHART_MARGIN - DEFAULT_HEADER_HEIGHT,
    );

    expect(computedWidth).toEqual(expectedWidth);
  });

  test('should calculate the chartHeight on full screen mode', async () => {
    const heightMultiple = 12;
    renderWrapper(createMockStore(), {
      component: {
        ...defaultProps.component,
        meta: {
          ...defaultProps.component.meta,
          height: heightMultiple,
        },
      },
    });

    expect(
      screen.getByTestId('dashboard-component-chart-holder'),
    ).toBeVisible();

    const container = screen.getByTestId('chart-container');

    const computedWidth = parseInt(container.getAttribute('height') || '0', 10);
    const expectedWidth =
      window.innerHeight - CHART_MARGIN - DEFAULT_HEADER_HEIGHT;

    expect(computedWidth).toEqual(expectedWidth);
  });

  test('should call deleteComponent when deleted', async () => {
    const deleteComponent = jest.fn();
    const store = createMockStore();
    const { rerender } = renderWrapper(store, {
      editMode: false,
      fullSizeChartId: null,
      deleteComponent,
    });

    expect(
      screen.queryByTestId('dashboard-delete-component-button'),
    ).not.toBeInTheDocument();

    rerender(
      <Provider store={store}>
        <ChartHolder
          {...defaultProps}
          deleteComponent={deleteComponent}
          fullSizeChartId={null}
          editMode
          isInView
        />
      </Provider>,
    );

    expect(
      screen.getByTestId('dashboard-delete-component-button'),
    ).toBeInTheDocument();

    userEvent.hover(screen.getByTestId('dashboard-component-chart-holder'));

    fireEvent.click(
      screen.getByTestId('dashboard-delete-component-button')
        .firstElementChild!,
    );
    expect(deleteComponent).toHaveBeenCalledTimes(1);
  });

  test('renders the chart and AI insight in a viewport-fixed popup when popped out', async () => {
    const setFullSizeChartId = jest.fn();
    renderWrapper(createMockStore(), {
      fullSizeChartId: chartId,
      setFullSizeChartId,
    });

    const popup = screen.getByTestId('full-size-popup');
    expect(popup).toBeInTheDocument();
    expect(popup.style.position).toBe('fixed');
    expect(screen.getByTestId('chart-container')).toBeInTheDocument();

    fireEvent.click(popup);
    expect(setFullSizeChartId).toHaveBeenCalledWith(null);
  });

  test('starts the AI insight panel expanded by default in responsive dashboards', async () => {
    renderWrapper(createMockStore(), {
      fullSizeChartId: null,
      responsiveDashboardEnabled: true,
    });

    expect(
      screen.getByLabelText('Collapse AI insight panel'),
    ).toBeInTheDocument();
  });

  const PoppingHarness = () => {
    const [fullSizeChartId, setFullSizeChartId] = useState<number | null>(null);
    return (
      <ChartHolder
        {...defaultProps}
        isInView
        fullSizeChartId={fullSizeChartId}
        setFullSizeChartId={setFullSizeChartId}
      />
    );
  };

  const renderHarness = () =>
    render(<PoppingHarness />, {
      useRouter: true,
      useDnd: true,
      useRedux: true,
      store: createMockStore(),
    });

  test('View fullscreen shows the popup in fullscreen with the chart inside', async () => {
    const requestFullscreen = jest.fn().mockResolvedValue(undefined);
    const original = HTMLElement.prototype.requestFullscreen;
    HTMLElement.prototype.requestFullscreen = requestFullscreen;
    renderHarness();

    userEvent.click(screen.getByRole('button', { name: 'More Options' }));
    userEvent.click(
      await screen.findByRole('menuitem', { name: /view fullscreen/i }),
    );

    const popup = await screen.findByTestId('full-size-popup');
    await waitFor(() => expect(requestFullscreen).toHaveBeenCalledTimes(1));
    const fullscreenTarget = requestFullscreen.mock.contexts[0] as HTMLElement;
    expect(popup.contains(fullscreenTarget)).toBe(true);
    expect(
      fullscreenTarget.querySelector('[data-test="chart-container"]'),
    ).not.toBeNull();
    HTMLElement.prototype.requestFullscreen = original;
  });

  test('the AI panel pop-out button opens the popup without fullscreen', async () => {
    const requestFullscreen = jest.fn().mockResolvedValue(undefined);
    const original = HTMLElement.prototype.requestFullscreen;
    HTMLElement.prototype.requestFullscreen = requestFullscreen;
    renderHarness();

    // The pop-out button shows once the AI panel is collapsed
    userEvent.click(
      screen.getByRole('button', { name: 'Collapse AI insight panel' }),
    );
    userEvent.click(
      await screen.findByRole('button', {
        name: 'Pop out chart and AI insight',
      }),
    );

    expect(await screen.findByTestId('full-size-popup')).toBeInTheDocument();
    expect(requestFullscreen).not.toHaveBeenCalled();
    HTMLElement.prototype.requestFullscreen = original;
  });

  test('the chart stays visible in the popup when fullscreen is refused', async () => {
    const original = HTMLElement.prototype.requestFullscreen;
    HTMLElement.prototype.requestFullscreen = jest
      .fn()
      .mockRejectedValue(new Error('denied'));
    renderHarness();

    userEvent.click(screen.getByRole('button', { name: 'More Options' }));
    userEvent.click(
      await screen.findByRole('menuitem', { name: /view fullscreen/i }),
    );

    const popup = await screen.findByTestId('full-size-popup');
    await waitFor(() =>
      expect(HTMLElement.prototype.requestFullscreen).toHaveBeenCalled(),
    );
    expect(popup.querySelector('[data-test="chart-container"]')).not.toBeNull();
    HTMLElement.prototype.requestFullscreen = original;
  });

  test('does not render the popup when not popped out', async () => {
    renderWrapper(createMockStore(), { fullSizeChartId: null });

    expect(screen.queryByTestId('full-size-popup')).not.toBeInTheDocument();
    expect(screen.getByTestId('chart-container')).toBeInTheDocument();
  });
});
