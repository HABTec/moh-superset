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
import { useEffect } from 'react';
import { flushSync } from 'react-dom';
import { ThemeMode } from '@apache-superset/core/theme';
import { useOptionalThemeContext } from './ThemeProvider';

/**
 * Prints in light whatever the user's mode, so pages aren't printed black.
 * On "beforeprint" a dark page switches to the light theme without saving the
 * choice, and "afterprint" switches it back.
 */
export function usePrintInLightMode(): void {
  const previewMode = useOptionalThemeContext()?.previewMode;
  useEffect(() => {
    if (!previewMode) return undefined;
    let restore: (() => void) | null = null;
    const beforePrint = () => {
      const isDark =
        document.documentElement.getAttribute('data-theme-mode') === 'dark';
      if (!isDark || restore) return;
      // The browser takes its print snapshot as soon as this handler returns,
      // so the light theme has to be rendered now, not on React's next tick
      flushSync(() => {
        restore = previewMode(ThemeMode.DEFAULT);
      });
    };
    const afterPrint = () => {
      const undo = restore;
      restore = null;
      undo?.();
    };
    window.addEventListener('beforeprint', beforePrint);
    window.addEventListener('afterprint', afterPrint);
    return () => {
      window.removeEventListener('beforeprint', beforePrint);
      window.removeEventListener('afterprint', afterPrint);
      afterPrint();
    };
  }, [previewMode]);
}
