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
import {
  REDRAW_SETTLE_MS,
  registerThemePreview,
  runInLightMode,
} from './lightModeExport';

const lightTheme = { colorBgContainer: '#ffffff' } as SupersetTheme;

function setPageMode(mode: 'light' | 'dark' | null) {
  if (mode) document.documentElement.setAttribute('data-theme-mode', mode);
  else document.documentElement.removeAttribute('data-theme-mode');
}

function registerMockPreview() {
  const restore = jest.fn();
  const previewMode = jest.fn(() => restore);
  registerThemePreview({ previewMode, getTheme: () => lightTheme });
  return { previewMode, restore };
}

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  registerThemePreview(null);
  setPageMode(null);
  jest.useRealTimers();
});

test('runs the task straight away on a light page, without a preview', async () => {
  setPageMode('light');
  const { previewMode } = registerMockPreview();
  const task = jest.fn(() => 'done');

  await expect(runInLightMode(task)).resolves.toBe('done');

  expect(task).toHaveBeenCalledWith();
  expect(previewMode).not.toHaveBeenCalled();
});

test('runs the task as shown when no theme controller is registered', async () => {
  setPageMode('dark');
  const task = jest.fn(() => 'done');

  await expect(runInLightMode(task)).resolves.toBe('done');
  expect(task).toHaveBeenCalledWith();
});

test('on a dark page, shows light, waits for the redraw, runs the task, then restores', async () => {
  setPageMode('dark');
  const { previewMode, restore } = registerMockPreview();
  const task = jest.fn((theme?: SupersetTheme) => theme?.colorBgContainer);

  const result = runInLightMode(task);

  expect(previewMode).toHaveBeenCalledWith(ThemeMode.DEFAULT);
  // The charts haven't had time to redraw yet
  await jest.advanceTimersByTimeAsync(REDRAW_SETTLE_MS / 2);
  expect(task).not.toHaveBeenCalled();
  expect(restore).not.toHaveBeenCalled();

  await jest.advanceTimersByTimeAsync(REDRAW_SETTLE_MS);
  await expect(result).resolves.toBe('#ffffff');
  expect(task).toHaveBeenCalledWith(lightTheme);
  expect(restore).toHaveBeenCalledTimes(1);
});

test('restores the user theme when the task fails', async () => {
  setPageMode('dark');
  const { restore } = registerMockPreview();

  const result = runInLightMode(() => {
    throw new Error('capture failed');
  });
  const assertion = expect(result).rejects.toThrow('capture failed');
  await jest.advanceTimersByTimeAsync(REDRAW_SETTLE_MS * 2);
  await assertion;

  expect(restore).toHaveBeenCalledTimes(1);
});

test('finishes even when the browser pauses animation frames (hidden or covered window)', async () => {
  setPageMode('dark');
  const { restore } = registerMockPreview();
  const raf = jest
    .spyOn(window, 'requestAnimationFrame')
    .mockImplementation(() => 0);
  const task = jest.fn(() => 'done');

  const result = runInLightMode(task);
  await jest.advanceTimersByTimeAsync(REDRAW_SETTLE_MS);

  await expect(result).resolves.toBe('done');
  expect(restore).toHaveBeenCalledTimes(1);
  raf.mockRestore();
});
