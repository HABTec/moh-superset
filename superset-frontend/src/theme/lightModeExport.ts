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
import { ThemeMode, type SupersetTheme } from '@apache-superset/core/theme';

/**
 * What runInLightMode needs from the app's theme controller.
 */
export interface ThemePreviewApi {
  /** Shows a mode without saving it; returns the function that undoes it */
  previewMode: (mode: ThemeMode) => () => void;
  /** The theme tokens on screen */
  getTheme: () => SupersetTheme;
}

let previewApi: ThemePreviewApi | null = null;

// ECharts animates a chart to its new colours (animationDurationUpdate,
// 300 ms by default); waiting this long keeps a half-redrawn chart out of
// the export.
export const REDRAW_SETTLE_MS = 400;

/**
 * Connects runInLightMode to the app's theme controller. Pages without one
 * (embedded dashboards, tests) leave it unset and export as shown.
 */
export function registerThemePreview(api: ThemePreviewApi | null): void {
  previewApi = api;
}

const isPageDark = (): boolean =>
  typeof document !== 'undefined' &&
  document.documentElement.getAttribute('data-theme-mode') === 'dark';

const wait = (ms: number): Promise<void> =>
  new Promise(resolve => setTimeout(resolve, ms));

/**
 * Runs an export (chart image, PDF) in the light theme, whatever the user's
 * mode, because exports go into printed and shared reports. On a dark page
 * the light theme is shown without saving it, the task runs once the charts
 * have redrawn, and the user's theme comes back afterwards, even if the task
 * fails. On a light page the task simply runs.
 * @param task - The export; receives the light theme's tokens on a dark page
 * @returns What the task returns
 */
export async function runInLightMode<T>(
  task: (lightTheme?: SupersetTheme) => Promise<T> | T,
): Promise<T> {
  const api = previewApi;
  if (!api || !isPageDark()) return task();

  const restore = api.previewMode(ThemeMode.DEFAULT);
  try {
    // React renders the light theme within a few milliseconds and ECharts
    // then animates to its new colours. A timer rather than animation frames,
    // which browsers pause in windows that are hidden or covered and would
    // leave the page stuck in light.
    await wait(REDRAW_SETTLE_MS);
    return await task(api.getTheme());
  } finally {
    restore();
  }
}
