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
  (window as unknown as { featureFlags: Record<string, boolean> }).featureFlags =
    { MOH_AI_INSIGHTS: true };
});

test('posts the summarized query data and renders the insight', async () => {
  mockPost.mockResolvedValue({
    json: {
      insight: 'visits increased from 10 to 30 over the period',
      provider: 'demo',
      generated_at: '2026-09-21T00:00:00Z',
    },
  } as never);

  renderPanel();

  expect(screen.getByTestId('ai-insight-panel')).toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getByText(/visits increased from 10 to 30 over the period/),
    ).toBeInTheDocument(),
  );
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
    json: { insight: 'x', provider: 'demo', generated_at: '' },
  } as never);

  renderPanel();
  await waitFor(() =>
    expect(mockPost).toHaveBeenCalledTimes(1),
  );

  mockPost.mockClear();
  (window as unknown as { featureFlags: Record<string, boolean> }).featureFlags =
    { MOH_AI_INSIGHTS: false };

  renderPanel();
  await waitFor(() =>
    expect(screen.getByText(/No data available/)).toBeInTheDocument(),
  );
  expect(mockPost).not.toHaveBeenCalled();
});

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