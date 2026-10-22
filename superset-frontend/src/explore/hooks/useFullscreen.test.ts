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
import { act, renderHook } from '@testing-library/react';
import { useFullscreen } from './useFullscreen';

const flushResizeDelay = () =>
  act(() => {
    jest.advanceTimersByTime(300);
  });

const setFullscreenElement = (element: Element | null) => {
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    get: () => element,
  });
  act(() => {
    document.dispatchEvent(new Event('fullscreenchange'));
  });
};

const setup = (options = {}) => {
  const target = document.createElement('div');
  const requestFullscreen = jest.fn().mockResolvedValue(undefined);
  target.requestFullscreen = requestFullscreen;

  const onExit = jest.fn();
  const onError = jest.fn();

  const { result } = renderHook(() =>
    useFullscreen({
      targetRef: { current: target },
      onExit,
      onError,
      ...options,
    }),
  );

  return { result, target, requestFullscreen, onExit, onError };
};

const supportFullscreenApi = () => {
  // The hook feature-detects on the document element, as browsers expose the
  // method on Element.prototype. jsdom ships neither, so both are stubbed to
  // emulate a supporting browser.
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: jest.fn(),
  });
  Object.defineProperty(document, 'exitFullscreen', {
    configurable: true,
    value: jest.fn().mockResolvedValue(undefined),
  });
};

const removeFullscreenApi = () => {
  // @ts-expect-error deleting a property jsdom never defined
  delete document.documentElement.requestFullscreen;
  Object.defineProperty(document, 'exitFullscreen', {
    configurable: true,
    value: undefined,
  });
};

beforeEach(() => {
  jest.useFakeTimers();
  supportFullscreenApi();
  setFullscreenElement(null);
});

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

test('starts outside fullscreen', () => {
  const { result } = setup();
  expect(result.current.isFullscreen).toBe(false);
});

test('requests fullscreen on the target element', () => {
  const { result, requestFullscreen } = setup();

  act(() => result.current.enter());

  expect(requestFullscreen).toHaveBeenCalledTimes(1);
  expect(result.current.isFullscreen).toBe(false); // browser drives the change
});

test('becomes fullscreen once the browser reports it', () => {
  const { result, target } = setup();

  act(() => result.current.enter());
  setFullscreenElement(target);

  expect(result.current.isFullscreen).toBe(true);
});

test('exits fullscreen through the browser API', () => {
  const { result, target } = setup();

  act(() => result.current.enter());
  setFullscreenElement(target);
  act(() => result.current.exit());

  expect(document.exitFullscreen).toHaveBeenCalledTimes(1);
});

test('toggle enters then exits', () => {
  const { result, target, requestFullscreen } = setup();

  act(() => result.current.toggle());
  expect(requestFullscreen).toHaveBeenCalledTimes(1);

  setFullscreenElement(target);
  act(() => result.current.toggle());
  expect(document.exitFullscreen).toHaveBeenCalledTimes(1);
});

test('leaving fullscreen with the escape key is reflected and cleans up', () => {
  const { result, target, onExit } = setup();

  act(() => result.current.enter());
  setFullscreenElement(target);
  expect(result.current.isFullscreen).toBe(true);

  // The browser leaves fullscreen on its own, e.g. the user presses escape.
  setFullscreenElement(null);

  expect(result.current.isFullscreen).toBe(false);
  expect(onExit).toHaveBeenCalledTimes(1);
});

test('ignores fullscreen changes belonging to another element', () => {
  const { result } = setup();
  const other = document.createElement('div');

  setFullscreenElement(other);

  expect(result.current.isFullscreen).toBe(false);
});

test('nudges charts to resize after leaving fullscreen', () => {
  const { result, target } = setup();
  const dispatch = jest.spyOn(window, 'dispatchEvent');

  act(() => result.current.enter());
  setFullscreenElement(target);
  dispatch.mockClear();
  setFullscreenElement(null);

  expect(dispatch).not.toHaveBeenCalledWith(expect.any(Event));
  flushResizeDelay();
  expect(dispatch).toHaveBeenCalledWith(expect.any(Event));
});

test('surfaces a failure to enter fullscreen', async () => {
  const { result, target, onError } = setup();
  target.requestFullscreen = jest
    .fn()
    .mockRejectedValue(new Error('denied')) as never;

  await act(async () => {
    result.current.enter();
  });

  expect(onError).toHaveBeenCalledWith(
    expect.stringContaining('Error enabling fullscreen: denied'),
  );
});

test('surfaces a failure to exit fullscreen', async () => {
  const { result, target, onError } = setup();
  Object.defineProperty(document, 'exitFullscreen', {
    configurable: true,
    value: jest.fn().mockRejectedValue(new Error('nope')),
  });

  act(() => result.current.enter());
  setFullscreenElement(target);
  await act(async () => {
    result.current.exit();
  });

  expect(onError).toHaveBeenCalledWith(
    expect.stringContaining('Error disabling fullscreen: nope'),
  );
});

describe('browsers without the Fullscreen API', () => {
  beforeEach(() => {
    removeFullscreenApi();
  });

  test('reports the API as unsupported', () => {
    const { result } = setup();
    expect(result.current.isSupported).toBe(false);
  });

  test('falls back to a CSS-only fullscreen without calling the API', () => {
    const { result, requestFullscreen, onError } = setup();

    act(() => result.current.enter());

    expect(requestFullscreen).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(result.current.isFullscreen).toBe(true);
  });

  test('toggles back out and runs the exit cleanup', () => {
    const { result, onExit } = setup();

    act(() => result.current.toggle());
    expect(result.current.isFullscreen).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.isFullscreen).toBe(false);
    expect(onExit).toHaveBeenCalledTimes(1);
  });
});
