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
import { SupersetClient } from '@superset-ui/core';
import { screen, render, waitFor } from 'spec/helpers/testing-library';
import { AiInsightPanel } from './AiInsightPanel';

const mockPost = jest
  .spyOn(SupersetClient, 'post')
  .mockResolvedValue({} as never);

const mockQuery = {
  rowcount: 3,
  colnames: ['period', 'visits'],
  data: [
    { period: '2025-01', visits: 10 },
    { period: '2025-02', visits: 20 },
    { period: '2025-03', visits: 30 },
  ],
};

const initialState = {
  charts: {
    42: { queriesResponse: [mockQuery] },
  },
  sliceEntities: {
    slices: { 42: { slice_id: 42, slice_name: 'Visits', viz_type: 'line' } },
  },
};

const renderPanel = (props: { inView?: boolean } = {}) =>
  render(
    <AiInsightPanel
      chartId={42}
      dashboardId={8}
      sliceName="Visits"
      width={260}
      height={200}
      inView={props.inView ?? true}
    />,
    { useRedux: true, initialState },
  );

beforeEach(() => {
  mockPost.mockClear();
  (
    window as unknown as { featureFlags: Record<string, boolean> }
  ).featureFlags = { MOH_AI_INSIGHTS: true };
});

test('posts the summarized query data and renders the insight', async () => {
  mockPost.mockResolvedValue({
    json: {
      summary: 'Visits grew steadily over the reported period.',
      recommendation: 'Recommendation: prioritize additional outreach in February and March to sustain the upward trend.',
      bullets: [
        'Values increased from 10 to 30.',
        'February saw the largest single jump.',
        'Daily average sits at 20 visits.',
      ],
      provider: 'demo',
      generated_at: '2026-09-21T00:00:00Z',
    },
  } as never);

  renderPanel();

  expect(screen.getByTestId('ai-insight-panel')).toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getByText(/Visits grew steadily over the reported period/),
    ).toBeInTheDocument(),
  );
  expect(
    screen.getByText(/Values increased from 10 to 30/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/February saw the largest single jump/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Daily average sits at 20 visits/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/prioritize additional outreach in February and March/i),
  ).toBeInTheDocument();
  expect(mockPost).toHaveBeenCalledWith(
    expect.objectContaining({
      endpoint: '/ai-insights/chart/42/',
      jsonPayload: expect.objectContaining({
        chart_id: 42,
        dashboard_id: 8,
        viz_type: 'line',
        summary: expect.objectContaining({ rowCount: 3 }),
        sample_rows: expect.any(Array),
      }),
    }),
  );
});

test('shows a no-data message and skips the request when the feature flag is off', async () => {
  mockPost.mockResolvedValue({
    json: { summary: 'x', bullets: [], provider: 'demo', generated_at: '' },
  } as never);

  renderPanel();
  await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));

  mockPost.mockClear();
  (
    window as unknown as { featureFlags: Record<string, boolean> }
  ).featureFlags = { MOH_AI_INSIGHTS: false };

  renderPanel();
  await waitFor(() =>
    expect(screen.getByText(/No data available/)).toBeInTheDocument(),
  );
});

// Card-type charts (KPI big-number and handlebars templates) never get an
// AI insight generated — the sidebar is not rendered and no request fires.
test.each(['big_number', 'big_number_total', 'handlebars'])(
  'renders no sidebar and skips the insight request for %s charts',
  async vizType => {
    const cardState = {
      charts: {
        42: { queriesResponse: [mockQuery] },
      },
      sliceEntities: {
        slices: {
          42: { slice_id: 42, slice_name: 'KPI', viz_type: vizType },
        },
      },
    };

    render(
      <AiInsightPanel
        chartId={42}
        dashboardId={8}
        sliceName="KPI"
        width={260}
        height={200}
        inView
      />,
      { useRedux: true, initialState: cardState },
    );

    await waitFor(() =>
      expect(screen.queryByTestId('ai-insight-panel')).not.toBeInTheDocument(),
    );
    expect(mockPost).not.toHaveBeenCalled();
  },
);
test('renders the no-data state when the chart has no rows', async () => {
  const emptyState = {
    charts: {
      42: {
        queriesResponse: [
          { rowcount: 0, colnames: ['period', 'visits'], data: [] },
        ],
      },
    },
    sliceEntities: {
      slices: { 42: { slice_id: 42, slice_name: 'Visits', viz_type: 'line' } },
    },
  };

  render(
    <AiInsightPanel
      chartId={42}
      dashboardId={8}
      sliceName="Visits"
      width={260}
      height={200}
      inView
    />,
    { useRedux: true, initialState: emptyState },
  );

  await waitFor(() =>
    expect(screen.getByText(/No data available/)).toBeInTheDocument(),
  );
  expect(mockPost).not.toHaveBeenCalled();
});

const renderCollapsible = (
  props: {
    collapsed?: boolean;
    onToggleCollapsed?: () => void;
    onOpenPopup?: () => void;
    onClose?: () => void;
    showCollapseToggle?: boolean;
  } = {},
) =>
  render(
    <AiInsightPanel
      chartId={42}
      dashboardId={8}
      sliceName="Visits"
      width={32}
      height={200}
      inView
      collapsed={props.collapsed ?? false}
      onToggleCollapsed={props.onToggleCollapsed}
      onOpenPopup={props.onOpenPopup}
      onClose={props.onClose}
      showCollapseToggle={props.showCollapseToggle}
    />,
    { useRedux: true, initialState },
  );

test('when collapsed renders only a slim strip with an expand control', async () => {
  renderCollapsible({ collapsed: true });

  expect(screen.getByLabelText('Expand AI insight panel')).toBeInTheDocument();
  expect(
    screen.queryByLabelText('Collapse AI insight panel'),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByLabelText('Regenerate AI insight'),
  ).not.toBeInTheDocument();
  expect(screen.queryByText('AI Insight')).not.toBeInTheDocument();
});

test('clicking the expand control calls onToggleCollapsed', async () => {
  const onToggleCollapsed = jest.fn();
  renderCollapsible({ collapsed: true, onToggleCollapsed });

  screen.getByLabelText('Expand AI insight panel').click();
  expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
});

test('collapsed strip exposes a pop up control calling onOpenPopup', async () => {
  const onOpenPopup = jest.fn();
  renderCollapsible({ collapsed: true, onOpenPopup });

  expect(
    screen.getByLabelText('Pop out chart and AI insight'),
  ).toBeInTheDocument();
  screen.getByLabelText('Pop out chart and AI insight').click();
  expect(onOpenPopup).toHaveBeenCalledTimes(1);
});

test('when expanded shows a collapse control next to regenerate', async () => {
  const onToggleCollapsed = jest.fn();
  renderCollapsible({ collapsed: false, onToggleCollapsed });

  const collapseButton = screen.getByLabelText('Collapse AI insight panel');
  expect(collapseButton).toBeInTheDocument();
  collapseButton.click();
  expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
});

test('hides the collapse control when showCollapseToggle is false', async () => {
  renderCollapsible({ collapsed: false, showCollapseToggle: false });

  expect(
    screen.queryByLabelText('Collapse AI insight panel'),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText('Regenerate AI insight')).toBeInTheDocument();
});

test('shows a close control that calls onClose when provided', async () => {
  const onClose = jest.fn();
  renderCollapsible({ collapsed: false, onClose });

  const closeButton = screen.getByLabelText('Close AI insight popup');
  expect(closeButton).toBeInTheDocument();
  closeButton.click();
  expect(onClose).toHaveBeenCalledTimes(1);
});
