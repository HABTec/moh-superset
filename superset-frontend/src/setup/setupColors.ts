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
import {
  CategoricalScheme,
  ColorScheme,
  ColorSchemeConfig,
  getCategoricalSchemeRegistry,
  getSequentialSchemeRegistry,
  SequentialScheme,
  SequentialSchemeConfig,
  CategoricalAirbnb,
  CategoricalD3,
  CategoricalEcharts,
  CategoricalGoogle,
  CategoricalLyft,
  CategoricalPreset,
  CategoricalSuperset,
  SequentialCommon,
  SequentialD3,
  ColorSchemeRegistry,
  ColorSchemeGroup,
  CategoricalPresetSuperset,
  CategoricalModernSunset,
  CategoricalColorsOfRainbow,
  CategoricalBlueToGreen,
  CategoricalRedToYellow,
  CategoricalWavesOfBlue,
} from '@superset-ui/core';

function registerColorSchemes<T extends ColorScheme>(
  registry: ColorSchemeRegistry<T>,
  colorSchemes: T[],
  standardDefaultKey: string,
) {
  colorSchemes.forEach(scheme => {
    registry.registerValue(scheme.id, scheme);
  });

  const defaultKey =
    colorSchemes.find(scheme => scheme.isDefault)?.id || standardDefaultKey;
  registry.setDefaultKey(defaultKey);
}

/**
 * A custom colour scheme from the server config may carry a second set of
 * colours, "colorsDark", used while the app is in dark mode (for example
 * ramps that run dim to bright instead of light to dark).
 */
type WithDarkColors<T> = T & { colorsDark?: string[] };

/**
 * Picks the colours for the current mode and drops colorsDark, which the
 * scheme classes don't know about.
 */
function forMode<T extends { colors: string[] }>(
  config: WithDarkColors<T>,
  isDark: boolean,
): T {
  const { colorsDark, ...rest } = config;
  return (
    isDark && colorsDark?.length ? { ...rest, colors: colorsDark } : rest
  ) as T;
}

export default function setupColors(
  extraCategoricalColorSchemeConfigs: WithDarkColors<ColorSchemeConfig>[] = [],
  extraSequentialColorSchemeConfigs: WithDarkColors<SequentialSchemeConfig>[] = [],
  isDark = false,
) {
  const extraCategoricalColorSchemes = extraCategoricalColorSchemeConfigs.map(
    config =>
      new CategoricalScheme({
        ...forMode(config, isDark),
        group: ColorSchemeGroup.Custom,
      }),
  );
  const extraSequentialColorSchemes = extraSequentialColorSchemeConfigs.map(
    config => new SequentialScheme(forMode(config, isDark)),
  );
  registerColorSchemes(
    getCategoricalSchemeRegistry(),
    [
      ...CategoricalAirbnb,
      ...CategoricalD3,
      ...CategoricalEcharts,
      ...CategoricalGoogle,
      ...CategoricalLyft,
      ...CategoricalPreset,
      ...CategoricalSuperset,
      ...CategoricalPresetSuperset,
      ...CategoricalModernSunset,
      ...CategoricalColorsOfRainbow,
      ...CategoricalBlueToGreen,
      ...CategoricalRedToYellow,
      ...CategoricalWavesOfBlue,
      ...extraCategoricalColorSchemes,
    ],
    'supersetColors',
  );
  registerColorSchemes(
    getSequentialSchemeRegistry(),
    [...SequentialCommon, ...SequentialD3, ...extraSequentialColorSchemes],
    'superset_seq_1',
  );
}
