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
import tinycolor from 'tinycolor2';
import { useTheme as useEmotionTheme } from '@emotion/react';
import { theme as antdTheme } from 'antd';
import type {
  SupersetTheme,
  FontSizeKey,
  ColorVariants,
  AnyThemeConfig,
} from '../types';
import { normalizeThemeConfig } from '.';

const fontSizeMap: Record<FontSizeKey, keyof SupersetTheme> = {
  xs: 'fontSizeXS',
  s: 'fontSizeSM',
  m: 'fontSize',
  l: 'fontSizeLG',
  xl: 'fontSizeXL',
  xxl: 'fontSizeXXL',
};

/**
 * Get font size from theme tokens based on size key
 * @param theme - Theme tokens from useTheme()
 * @param size - Font size key
 * @returns Font size as string
 */
export function getFontSize(theme: SupersetTheme, size?: FontSizeKey): string {
  const key = fontSizeMap[size || 'm'];
  return String(theme[key] || theme.fontSize);
}

/**
 * Check if the current theme is dark mode based on background color
 * @param theme - Theme tokens from useTheme()
 * @returns true if theme is dark, false if light
 */
export function isThemeDark(theme: SupersetTheme): boolean {
  return tinycolor(theme.colorBgContainer).isDark();
}

/**
 * Get color variants for a given color type from theme tokens
 * @param theme - Theme tokens from useTheme()
 * @param color - Color type (e.g., 'primary', 'error', 'success')
 * @returns ColorVariants object with bg, border, text colors etc.
 */
export function getColorVariants(
  theme: SupersetTheme,
  color: string,
): ColorVariants {
  const firstLetterCapped = color.charAt(0).toUpperCase() + color.slice(1);

  if (color === 'default' || color === 'grayscale') {
    const isDark = isThemeDark(theme);

    const flipBrightness = (baseColor: string): string => {
      if (!isDark) return baseColor;
      const { r, g, b } = tinycolor(baseColor).toRgb();
      const invertedColor = tinycolor({ r: 255 - r, g: 255 - g, b: 255 - b });
      return invertedColor.toHexString();
    };

    return {
      active: flipBrightness('#222'),
      textActive: flipBrightness('#444'),
      text: flipBrightness('#555'),
      textHover: flipBrightness('#666'),
      hover: flipBrightness('#888'),
      borderHover: flipBrightness('#AAA'),
      border: flipBrightness('#CCC'),
      bgHover: flipBrightness('#DDD'),
      bg: flipBrightness('#F4F4F4'),
    };
  }

  return {
    active: theme[
      `color${firstLetterCapped}Active` as keyof SupersetTheme
    ] as string,
    textActive: theme[
      `color${firstLetterCapped}TextActive` as keyof SupersetTheme
    ] as string,
    text: theme[
      `color${firstLetterCapped}Text` as keyof SupersetTheme
    ] as string,
    textHover: theme[
      `color${firstLetterCapped}TextHover` as keyof SupersetTheme
    ] as string,
    hover: theme[
      `color${firstLetterCapped}Hover` as keyof SupersetTheme
    ] as string,
    borderHover: theme[
      `color${firstLetterCapped}BorderHover` as keyof SupersetTheme
    ] as string,
    border: theme[
      `color${firstLetterCapped}Border` as keyof SupersetTheme
    ] as string,
    bgHover: theme[
      `color${firstLetterCapped}BgHover` as keyof SupersetTheme
    ] as string,
    bg: theme[`color${firstLetterCapped}Bg` as keyof SupersetTheme] as string,
  };
}

/**
 * Check if a theme configuration results in a dark theme
 * @param config - The theme configuration to check
 * @returns true if the config results in a dark theme, false otherwise
 */
export function isThemeConfigDark(config: AnyThemeConfig): boolean {
  try {
    const normalizedConfig = normalizeThemeConfig(config);
    const themeConfig = antdTheme.getDesignToken(normalizedConfig);

    return tinycolor(themeConfig.colorBgContainer).isDark();
  } catch {
    return false;
  }
}

/**
 * A theme's "forceMode" setting. A theme with forceMode always renders in that
 * mode (for example a wall-TV theme that must stay light); a theme without it
 * follows the user's light/dark choice.
 */
export type ThemeForceMode = 'light' | 'dark';

/**
 * Reads a theme's forceMode setting, if it has a valid one.
 * @param config - The theme configuration to read
 * @returns "light", "dark", or undefined when the theme follows the user
 */
export function getThemeForceMode(
  config: AnyThemeConfig | null | undefined,
): ThemeForceMode | undefined {
  const value = (config as { forceMode?: unknown } | null | undefined)
    ?.forceMode;
  return value === 'light' || value === 'dark' ? value : undefined;
}

// Colours that only work in one mode: backgrounds, text, borders and fills
const MODE_SPECIFIC_COLOR_TOKEN = /^color(Bg|Text|Border|Fill|Split)/;

/**
 * The mode a theme must render in, if any. An explicit forceMode wins. A
 * theme that sets its own background or text colours (a complete light or
 * dark palette) keeps the mode those colours belong to; rendering it in the
 * other mode would mix its fixed colours with ones computed for that mode.
 * A theme that only sets brand details (fonts, primary colour) follows the
 * user's mode.
 * @param config - The theme configuration
 * @returns "light", "dark", or undefined when the theme follows the user
 */
export function getEffectiveForceMode(
  config: AnyThemeConfig | null | undefined,
): ThemeForceMode | undefined {
  const explicit = getThemeForceMode(config);
  if (explicit || !config) return explicit;
  const token = (config as { token?: Record<string, unknown> }).token ?? {};
  const setsModeColors = Object.keys(token).some(key =>
    MODE_SPECIFIC_COLOR_TOKEN.test(key),
  );
  if (!setsModeColors) return undefined;
  return isThemeConfigDark(config) ? 'dark' : 'light';
}

const isModeAlgorithm = (algorithm: unknown): boolean =>
  algorithm === 'default' ||
  algorithm === 'dark' ||
  algorithm === antdTheme.defaultAlgorithm ||
  algorithm === antdTheme.darkAlgorithm;

/**
 * Returns a copy of a theme set to light or dark. Other algorithms, such as
 * compact, are kept, and forceMode is removed because it is not an Ant Design
 * setting.
 * @param config - The theme configuration (serializable or Ant Design form)
 * @param isDark - true for the dark algorithm, false for the light one
 */
export function applyThemeMode<T extends AnyThemeConfig>(
  config: T,
  isDark: boolean,
): T {
  const result: Record<string, unknown> = { ...config };
  delete result.forceMode;

  const current = result.algorithm;
  const algorithms: unknown[] = Array.isArray(current)
    ? current
    : current
      ? [current]
      : [];
  const others = algorithms.filter(algorithm => !isModeAlgorithm(algorithm));
  const isSerializable = algorithms.every(
    algorithm => typeof algorithm === 'string',
  );
  const lightAlgorithm = isSerializable
    ? 'default'
    : antdTheme.defaultAlgorithm;
  const darkAlgorithm = isSerializable ? 'dark' : antdTheme.darkAlgorithm;
  const mode = isDark ? darkAlgorithm : lightAlgorithm;

  result.algorithm = others.length ? [mode, ...others] : mode;
  return result as T;
}

/**
 * Hook to determine if the current theme is dark mode
 * @returns true if theme is dark, false if light
 */
export function useThemeMode(): boolean {
  const theme = useEmotionTheme() as SupersetTheme;
  return isThemeDark(theme);
}
