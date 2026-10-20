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

type Rgba = { r: number; g: number; b: number; a: number };

const parseColor = (color: string): Rgba | null => {
  const value = color.trim();
  const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const digits =
      hex[1].length === 3
        ? hex[1]
            .split('')
            .map(digit => digit + digit)
            .join('')
        : hex[1];
    return {
      r: parseInt(digits.slice(0, 2), 16),
      g: parseInt(digits.slice(2, 4), 16),
      b: parseInt(digits.slice(4, 6), 16),
      a: 1,
    };
  }
  const rgb = value.match(
    /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i,
  );
  if (rgb) {
    return {
      r: Number(rgb[1]),
      g: Number(rgb[2]),
      b: Number(rgb[3]),
      a: rgb[4] === undefined ? 1 : Number(rgb[4]),
    };
  }
  return null;
};

const toHex = (channel: number) =>
  Math.round(Math.min(255, Math.max(0, channel)))
    .toString(16)
    .padStart(2, '0');

/**
 * Paints a possibly translucent colour over a solid one and returns the
 * resulting solid colour as hex, e.g. a row-stripe tint over the card colour.
 * Returns the base colour unchanged if either colour can't be read.
 */
export default function blendColors(overlay: string, base: string): string {
  const top = parseColor(overlay);
  const bottom = parseColor(base);
  if (!top || !bottom) return base;
  const mix = (front: number, back: number) =>
    front * top.a + back * (1 - top.a);
  return `#${toHex(mix(top.r, bottom.r))}${toHex(mix(top.g, bottom.g))}${toHex(
    mix(top.b, bottom.b),
  )}`;
}
