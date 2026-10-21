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
import { type ReactNode } from 'react';
import { render, screen } from 'spec/helpers/testing-library';
import { logging } from '@apache-superset/core/utils';
import {
  Theme,
  normalizeThemeConfig,
  isThemeConfigDark,
  useThemeMode,
} from '@apache-superset/core/theme';
import getBootstrapData from 'src/utils/getBootstrapData';
import CrudThemeProvider from './CrudThemeProvider';

jest.mock('@apache-superset/core/theme', () => ({
  ...jest.requireActual('@apache-superset/core/theme'),
  normalizeThemeConfig: jest.fn((config: unknown) => config),
  isThemeConfigDark: jest.fn(() => false),
  useThemeMode: jest.fn(() => false),
}));

jest.mock('src/utils/getBootstrapData', () => ({
  __esModule: true,
  default: jest.fn(() => ({
    common: { theme: { default: {}, dark: {} } },
  })),
}));

const mockGetBootstrapData = getBootstrapData as jest.MockedFunction<
  typeof getBootstrapData
>;
const mockNormalizeThemeConfig = normalizeThemeConfig as jest.MockedFunction<
  typeof normalizeThemeConfig
>;
const mockIsThemeConfigDark = isThemeConfigDark as jest.MockedFunction<
  typeof isThemeConfigDark
>;
const mockUseThemeMode = useThemeMode as jest.MockedFunction<
  typeof useThemeMode
>;

type BootstrapData = ReturnType<typeof getBootstrapData>;
type BootstrapThemes = BootstrapData['common']['theme'];

function mockBootstrap(themes: Partial<BootstrapThemes> = {}): BootstrapData {
  return {
    common: {
      theme: { default: {}, dark: {}, ...themes },
    },
  } as unknown as BootstrapData;
}

const MockSupersetThemeProvider = ({ children }: { children: ReactNode }) => (
  <div data-test="dashboard-theme-provider">{children}</div>
);

beforeEach(() => {
  jest.restoreAllMocks();
  jest.spyOn(Theme, 'fromConfig').mockReturnValue({
    SupersetThemeProvider: MockSupersetThemeProvider,
  } as unknown as Theme);
  mockNormalizeThemeConfig.mockImplementation(
    config => config as ReturnType<typeof normalizeThemeConfig>,
  );
  mockIsThemeConfigDark.mockReturnValue(false);
  mockUseThemeMode.mockReturnValue(false);
  mockGetBootstrapData.mockReturnValue(mockBootstrap());
  // Clean up font style elements from previous tests
  document
    .querySelectorAll('style[data-superset-fonts]')
    .forEach(el => el.remove());
});

test('renders children directly when no theme is provided', () => {
  render(
    <CrudThemeProvider>
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );
  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  expect(
    screen.queryByTestId('dashboard-theme-provider'),
  ).not.toBeInTheDocument();
  expect(Theme.fromConfig).not.toHaveBeenCalled();
});

test('renders children directly when theme is null', () => {
  render(
    <CrudThemeProvider theme={null}>
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );
  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  expect(
    screen.queryByTestId('dashboard-theme-provider'),
  ).not.toBeInTheDocument();
  expect(Theme.fromConfig).not.toHaveBeenCalled();
});

test('wraps children with SupersetThemeProvider when valid theme data is provided', () => {
  const themeConfig = { token: { colorPrimary: '#ff0000' } };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Custom Theme',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );
  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  expect(screen.getByTestId('dashboard-theme-provider')).toBeInTheDocument();
  // The user is in light mode, so the theme is set to the light algorithm
  expect(Theme.fromConfig).toHaveBeenCalledWith(
    { ...themeConfig, algorithm: 'default' },
    expect.anything(),
  );
});

test('creates theme from inline json_data via Theme.fromConfig', () => {
  const themeConfig = { token: { colorPrimary: '#1677ff' } };
  render(
    <CrudThemeProvider
      theme={{
        id: 42,
        theme_name: 'Branded',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );
  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  // No API call can happen — CrudThemeProvider has no fetch/SupersetClient imports.
  // Theme is created synchronously from the inline json_data prop.
  expect(Theme.fromConfig).toHaveBeenCalledWith(
    { ...themeConfig, algorithm: 'default' },
    expect.anything(),
  );
});

test('falls back to rendering children without theme wrapper when json_data is invalid JSON', () => {
  jest.spyOn(logging, 'warn').mockImplementation();
  render(
    <CrudThemeProvider
      theme={{ id: 1, theme_name: 'Bad Theme', json_data: 'not-valid-json' }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );
  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  expect(
    screen.queryByTestId('dashboard-theme-provider'),
  ).not.toBeInTheDocument();
  expect(logging.warn).toHaveBeenCalled();
});

test('falls back to rendering children without theme wrapper when Theme.fromConfig throws', () => {
  (Theme.fromConfig as jest.Mock).mockImplementation(() => {
    throw new Error('Invalid theme config');
  });
  jest.spyOn(logging, 'warn').mockImplementation();
  render(
    <CrudThemeProvider
      theme={{ id: 1, theme_name: 'Bad Theme', json_data: '{}' }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );
  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  expect(
    screen.queryByTestId('dashboard-theme-provider'),
  ).not.toBeInTheDocument();
  expect(logging.warn).toHaveBeenCalled();
});

test('merges dashboard theme with default base theme from bootstrap data', () => {
  const bootstrapDefault = { token: { colorPrimary: '#base-default' } };
  mockGetBootstrapData.mockReturnValue(
    mockBootstrap({ default: bootstrapDefault }),
  );
  mockIsThemeConfigDark.mockReturnValue(false);

  const themeConfig = { token: { colorPrimary: '#custom' } };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Custom Theme',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  // Theme.fromConfig should be called with TWO args: normalized config + base theme
  expect(Theme.fromConfig).toHaveBeenCalledWith(
    expect.objectContaining({
      token: expect.objectContaining({ colorPrimary: '#custom' }),
    }),
    bootstrapDefault,
  );
});

test("follows the user's dark mode when the theme does not set forceMode", () => {
  const bootstrapDark = {
    algorithm: 'dark',
    token: { colorPrimary: '#base-dark' },
  };
  mockGetBootstrapData.mockReturnValue(mockBootstrap({ dark: bootstrapDark }));
  mockUseThemeMode.mockReturnValue(true);

  // A theme saved as light still follows the user into dark mode
  const themeConfig = {
    algorithm: 'default',
    token: { colorPrimary: '#custom' },
  };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Branded Theme',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  expect(Theme.fromConfig).toHaveBeenCalledWith(
    { ...themeConfig, algorithm: 'dark' },
    bootstrapDark,
  );
});

test('uses the dark base when the theme sets forceMode dark, even in light mode', () => {
  const bootstrapDark = {
    algorithm: 'dark',
    token: { colorPrimary: '#base-dark' },
  };
  mockGetBootstrapData.mockReturnValue(mockBootstrap({ dark: bootstrapDark }));
  mockUseThemeMode.mockReturnValue(false);

  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Dark Theme',
        json_data: JSON.stringify({
          forceMode: 'dark',
          token: { colorPrimary: '#custom-dark' },
        }),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  // forceMode is not an Ant Design setting, so it is removed
  expect(Theme.fromConfig).toHaveBeenCalledWith(
    { algorithm: 'dark', token: { colorPrimary: '#custom-dark' } },
    bootstrapDark,
  );
});

test('stays light when the theme sets forceMode light, even in dark mode', () => {
  const bootstrapDefault = { token: { colorPrimary: '#base-default' } };
  mockGetBootstrapData.mockReturnValue(
    mockBootstrap({ default: bootstrapDefault }),
  );
  mockUseThemeMode.mockReturnValue(true);

  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Boardroom TV',
        json_data: JSON.stringify({
          forceMode: 'light',
          token: { fontSize: 22 },
        }),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  expect(Theme.fromConfig).toHaveBeenCalledWith(
    { algorithm: 'default', token: { fontSize: 22 } },
    bootstrapDefault,
  );
});

test('injects font URLs as CSS @import rules', () => {
  const fontUrl = 'https://fonts.example.com/custom.css';
  const themeConfig = {
    token: { colorPrimary: '#ff0000', fontUrls: [fontUrl] },
  };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Font Theme',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  const fontStyle = document.querySelector('style[data-superset-fonts]');
  expect(fontStyle).not.toBeNull();
  expect(fontStyle?.textContent).toContain(`@import url("${fontUrl}")`);
});

test('does not inject fonts when Theme.fromConfig throws even if fontUrls are present', () => {
  (Theme.fromConfig as jest.Mock).mockImplementation(() => {
    throw new Error('Invalid theme config');
  });
  jest.spyOn(logging, 'warn').mockImplementation();
  const themeConfig = {
    token: {
      colorPrimary: '#ff0000',
      fontUrls: ['https://fonts.example.com/custom.css'],
    },
  };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Bad Theme With Fonts',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  const fontStyle = document.querySelector('style[data-superset-fonts]');
  expect(fontStyle).toBeNull();
  expect(logging.warn).toHaveBeenCalled();
});

test('ignores non-array fontUrls in theme config without throwing', () => {
  const themeConfig = {
    token: { colorPrimary: '#ff0000', fontUrls: 'not-an-array' },
  };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'Malformed Fonts',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  expect(screen.getByTestId('dashboard-theme-provider')).toBeInTheDocument();
  const fontStyle = document.querySelector('style[data-superset-fonts]');
  expect(fontStyle).toBeNull();
});

test('does not inject font style element when no fontUrls in config', () => {
  const themeConfig = { token: { colorPrimary: '#ff0000' } };
  render(
    <CrudThemeProvider
      theme={{
        id: 1,
        theme_name: 'No Fonts',
        json_data: JSON.stringify(themeConfig),
      }}
    >
      <div>Dashboard Content</div>
    </CrudThemeProvider>,
  );

  const fontStyle = document.querySelector('style[data-superset-fonts]');
  expect(fontStyle).toBeNull();
});
