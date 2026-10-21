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

import { getExtensionsRegistry } from '@superset-ui/core';
import { Provider as ReduxProvider } from 'react-redux';
import { QueryParamProvider } from 'use-query-params';
import { ReactRouter5Adapter } from 'use-query-params/adapters/react-router-5';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { DynamicPluginProvider } from 'src/components';
import { EmbeddedUiConfigProvider } from 'src/components/UiConfigContext';
import { SupersetThemeProvider } from 'src/theme/ThemeProvider';
import type { ThemeMode } from '@apache-superset/core/theme';
import { ThemeController } from 'src/theme/ThemeController';
import { registerThemePreview } from 'src/theme/lightModeExport';
import getBootstrapData from 'src/utils/getBootstrapData';
import setupColors from 'src/setup/setupColors';
import { store } from './store';
import '../preamble';
import querystring from 'query-string';

const themeController = new ThemeController({
  initialMode: getBootstrapData().common?.theme?.defaultMode,
});

// Custom colour schemes can define dark colours ("colorsDark"); register the
// set that matches the theme on screen (including a temporary light preview
// for printing), and switch when light/dark changes.
let colorSchemesAreDark: boolean | null = null;
const registerColorSchemesForMode = () => {
  const isDark = themeController.getCurrentModeResolved() === 'dark';
  if (isDark === colorSchemesAreDark) return;
  colorSchemesAreDark = isDark;
  const { common } = getBootstrapData();
  setupColors(
    common.extra_categorical_color_schemes,
    common.extra_sequential_color_schemes,
    isDark,
  );
};
registerColorSchemesForMode();
themeController.onChange(registerColorSchemesForMode);

declare global {
  interface Window {
    /** Lets MoH page templates (chart image export) show light output */
    supersetTheme?: { previewMode: (mode: ThemeMode) => () => void };
  }
}
window.supersetTheme = {
  previewMode: mode => themeController.previewMode(mode),
};

// Image and PDF downloads switch to light through this (runInLightMode)
registerThemePreview({
  previewMode: mode => themeController.previewMode(mode),
  getTheme: () => themeController.getTheme().theme,
});

const extensionsRegistry = getExtensionsRegistry();

export const RootContextProviders: React.FC<{ children?: React.ReactNode }> = ({
  children,
}) => {
  const RootContextProviderExtension = extensionsRegistry.get(
    'root.context.provider',
  );

  return (
    <SupersetThemeProvider themeController={themeController}>
      <ReduxProvider store={store}>
        {/* @ts-expect-error react-dnd types not updated for React 18 */}
        <DndProvider backend={HTML5Backend}>
          <EmbeddedUiConfigProvider>
            <DynamicPluginProvider>
              <QueryParamProvider
                adapter={ReactRouter5Adapter}
                options={{
                  searchStringToObject: querystring.parse,
                  objectToSearchString: (object: Record<string, any>) =>
                    querystring.stringify(object, { encode: false }),
                }}
              >
                {RootContextProviderExtension ? (
                  <RootContextProviderExtension>
                    {children}
                  </RootContextProviderExtension>
                ) : (
                  children
                )}
              </QueryParamProvider>
            </DynamicPluginProvider>
          </EmbeddedUiConfigProvider>
        </DndProvider>
      </ReduxProvider>
    </SupersetThemeProvider>
  );
};
