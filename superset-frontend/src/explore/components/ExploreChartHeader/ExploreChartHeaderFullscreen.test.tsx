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
import { VizType } from '@superset-ui/core';
import { render, screen, userEvent } from 'spec/helpers/testing-library';
import {
  ExploreFullscreenContext,
  ExploreFullscreenContextValue,
} from 'src/explore/components/ExploreFullscreen';
import ExploreChartHeader, { ExploreChartHeaderProps } from '.';

const createProps = (): ExploreChartHeaderProps =>
  ({
    chart: {
      id: 1,
      latestQueryFormData: {
        viz_type: VizType.Histogram,
        datasource: '49__table',
        slice_id: 318,
        url_params: {},
        granularity_sqla: 'time_start',
        time_range: 'No filter',
        all_columns_x: ['age'],
        adhoc_filters: [],
        row_limit: 10000,
        groupby: null,
        color_scheme: 'supersetColors',
        label_colors: {},
        link_length: '25',
        x_axis_label: 'age',
        y_axis_label: 'count',
        server_pagination: false,
      },
      chartStatus: 'rendered' as const,
    },
    actions: {
      updateChartTitle: jest.fn(),
      fetchFaveStar: jest.fn(),
      saveFaveStar: jest.fn(),
      redirectSQLLab: jest.fn(),
    },
    user: {
      userId: 1,
      username: 'admin',
      first_name: 'Ada',
      last_name: 'Lovelace',
      email: 'ada@example.com',
    },
    canOverwrite: true,
    isStarred: false,
    formData: {
      viz_type: VizType.Histogram,
      datasource: '49__table',
      granularity_sqla: 'time_start',
      all_columns_x: ['age'],
      row_limit: 10000,
    },
  }) as unknown as ExploreChartHeaderProps;

const contextValue = (
  overrides: Partial<ExploreFullscreenContextValue> = {},
): ExploreFullscreenContextValue => ({
  isAvailable: true,
  isFullscreen: false,
  isSupported: true,
  toggle: jest.fn(),
  exit: jest.fn(),
  ...overrides,
});

const renderHeader = (context: ExploreFullscreenContextValue | null) =>
  render(
    context ? (
      <ExploreFullscreenContext.Provider value={context}>
        <ExploreChartHeader {...createProps()} />
      </ExploreFullscreenContext.Provider>
    ) : (
      <ExploreChartHeader {...createProps()} />
    ),
    { useRedux: true },
  );

test('hides the fullscreen control when no fullscreen container exists', () => {
  renderHeader(null);
  expect(
    screen.queryByTestId('explore-fullscreen-toggle'),
  ).not.toBeInTheDocument();
});

test('hides the fullscreen control when the container is unavailable', () => {
  renderHeader(contextValue({ isAvailable: false }));
  expect(
    screen.queryByTestId('explore-fullscreen-toggle'),
  ).not.toBeInTheDocument();
});

test('shows an entry control that requests fullscreen', () => {
  const toggle = jest.fn();
  renderHeader(contextValue({ toggle }));

  const button = screen.getByTestId('explore-fullscreen-toggle');
  expect(button).toHaveAttribute('aria-label', 'View fullscreen');

  userEvent.click(button);
  expect(toggle).toHaveBeenCalledTimes(1);
});

test('shows an exit control while fullscreen', () => {
  const toggle = jest.fn();
  renderHeader(contextValue({ isFullscreen: true, toggle }));

  const button = screen.getByTestId('explore-fullscreen-toggle');
  expect(button).toHaveAttribute('aria-label', 'Exit fullscreen');

  userEvent.click(button);
  expect(toggle).toHaveBeenCalledTimes(1);
});
