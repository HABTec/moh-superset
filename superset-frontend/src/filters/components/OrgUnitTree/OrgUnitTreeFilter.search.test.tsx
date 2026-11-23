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
import { NativeFilterType } from '@superset-ui/core';
import {
  render,
  screen,
  userEvent,
  waitFor,
  within,
} from 'spec/helpers/testing-library';
import OrgUnitTreeFilter from './OrgUnitTreeFilter';
import { resetAssignedOrgUnitCacheForTests } from './useAssignedOrgUnit';
import type { OrgUnit, OrgUnitTreeFilterProps } from './types';

const AMHARA: OrgUnit = {
  id: 'R1',
  displayName: 'Amhara ',
  level: 2,
  path: '/R1',
};
const OROMIA: OrgUnit = {
  id: 'R2',
  displayName: 'Oromia',
  level: 2,
  path: '/R2',
};
const NORTH_GONDAR: OrgUnit = {
  id: 'Z1',
  displayName: 'North Gondar',
  level: 3,
  path: '/R1/Z1',
};
const DABAT: OrgUnit = {
  id: 'W1',
  displayName: 'Dabat',
  level: 4,
  path: '/R1/Z1/W1',
  ancestors: [
    { id: 'R1', displayName: 'Amhara', level: 2 },
    { id: 'Z1', displayName: 'North Gondar', level: 3 },
  ],
};
// Same name as DABAT in a different zone: must stay distinguishable.
const DABAT_2: OrgUnit = {
  id: 'W2',
  displayName: 'Dabat',
  level: 4,
  path: '/R1/Z2/W2',
  ancestors: [
    { id: 'R1', displayName: 'Amhara', level: 2 },
    { id: 'Z2', displayName: 'Central Gondar', level: 3 },
  ],
};

type Responder = (url: string) => Promise<Response> | Response;

const json = (body: unknown, status = 200) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as Response;

let searchResponder: Responder;
let fetchMock: jest.Mock;

const searchCalls = () =>
  fetchMock.mock.calls
    .map(([url]) => String(url))
    .filter(url => url.includes('/organisationUnits/search'));

const queryOf = (url: string) => new URL(url, 'http://x').searchParams.get('q');

beforeEach(() => {
  resetAssignedOrgUnitCacheForTests();
  searchResponder = () => json({ organisationUnits: [] });
  fetchMock = jest.fn((input: RequestInfo) => {
    const url = String(input);
    if (url.includes('/me/organisationUnit')) {
      return Promise.resolve(json({ organisationUnit: null }));
    }
    if (url.includes('/organisationUnits/search')) {
      return Promise.resolve(searchResponder(url));
    }
    if (url.includes('/organisationUnits/R1')) {
      return Promise.resolve(json({ ...AMHARA, children: [NORTH_GONDAR] }));
    }
    if (url.includes('/organisationUnits?level=')) {
      return Promise.resolve(json({ organisationUnits: [AMHARA, OROMIA] }));
    }
    return Promise.resolve(json({}, 404));
  });
  global.fetch = fetchMock as unknown as typeof fetch;
});

function setup(
  options: {
    formData?: OrgUnitTreeFilterProps['formData'];
    initialState?: object;
  } = {},
) {
  const setDataMask = jest.fn();
  render(
    <OrgUnitTreeFilter
      formData={options.formData ?? {}}
      filterState={{ value: null }}
      setDataMask={setDataMask}
      width={300}
      height={400}
    />,
    {
      useRedux: true,
      initialState: options.initialState ?? {
        nativeFilters: { filters: {} },
        dataMask: {},
      },
    },
  );
  return { setDataMask };
}

const searchBox = () =>
  screen.getByRole('searchbox', { name: /search org units/i });

async function typeQuery(text: string, delay?: number) {
  await userEvent.type(searchBox(), text, delay ? { delay } : undefined);
}

/** The most recent filter payload sent to Superset. */
const lastMask = (setDataMask: jest.Mock) =>
  setDataMask.mock.calls[setDataMask.mock.calls.length - 1][0];

function treeNode(title: string): HTMLElement {
  const node = screen
    .getByText(title, { selector: '.ant-tree-title' })
    .closest('.ant-tree-treenode');
  if (!node) throw new Error(`No tree node for ${title}`);
  return node as HTMLElement;
}

function treeCheckbox(title: string): HTMLElement {
  const node = treeNode(title);
  const box = node?.querySelector('.ant-tree-checkbox');
  if (!box) throw new Error(`No tree checkbox for ${title}`);
  return box as HTMLElement;
}

function resultCheckbox(index: number): HTMLElement {
  return within(screen.getAllByRole('listitem')[index]).getByRole('checkbox');
}

async function waitForTree() {
  await screen.findByText('Oromia');
}

test('a single character does not search and keeps the tree visible', async () => {
  setup();
  await waitForTree();

  await typeQuery('d');
  await new Promise(resolve => setTimeout(resolve, 400));

  expect(searchCalls()).toHaveLength(0);
  expect(
    screen.queryByRole('list', { name: /search results/i }),
  ).not.toBeInTheDocument();
  expect(screen.getByText('Oromia')).toBeVisible();
});

test('whitespace-only input is not treated as a search', async () => {
  setup();
  await waitForTree();

  await typeQuery('     ');
  await new Promise(resolve => setTimeout(resolve, 400));

  expect(searchCalls()).toHaveLength(0);
  expect(screen.getByText('Select all')).toBeInTheDocument();
});

test('fast typing is debounced into one request for the final query', async () => {
  setup();
  await waitForTree();

  // Human-speed typing (50 ms per key) stays within one debounce window.
  await typeQuery('dabat', 50);
  await new Promise(resolve => setTimeout(resolve, 400));

  await waitFor(() => expect(searchCalls()).toHaveLength(1));
  expect(queryOf(searchCalls()[0])).toBe('dabat');
});

test('query text is URL-encoded, including Amharic and reserved characters', async () => {
  setup();
  await waitForTree();

  await typeQuery('ደባ & #1%');

  await waitFor(() => expect(searchCalls()).toHaveLength(1));
  const url = searchCalls()[0];
  expect(url).not.toContain(' ');
  expect(url).not.toContain('#');
  expect(queryOf(url)).toBe('ደባ & #1%');
});

test('leading and trailing spaces are trimmed from the query', async () => {
  setup();
  await waitForTree();

  await typeQuery('  dab  ');

  await waitFor(() => expect(searchCalls()).toHaveLength(1));
  expect(queryOf(searchCalls()[0])).toBe('dab');
});

test('selected CBMP types are forwarded to the search', async () => {
  setup({
    initialState: {
      nativeFilters: {
        filters: {
          cbmp: {
            id: 'cbmp',
            name: 'CBMP',
            type: NativeFilterType.NativeFilter,
            filterType: 'filter_select',
            targets: [{ column: { name: 'cbmp_type' } }],
          },
        },
      },
      dataMask: {
        cbmp: {
          id: 'cbmp',
          extraFormData: {
            filters: [{ col: 'cbmp_type', op: 'IN', val: ['Hospital'] }],
          },
        },
      },
    },
  });
  await waitForTree();

  await typeQuery('dab');

  await waitFor(() => expect(searchCalls()).toHaveLength(1));
  const params = new URL(searchCalls()[0], 'http://x').searchParams;
  expect(params.getAll('cbmp_type')).toEqual(['Hospital']);
  expect(params.get('q')).toBe('dab');
});

test('results show level and ancestor trail so same-named units differ', async () => {
  searchResponder = () => json({ organisationUnits: [DABAT, DABAT_2] });
  setup();
  await waitForTree();

  await typeQuery('dabat');

  expect(
    await screen.findByText('Woreda · Amhara › North Gondar'),
  ).toBeInTheDocument();
  expect(
    screen.getByText('Woreda · Amhara › Central Gondar'),
  ).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(2);
  expect(screen.getByText('Select all matches')).toBeInTheDocument();
});

test('no matches shows an explicit empty message', async () => {
  setup();
  await waitForTree();

  await typeQuery('zzz');

  expect(
    await screen.findByText('No org units match "zzz"'),
  ).toBeInTheDocument();
});

test('a failed search shows the error instead of an empty list', async () => {
  searchResponder = () => json({}, 500);
  setup();
  await waitForTree();

  await typeQuery('dab');

  expect(await screen.findByText('HTTP 500')).toBeInTheDocument();
  expect(screen.queryByText(/No org units match/)).not.toBeInTheDocument();
});

test('a network failure during search is reported', async () => {
  searchResponder = () => Promise.reject(new Error('Network down'));
  setup();
  await waitForTree();

  await typeQuery('dab');

  expect(await screen.findByText('Network down')).toBeInTheDocument();
});

test('a slow earlier response never overwrites newer results', async () => {
  const pending: Array<(r: Response) => void> = [];
  searchResponder = () =>
    new Promise<Response>(resolve => {
      pending.push(resolve);
    });
  setup();
  await waitForTree();

  await typeQuery('no');
  await waitFor(() => expect(searchCalls()).toHaveLength(1));
  await typeQuery('r');
  await waitFor(() => expect(searchCalls()).toHaveLength(2));

  pending[1](json({ organisationUnits: [NORTH_GONDAR] }));
  expect(await screen.findByText('North Gondar')).toBeInTheDocument();
  pending[0](json({ organisationUnits: [DABAT] }));
  await new Promise(resolve => setTimeout(resolve, 50));

  expect(screen.getByText('North Gondar')).toBeInTheDocument();
  expect(screen.queryByText('Dabat')).not.toBeInTheDocument();
}, 10000);

test('checking a result selects it with the matching dimension and shows a tag', async () => {
  searchResponder = () => json({ organisationUnits: [DABAT] });
  const { setDataMask } = setup();
  await waitForTree();
  await typeQuery('dabat');
  await screen.findByRole('listitem');

  await userEvent.click(resultCheckbox(0));

  expect(lastMask(setDataMask)).toEqual({
    filterState: { value: ['Dabat'] },
    extraFormData: { filters: [{ col: 'woreda', op: 'IN', val: ['Dabat'] }] },
  });
  expect(resultCheckbox(0)).toBeChecked();
  expect(
    within(screen.getByLabelText('Selected org units')).getByText('Dabat'),
  ).toBeInTheDocument();
});

test('unchecking a result removes it from the filter', async () => {
  searchResponder = () => json({ organisationUnits: [DABAT] });
  const { setDataMask } = setup();
  await waitForTree();
  await typeQuery('dabat');
  await screen.findByRole('listitem');

  await userEvent.click(resultCheckbox(0));
  await userEvent.click(resultCheckbox(0));

  expect(lastMask(setDataMask)).toEqual({
    filterState: { value: null },
    extraFormData: { filters: [] },
  });
  expect(screen.queryByLabelText('Selected org units')).not.toBeInTheDocument();
});

test('a search pick survives clearing the search and checking a tree node', async () => {
  searchResponder = () => json({ organisationUnits: [DABAT] });
  const { setDataMask } = setup();
  await waitForTree();
  await typeQuery('dabat');
  await screen.findByRole('listitem');
  await userEvent.click(resultCheckbox(0));

  await userEvent.clear(searchBox());
  await userEvent.click(treeCheckbox('Oromia'));

  expect(lastMask(setDataMask)).toEqual({
    filterState: { value: ['Dabat', 'Oromia'] },
    extraFormData: {
      filters: [
        { col: 'woreda', op: 'IN', val: ['Dabat'] },
        { col: 'region', op: 'IN', val: ['Oromia'] },
      ],
    },
  });
});

test('unchecking a tree node keeps every other selection', async () => {
  const { setDataMask } = setup();
  await waitForTree();

  await userEvent.click(treeCheckbox('Amhara'));
  await userEvent.click(treeCheckbox('Oromia'));
  await userEvent.click(treeCheckbox('Amhara'));

  expect(lastMask(setDataMask)).toEqual({
    filterState: { value: ['Oromia'] },
    extraFormData: { filters: [{ col: 'region', op: 'IN', val: ['Oromia'] }] },
  });
});

test('tree node names are trimmed before being sent as filter values', async () => {
  const { setDataMask } = setup();
  await waitForTree();

  await userEvent.click(treeCheckbox('Amhara'));

  expect(lastMask(setDataMask).filterState.value).toEqual(['Amhara']);
});

test('a result checked in search shows as checked in the tree once loaded', async () => {
  searchResponder = () => json({ organisationUnits: [NORTH_GONDAR] });
  setup();
  await waitForTree();
  await typeQuery('north');
  await screen.findByRole('listitem');
  await userEvent.click(resultCheckbox(0));
  await userEvent.clear(searchBox());

  await userEvent.click(
    treeNode('Amhara').querySelector('.ant-tree-switcher')!,
  );
  await screen.findByText('North Gondar', { selector: '.ant-tree-title' });

  expect(treeCheckbox('North Gondar')).toHaveClass('ant-tree-checkbox-checked');
});

test('removing a tag deselects just that unit', async () => {
  const { setDataMask } = setup();
  await waitForTree();
  await userEvent.click(treeCheckbox('Amhara'));
  await userEvent.click(treeCheckbox('Oromia'));

  const tags = screen.getByLabelText('Selected org units');
  const amharaTag = within(tags).getByText('Amhara').closest('.ant-tag');
  await userEvent.click(within(amharaTag as HTMLElement).getByRole('img'));

  expect(lastMask(setDataMask).filterState.value).toEqual(['Oromia']);
  expect(within(tags).queryByText('Amhara')).not.toBeInTheDocument();
  expect(treeCheckbox('Amhara')).not.toHaveClass('ant-tree-checkbox-checked');
});

test('select all matches adds every match without duplicating existing picks', async () => {
  searchResponder = () => json({ organisationUnits: [DABAT, DABAT_2] });
  const { setDataMask } = setup();
  await waitForTree();
  await userEvent.click(treeCheckbox('Oromia'));
  await typeQuery('dabat');
  await screen.findAllByRole('listitem');
  await userEvent.click(resultCheckbox(0));

  await userEvent.click(screen.getByText('Select all matches'));

  const ids = lastMask(setDataMask).filterState.value;
  expect(ids).toEqual(['Oromia', 'Dabat', 'Dabat']);
  expect(screen.getByText('Select all matches')).toBeDisabled();
});

test('select all matches is disabled when there are no matches', async () => {
  setup();
  await waitForTree();

  await typeQuery('zzz');
  await screen.findByText('No org units match "zzz"');

  expect(screen.getByText('Select all matches')).toBeDisabled();
});

test('outside search, select all picks the roots and clear empties everything', async () => {
  const { setDataMask } = setup();
  await waitForTree();

  await userEvent.click(screen.getByText('Select all'));
  expect(lastMask(setDataMask).filterState.value).toEqual(['Amhara', 'Oromia']);
  expect(screen.getByText('Select all')).toBeDisabled();

  await userEvent.click(screen.getByText('Clear'));
  expect(lastMask(setDataMask)).toEqual({
    filterState: { value: null },
    extraFormData: { filters: [] },
  });
  expect(screen.getByText('Clear')).toBeDisabled();
});

test('clearing the search box restores the tree with its expanded state', async () => {
  searchResponder = () => json({ organisationUnits: [DABAT] });
  setup();
  await waitForTree();
  await userEvent.click(
    treeNode('Amhara').querySelector('.ant-tree-switcher')!,
  );
  await screen.findByText('North Gondar');

  await typeQuery('dabat');
  await screen.findByRole('listitem');
  await userEvent.clear(searchBox());

  expect(
    screen.queryByRole('list', { name: /search results/i }),
  ).not.toBeInTheDocument();
  expect(screen.getByText('North Gondar')).toBeVisible();
  expect(screen.getByText('Select all')).toBeInTheDocument();
});

test('stale results are not shown when a new search starts', async () => {
  let resolveSecond: (r: Response) => void = () => {};
  let call = 0;
  searchResponder = () => {
    call += 1;
    if (call === 1) return json({ organisationUnits: [DABAT] });
    return new Promise<Response>(resolve => {
      resolveSecond = resolve;
    });
  };
  setup();
  await waitForTree();
  await typeQuery('dabat');
  await screen.findByRole('listitem');

  await userEvent.clear(searchBox());
  await typeQuery('north');
  await waitFor(() => expect(searchCalls()).toHaveLength(2));
  resolveSecond(json({ organisationUnits: [NORTH_GONDAR] }));

  expect(await screen.findByText('North Gondar')).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(1);
});

test('the search box stays in the pinned header above the list', async () => {
  searchResponder = () =>
    json({
      organisationUnits: Array.from({ length: 40 }, (_, i) => ({
        ...DABAT,
        id: `W${i}`,
        displayName: `Woreda ${i}`,
      })),
    });
  setup();
  await waitForTree();
  await typeQuery('woreda');
  await screen.findAllByRole('listitem');

  let el: HTMLElement | null = searchBox();
  while (el && getComputedStyle(el).position !== 'sticky') {
    el = el.parentElement;
  }
  expect(el).not.toBeNull();
  // The toolbar is pinned together with the search box.
  expect(within(el!).getByText('Select all matches')).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(40);
});

test('a failed root load shows the error and disables select all', async () => {
  fetchMock.mockImplementation((input: RequestInfo) => {
    const url = String(input);
    if (url.includes('/me/organisationUnit')) {
      return Promise.resolve(json({ organisationUnit: null }));
    }
    return Promise.resolve(json({}, 503));
  });
  setup();

  expect(await screen.findByText('HTTP 503')).toBeInTheDocument();
  expect(screen.getByText('Select all')).toBeDisabled();
});
