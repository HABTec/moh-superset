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
import domToPdf from 'dom-to-pdf';
import { addWarningToast } from 'src/components/MessageToasts/actions';
import { registerThemePreview } from 'src/theme/lightModeExport';
import downloadAsPdf from './downloadAsPdf';

jest.mock('dom-to-pdf', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('src/components/MessageToasts/actions', () => ({
  addWarningToast: jest.fn(),
}));

const mockDomToPdf = domToPdf as unknown as jest.Mock;

let target: HTMLElement;

beforeEach(() => {
  jest.clearAllMocks();
  mockDomToPdf.mockResolvedValue(undefined);
  target = document.createElement('div');
  target.className = 'pdf-target';
  document.body.appendChild(target);
});

afterEach(() => {
  target.remove();
  registerThemePreview(null);
  document.documentElement.removeAttribute('data-theme-mode');
  jest.useRealTimers();
});

test('creates the PDF straight away on a light page', async () => {
  await downloadAsPdf('.pdf-target', 'My Dashboard', true)({} as any);

  expect(mockDomToPdf).toHaveBeenCalledWith(
    target,
    expect.objectContaining({
      filename: expect.stringMatching(/^my-dashboard-.*\.pdf$/),
    }),
  );
});

test('on a dark page, creates the PDF in the light theme and then restores the user theme', async () => {
  jest.useFakeTimers();
  document.documentElement.setAttribute('data-theme-mode', 'dark');
  const restore = jest.fn();
  const previewMode = jest.fn(() => restore);
  registerThemePreview({
    previewMode,
    getTheme: () => ({ colorBgContainer: '#ffffff' }) as any,
  });
  let restoredBeforeCapture: boolean | null = null;
  mockDomToPdf.mockImplementation(async () => {
    restoredBeforeCapture = restore.mock.calls.length > 0;
  });

  const exportPromise = downloadAsPdf(
    '.pdf-target',
    'My Dashboard',
    true,
  )({} as any);
  await jest.runAllTimersAsync();
  await exportPromise;

  expect(previewMode).toHaveBeenCalledWith('default');
  expect(mockDomToPdf).toHaveBeenCalledTimes(1);
  expect(restoredBeforeCapture).toBe(false);
  expect(restore).toHaveBeenCalledTimes(1);
});

test('warns when the element is missing', async () => {
  await downloadAsPdf('.does-not-exist', 'My Dashboard', true)({} as any);

  expect(mockDomToPdf).not.toHaveBeenCalled();
  expect(addWarningToast).toHaveBeenCalledWith(
    'PDF download failed, please refresh and try again.',
  );
});
