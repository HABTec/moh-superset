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
import { render, screen } from 'spec/helpers/testing-library';
import { Filter } from '@superset-ui/core';
import { FilterBarOrientation } from 'src/dashboard/types';
import { CrossFilterIndicator } from '../../selectors';
import { FiltersDropdownContent } from '.';

const buildFilter = (id: string, name: string): Filter =>
  ({
    id,
    name,
    filterType: 'filter_select',
    targets: [{ datasetId: 1, column: { name: 'country' } }],
    defaultDataMask: {},
    controlValues: {},
    cascadeParentIds: [],
    scope: { rootPath: ['ROOT_ID'], excluded: [] as string[] },
  }) as unknown as Filter;

const buildCrossFilter = (
  name: string,
  emitterId: number,
): CrossFilterIndicator =>
  ({ name, emitterId }) as unknown as CrossFilterIndicator;

const baseProps = {
  overflowedCrossFilters: [],
  filtersInScope: [buildFilter('filter-1', 'In Scope Filter')],
  renderer: (filter: any) => <div key={filter.id}>{filter.name}</div>,
  rendererCrossFilter: (
    crossFilter: CrossFilterIndicator,
    orientation: FilterBarOrientation.Vertical,
  ) => (
    <div key={`${crossFilter.name}${crossFilter.emitterId}`}>
      {crossFilter.name} ({orientation})
    </div>
  ),
};

test('renders in-scope filters in the dropdown content', () => {
  render(<FiltersDropdownContent {...baseProps} />);

  expect(screen.getByText('In Scope Filter')).toBeInTheDocument();
});

test('renders overflowed cross filters in the dropdown content', () => {
  render(
    <FiltersDropdownContent
      {...baseProps}
      overflowedCrossFilters={[
        buildCrossFilter('Region', 1),
        buildCrossFilter('Country', 2),
      ]}
    />,
  );

  expect(screen.getByText('Region (VERTICAL)')).toBeInTheDocument();
  expect(screen.getByText('Country (VERTICAL)')).toBeInTheDocument();
});

test('renders both cross filters and in-scope filters together', () => {
  render(
    <FiltersDropdownContent
      {...baseProps}
      overflowedCrossFilters={[buildCrossFilter('Region', 1)]}
    />,
  );

  expect(screen.getByText('Region (VERTICAL)')).toBeInTheDocument();
  expect(screen.getByText('In Scope Filter')).toBeInTheDocument();
});
