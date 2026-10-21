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
import { RefObject, useCallback, useEffect, useRef, useState } from 'react';
import { t } from '@apache-superset/core/translation';

// Charts size themselves off the viewport, so they need a nudge once the
// browser has resized the element in or out of fullscreen.
const RESIZE_REDELAY_MS = 300;

export const queueChartResize = () => {
  window.setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, RESIZE_REDELAY_MS);
};

const isFullscreenApiAvailable = () =>
  typeof document !== 'undefined' &&
  typeof document.documentElement?.requestFullscreen === 'function';

export type UseFullscreenOptions = {
  /**
   * The element that fills the screen. It must be mounted and visible when
   * `enter` is called.
   */
  targetRef: RefObject<HTMLElement>;
  /**
   * Runs whenever fullscreen ends, whether it ended through this hook or
   * through the browser's own escape key.
   */
  onExit?: () => void;
  /**
   * Reports a message the user needs to see, such as a browser refusing to
   * enter fullscreen.
   */
  onError?: (message: string) => void;
};

export type UseFullscreenResult = {
  /** True for the native fullscreen state and for the CSS-only fallback. */
  isFullscreen: boolean;
  /**
   * Whether the browser exposes the Fullscreen API. When false the hook
   * falls back to a CSS-only fullscreen and the caller is expected to style
   * the element from `isFullscreen` alone.
   */
  isSupported: boolean;
  enter: () => void;
  exit: () => void;
  toggle: () => void;
};

/**
 * Drives the Fullscreen API for a single element.
 *
 * Native state is derived from `document.fullscreenElement` rather than from
 * this hook's own toggles, so it stays correct when the user leaves fullscreen
 * with the escape key or the browser UI. Browsers without the Fullscreen API
 * get an equivalent CSS-only fullscreen driven by local state.
 *
 * Dashboard charts keep their own Redux-backed implementation in
 * `SliceHeaderControls`; this is the standalone equivalent used by Explore.
 */
export const useFullscreen = ({
  targetRef,
  onExit,
  onError,
}: UseFullscreenOptions): UseFullscreenResult => {
  const [isNativeFullscreen, setIsNativeFullscreen] = useState(false);
  const [isFallbackFullscreen, setIsFallbackFullscreen] = useState(false);

  // Keep the latest callbacks without re-subscribing the document listener.
  const onExitRef = useRef(onExit);
  onExitRef.current = onExit;

  useEffect(() => {
    const handleFullscreenChange = () => {
      // Only track this hook's own element, so unrelated fullscreen elements
      // elsewhere on the page are left alone.
      setIsNativeFullscreen(document.fullscreenElement === targetRef.current);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [targetRef]);

  const isFullscreen = isNativeFullscreen || isFallbackFullscreen;

  const exitRef = useRef<() => void>(() => {});
  exitRef.current = () => {
    queueChartResize();
    onExitRef.current?.();
  };

  // A fullscreen session that ends for any reason needs the same cleanup.
  const wasFullscreenRef = useRef(false);
  useEffect(() => {
    if (wasFullscreenRef.current && !isFullscreen) {
      exitRef.current();
    }
    wasFullscreenRef.current = isFullscreen;
  }, [isFullscreen]);

  const enter = useCallback(() => {
    if (!isFullscreenApiAvailable()) {
      setIsFallbackFullscreen(true);
      return;
    }

    const target = targetRef.current;
    if (!target) {
      onError?.(t('Fullscreen is not supported in this browser.'));
      return;
    }

    target.requestFullscreen().catch((error: Error) => {
      onError?.(
        t(
          'Error enabling fullscreen: %s',
          error?.message || t('Unknown error'),
        ),
      );
    });
  }, [targetRef, onError]);

  const exit = useCallback(() => {
    if (typeof document.exitFullscreen !== 'function') {
      setIsFallbackFullscreen(false);
      return;
    }

    document.exitFullscreen().catch((error: Error) => {
      onError?.(
        t(
          'Error disabling fullscreen: %s',
          error?.message || t('Unknown error'),
        ),
      );
    });
  }, [onError]);

  const toggle = useCallback(() => {
    if (isFullscreen) {
      exit();
    } else {
      enter();
    }
  }, [isFullscreen, enter, exit]);

  return {
    isFullscreen,
    isSupported: isFullscreenApiAvailable(),
    enter,
    exit,
    toggle,
  };
};

export default useFullscreen;
