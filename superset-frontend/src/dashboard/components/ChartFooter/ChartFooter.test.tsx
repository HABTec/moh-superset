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
  createStore,
  fireEvent,
  render,
  screen,
} from 'spec/helpers/testing-library';
import reducerIndex from 'spec/helpers/reducerIndex';
import { RootState } from 'src/dashboard/types';
import ChartFooter, {
  ADJUSTED_DENOMINATOR_TAB_ID,
  ADJUSTED_DENOMINATOR_URL,
} from '.';

const layoutWithDenominatorTab = {
  ROOT_ID: { id: 'ROOT_ID', type: 'ROOT', children: ['TABS-1'], parents: [] },
  'TABS-1': {
    id: 'TABS-1',
    type: 'TABS',
    children: [ADJUSTED_DENOMINATOR_TAB_ID],
    parents: ['ROOT_ID'],
  },
  [ADJUSTED_DENOMINATOR_TAB_ID]: {
    id: ADJUSTED_DENOMINATOR_TAB_ID,
    type: 'TAB',
    children: [],
    parents: ['ROOT_ID', 'TABS-1'],
    meta: { text: 'Adjusted Denominator' },
  },
};

test('explains values above 100% and links to Adjusted Denominator', () => {
  render(<ChartFooter />, {
    useRedux: true,
    initialState: { dashboardInfo: { id: 12 } },
  });

  expect(screen.getByRole('note')).toHaveTextContent(
    'Some values exceed 100%. Population estimates (denominators) can be lower than the number of people served. See Adjusted Denominator',
  );
  expect(
    screen.getByRole('link', { name: 'See Adjusted Denominator' }),
  ).toHaveAttribute('href', ADJUSTED_DENOMINATOR_URL);
});

test('switches to the Adjusted Denominator tab in place on its own dashboard', () => {
  const store = createStore(
    {
      dashboardInfo: { id: 3 },
      dashboardLayout: {
        past: [],
        present: layoutWithDenominatorTab,
        future: [],
      },
    },
    reducerIndex,
  );
  render(<ChartFooter />, { store });

  const link = screen.getByRole('link', { name: 'See Adjusted Denominator' });
  const notPrevented = fireEvent.click(link);

  expect(notPrevented).toBe(false);
  const state = store.getState() as unknown as RootState;
  expect(state.dashboardState.directPathToChild).toEqual([
    'ROOT_ID',
    'TABS-1',
    ADJUSTED_DENOMINATOR_TAB_ID,
  ]);
});

test('follows the link normally from other dashboards', () => {
  render(<ChartFooter />, {
    useRedux: true,
    initialState: {
      dashboardInfo: { id: 12 },
      dashboardLayout: {
        past: [],
        present: layoutWithDenominatorTab,
        future: [],
      },
    },
  });

  const notPrevented = fireEvent.click(
    screen.getByRole('link', { name: 'See Adjusted Denominator' }),
  );

  expect(notPrevented).toBe(true);
});
