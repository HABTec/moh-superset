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
// Width (in px) of the expanded insight panel rendered to the right of each chart.
export const AI_INSIGHT_PANEL_WIDTH = 260;
// Width (in px) of the collapsed insight panel — a slim strip that keeps an
// expand control visible next to the chart.
export const AI_INSIGHT_PANEL_COLLAPSED_WIDTH = 32;
// Vertical gutter between the chart and the insight panel.
export const AI_INSIGHT_PANEL_GUTTER = 8;

export { AiInsightPanel } from './AiInsightPanel';
export type { ChartDataSummary } from './summarizeQueryData';
export { summarizeQueryData } from './summarizeQueryData';
