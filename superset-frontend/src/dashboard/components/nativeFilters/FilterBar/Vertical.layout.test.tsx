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
import { stateWithoutNativeFilters } from 'spec/fixtures/mockStore';
import VerticalFilterBar from './Vertical';

jest.mock('./Header', () => () => <div data-test="bar-header" />);
jest.mock('./CrossFilters/Vertical', () => () => null);

const HEIGHT = 'calc(100vh - 96px)';

function renderBar(filtersOpen: boolean) {
  render(
    <VerticalFilterBar
      actions={<div data-test="bar-actions">Apply filters</div>}
      canEdit={false}
      dataMaskSelected={{}}
      filterValues={[]}
      chartCustomizationValues={[]}
      isInitialized
      onSelectionChange={jest.fn()}
      onPendingCustomizationDataMaskChange={jest.fn()}
      filtersOpen={filtersOpen}
      height={HEIGHT}
      offset={0}
      toggleFiltersBar={jest.fn()}
      width={280}
    />,
    { useRedux: true, initialState: stateWithoutNativeFilters },
  );
}

/** Nearest ancestor (inclusive) whose computed style matches. */
function closestWithStyle(
  start: HTMLElement,
  matches: (style: CSSStyleDeclaration) => boolean,
): HTMLElement | null {
  let el: HTMLElement | null = start;
  while (el && !matches(getComputedStyle(el))) {
    el = el.parentElement;
  }
  return el;
}

test('open bar is bounded to the viewport height instead of growing past it', () => {
  renderBar(true);

  const bar = screen.getByTestId('bar-header').parentElement as HTMLElement;
  expect(bar).toHaveClass('open');
  const style = getComputedStyle(bar);
  expect(style.maxHeight).toBe(HEIGHT);
  expect(style.height).toBe(HEIGHT);
  expect(style.overflow).toBe('hidden');

  const wrapper = bar.parentElement as HTMLElement;
  expect(getComputedStyle(wrapper).maxHeight).toBe(HEIGHT);
});

test('the filter list scrolls inside the bar while header and actions stay put', () => {
  renderBar(true);

  const list = screen.getByText('No global filters are currently added');
  const scroller = closestWithStyle(list, s => s.overflowY === 'auto');
  expect(scroller).not.toBeNull();
  expect(scroller).toHaveStyle({
    minHeight: '0',
    overscrollBehavior: 'contain',
  });

  // Header and Apply/Clear are siblings of the scroller, not inside it.
  expect(scroller).not.toContainElement(screen.getByTestId('bar-header'));
  expect(scroller).not.toContainElement(screen.getByTestId('bar-actions'));
  expect(scroller?.parentElement).toContainElement(
    screen.getByTestId('bar-actions'),
  );
});

test('collapsed bar keeps the narrow rail and hides the panel', () => {
  renderBar(false);

  const bar = screen.getByTestId('bar-header').parentElement as HTMLElement;
  expect(bar).not.toHaveClass('open');
  expect(getComputedStyle(bar).display).toBe('none');
});
