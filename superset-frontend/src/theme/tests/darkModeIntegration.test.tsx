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
/**
 * Dark mode behaviour with the real ThemeController and SupersetThemeProvider
 * (no mocks of theme logic): print preview, themed dashboards, applied themes,
 * forceMode and following the operating system.
 */
import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import { theme as antdTheme } from 'antd';
import { ThemeMode, useTheme } from '@apache-superset/core/theme';
import type { ThemeStorage } from '@apache-superset/core/theme';
import CrudThemeProvider from 'src/components/CrudThemeProvider';
import getBootstrapData from 'src/utils/getBootstrapData';
import { ThemeController } from '../ThemeController';
import { SupersetThemeProvider } from '../ThemeProvider';
import { usePrintInLightMode } from '../usePrintInLightMode';

jest.mock('src/utils/getBootstrapData');

const LIGHT_CARD = '#ffffff';
const DARK_CARD = '#141414';

const THEMES = {
  default: { algorithm: 'default', token: { colorPrimary: '#1a5cff' } },
  dark: { algorithm: 'dark', token: { colorPrimary: '#3d74ff' } },
};

class MemoryStorage implements ThemeStorage {
  values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }

  removeItem(key: string) {
    this.values.delete(key);
  }
}

let osPrefersDark = false;
let osListeners: Array<() => void> = [];

beforeEach(() => {
  osPrefersDark = false;
  osListeners = [];
  (getBootstrapData as jest.Mock).mockReturnValue({
    common: { theme: { ...THEMES, enableUiThemeAdministration: false } },
  });
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn(() => ({
      get matches() {
        return osPrefersDark;
      },
      addEventListener: (_: string, cb: () => void) => osListeners.push(cb),
      removeEventListener: jest.fn(),
    })),
  });
  document.documentElement.removeAttribute('data-theme-mode');
});

const setOsDark = (dark: boolean) => {
  osPrefersDark = dark;
  osListeners.forEach(cb => cb());
};

const Probe = ({ id }: { id: string }) => {
  const theme = useTheme();
  return <div data-test={id}>{theme.colorBgContainer}</div>;
};

const PrintHost = () => {
  usePrintInLightMode();
  return null;
};

const makeController = (
  storage: ThemeStorage,
  initialMode: ThemeMode = ThemeMode.DEFAULT,
) => new ThemeController({ storage, initialMode });

const renderApp = (controller: ThemeController, children = <></>) =>
  render(
    <SupersetThemeProvider themeController={controller}>
      <PrintHost />
      <Probe id="page" />
      {children}
    </SupersetThemeProvider>,
  );

test('new users start in light when the server default is light', () => {
  const controller = makeController(new MemoryStorage());
  osPrefersDark = true;
  renderApp(controller);
  expect(controller.getCurrentMode()).toBe(ThemeMode.DEFAULT);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
  expect(document.documentElement.getAttribute('data-theme-mode')).toBe(
    'light',
  );
});

test('a saved dark choice wins over the server default', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  const controller = makeController(storage);
  renderApp(controller);
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
});

test('printing switches a dark page to light before the print snapshot', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  const controller = makeController(storage);
  renderApp(controller);
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);

  // The browser takes its print snapshot as soon as the handlers return,
  // so the light theme must already be rendered here (no act/await)
  window.dispatchEvent(new Event('beforeprint'));
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
  expect(document.documentElement.getAttribute('data-theme-mode')).toBe(
    'light',
  );

  act(() => {
    window.dispatchEvent(new Event('afterprint'));
  });
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
  // The preview is never saved
  expect(storage.getItem('superset-theme-mode')).toBe('dark');
  expect(controller.getCurrentMode()).toBe(ThemeMode.DARK);
});

test('printing a light page changes nothing', () => {
  const controller = makeController(new MemoryStorage());
  const previewSpy = jest.spyOn(controller, 'previewMode');
  renderApp(controller);
  act(() => {
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('afterprint'));
  });
  expect(previewSpy).not.toHaveBeenCalled();
});

test('a themed dashboard follows a live switch to dark and back', () => {
  const controller = makeController(new MemoryStorage());
  renderApp(
    controller,
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Branded',
        json_data: JSON.stringify({
          algorithm: 'default',
          token: { colorPrimary: '#0374B8' },
        }),
      }}
    >
      <Probe id="dashboard" />
    </CrudThemeProvider>,
  );
  expect(screen.getByTestId('dashboard')).toHaveTextContent(LIGHT_CARD);

  act(() => controller.setThemeMode(ThemeMode.DARK));
  expect(screen.getByTestId('dashboard')).toHaveTextContent(DARK_CARD);

  act(() => controller.setThemeMode(ThemeMode.DEFAULT));
  expect(screen.getByTestId('dashboard')).toHaveTextContent(LIGHT_CARD);
});

test('a dashboard theme with forceMode light stays light in dark mode', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  renderApp(
    makeController(storage),
    <CrudThemeProvider
      theme={{
        id: 2,
        theme_name: 'Boardroom TV',
        json_data: JSON.stringify({ forceMode: 'light', token: {} }),
      }}
    >
      <Probe id="dashboard" />
    </CrudThemeProvider>,
  );
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
  expect(screen.getByTestId('dashboard')).toHaveTextContent(LIGHT_CARD);
});

test('the TV player theme keeps the whole page light on a dark-mode TV box', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'system');
  storage.setItem(
    'superset-dev-theme-override',
    JSON.stringify({ forceMode: 'light', token: { fontSize: 22 } }),
  );
  osPrefersDark = true;
  const controller = makeController(storage);
  renderApp(controller);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
  expect(controller.getCurrentModeResolved()).toBe('light');
});

test('an applied theme without forceMode follows the operating system live', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'system');
  storage.setItem(
    'superset-dev-theme-override',
    JSON.stringify({ token: { colorPrimary: '#ff0000' } }),
  );
  const controller = makeController(storage);
  renderApp(controller);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);

  act(() => setOsDark(true));
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
  expect(controller.hasDevOverride()).toBe(true);
});

test('clearing local theme settings removes the applied theme and resets to light', () => {
  // Upstream behaviour: "Clear local theme" shows what a new user sees
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  storage.setItem(
    'superset-dev-theme-override',
    JSON.stringify({ forceMode: 'light', token: {} }),
  );
  const controller = makeController(storage);
  renderApp(controller);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);

  act(() => controller.clearLocalOverrides());
  expect(controller.hasDevOverride()).toBe(false);
  expect(storage.getItem('superset-dev-theme-override')).toBeNull();
  expect(controller.getCurrentMode()).toBe(ThemeMode.DEFAULT);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
});

test('previewMode restore is safe to call twice and after a mode change', () => {
  const controller = makeController(new MemoryStorage());
  renderApp(controller);

  let restore: () => void = () => {};
  act(() => {
    restore = controller.previewMode(ThemeMode.DARK);
  });
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
  expect(controller.getCurrentModeResolved()).toBe('dark');

  act(() => {
    restore();
    restore();
  });
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
  expect(controller.getCurrentModeResolved()).toBe('light');
});

test('with dark mode disabled, everything stays light and preview is a no-op', () => {
  (getBootstrapData as jest.Mock).mockReturnValue({
    common: { theme: { default: THEMES.default, dark: {} } },
  });
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  osPrefersDark = true;
  const controller = makeController(storage);
  renderApp(controller);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
  expect(controller.getCurrentMode()).toBe(ThemeMode.DEFAULT);

  const restore = controller.previewMode(ThemeMode.DARK);
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);
  restore();
});

test('two overlapping previews keep light until both are done', () => {
  // e.g. a dark-mode user downloads two charts at once
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  const controller = makeController(storage);
  renderApp(controller);

  let first: () => void = () => {};
  let second: () => void = () => {};
  act(() => {
    first = controller.previewMode(ThemeMode.DEFAULT);
    second = controller.previewMode(ThemeMode.DEFAULT);
  });
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);

  act(() => first());
  expect(screen.getByTestId('page')).toHaveTextContent(LIGHT_CARD);

  act(() => second());
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
});

// A complete light theme, like SUPERSET_THEME_DAFULT: it fixes its own
// backgrounds and text colours, so it can only be rendered light
const FULL_LIGHT_THEME = {
  algorithm: 'default',
  token: {
    colorPrimary: '#1E5CE0',
    colorBgBase: '#FFFFFF',
    colorBgContainer: '#FFFFFF',
    colorBgLayout: '#F5F7FB',
    colorText: '#2A3140',
    colorTextBase: '#2A3140',
  },
};

const PrimaryBgProbe = () => {
  const theme = useTheme();
  return <div data-test="primary-bg">{theme.colorPrimaryBg}</div>;
};

test('an applied theme with its own light colours stays light in dark mode', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  storage.setItem(
    'superset-dev-theme-override',
    JSON.stringify(FULL_LIGHT_THEME),
  );
  const controller = makeController(storage);
  render(
    <SupersetThemeProvider themeController={controller}>
      <Probe id="page" />
      <PrimaryBgProbe />
    </SupersetThemeProvider>,
  );
  // No mix of light surfaces with dark-computed fills (navy buttons)
  expect(screen.getByTestId('page')).toHaveTextContent('#FFFFFF');
  expect(controller.getCurrentModeResolved()).toBe('light');
  const lightPrimaryBg = antdTheme.getDesignToken({
    algorithm: antdTheme.defaultAlgorithm,
    token: FULL_LIGHT_THEME.token,
  }).colorPrimaryBg;
  expect(screen.getByTestId('primary-bg')).toHaveTextContent(lightPrimaryBg);
});

test('a dashboard theme with its own light colours stays light in dark mode', () => {
  const storage = new MemoryStorage();
  storage.setItem('superset-theme-mode', 'dark');
  renderApp(
    makeController(storage),
    <CrudThemeProvider
      theme={{
        id: 3,
        theme_name: 'HABTech light',
        json_data: JSON.stringify(FULL_LIGHT_THEME),
      }}
    >
      <Probe id="dashboard" />
      <PrimaryBgProbe />
    </CrudThemeProvider>,
  );
  expect(screen.getByTestId('page')).toHaveTextContent(DARK_CARD);
  expect(screen.getByTestId('dashboard')).toHaveTextContent('#FFFFFF');
  const lightPrimaryBg = antdTheme.getDesignToken({
    algorithm: antdTheme.defaultAlgorithm,
    token: FULL_LIGHT_THEME.token,
  }).colorPrimaryBg;
  expect(screen.getByTestId('primary-bg')).toHaveTextContent(lightPrimaryBg);
});
