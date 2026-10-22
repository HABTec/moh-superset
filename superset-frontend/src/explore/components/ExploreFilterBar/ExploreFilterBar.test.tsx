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
import { Divider, Filter } from '@superset-ui/core';
import { render, screen } from 'spec/helpers/testing-library';
import ExploreFilterBar from 'src/explore/components/ExploreFilterBar';

// The real filter bar needs a large slice of dashboard state. This suite only
// covers whether the bar is shown at all, so the controls are stubbed.
jest.mock('src/dashboard/components/nativeFilters/FilterBar', () => ({
  __esModule: true,
  default: ({ orientation }: { orientation: string }) => (
    <div data-test="stub-filter-bar">{orientation}</div>
  ),
}));

const NATIVE_FILTER = {
  id: 'NATIVE_FILTER-abc',
  name: 'Region',
  filterType: 'NATIVE_FILTER',
  targets: [{ datasetId: 1, column: { name: 'region' } }],
} as unknown as Filter;

const CROSS_FILTER_DIVIDER = { id: 'DIVIDER-1', type: 'DIVIDER' } as Divider;

const renderBar = (nativeFilterConfiguration?: (Filter | Divider)[]) =>
  render(<ExploreFilterBar />, {
    useRedux: true,
    initialState: {
      explore: { nativeFilterConfiguration },
    },
  });

test('renders nothing when Explore was not opened from a dashboard', () => {
  renderBar(undefined);
  expect(screen.queryByTestId('explore-filter-bar')).not.toBeInTheDocument();
});

test('renders nothing when the dashboard has no filters', () => {
  renderBar([]);
  expect(screen.queryByTestId('explore-filter-bar')).not.toBeInTheDocument();
});

test('renders nothing when only dividers were configured', () => {
  renderBar([CROSS_FILTER_DIVIDER]);
  expect(screen.queryByTestId('explore-filter-bar')).not.toBeInTheDocument();
});

test('renders the bar for inherited native filters', () => {
  renderBar([CROSS_FILTER_DIVIDER, NATIVE_FILTER]);
  expect(screen.getByTestId('explore-filter-bar')).toBeInTheDocument();
  expect(screen.getByTestId('stub-filter-bar')).toHaveTextContent('HORIZONTAL');
});
