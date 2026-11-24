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
import { getInstanceByDom } from 'echarts/core';

/** Attribute ECharts sets on the DOM node of every chart instance. */
const ECHARTS_INSTANCE_SELECTOR = '[_echarts_instance_]';

type LegendOption = { selector?: unknown };
type ExportableOption = {
  animation?: boolean;
  legend?: LegendOption[];
};

const hasSelector = (selector: unknown): boolean =>
  Array.isArray(selector) ? selector.length > 0 : !!selector;

/**
 * Hides the ECharts legend "Select all" / "Invert selection" buttons on every
 * chart inside `root` for the duration of an export (image or PDF).
 *
 * The buttons are drawn into the chart canvas, so unlike the chart header
 * controls they cannot be dropped from the export with a CSS selector. The
 * charts are redrawn without them, synchronously and without animation so
 * the capture never sees a half-finished layout.
 *
 * @param root - The element being exported
 * @returns A function that puts the buttons back; safe to call once the
 *   charts have been unmounted
 */
export function hideLegendSelectorsForExport(root: ParentNode): () => void {
  const restores: Array<() => void> = [];

  const nodes = [
    ...(root instanceof Element && root.matches(ECHARTS_INSTANCE_SELECTOR)
      ? [root]
      : []),
    ...Array.from(root.querySelectorAll(ECHARTS_INSTANCE_SELECTOR)),
  ] as HTMLElement[];

  nodes.forEach(node => {
    const chart = getInstanceByDom(node);
    if (!chart || chart.isDisposed()) return;

    const option = chart.getOption() as ExportableOption;
    const legends = option.legend ?? [];
    if (!legends.some(legend => hasSelector(legend.selector))) return;

    const { animation } = option;
    try {
      chart.setOption({
        animation: false,
        legend: legends.map(() => ({ selector: false })),
      });
    } catch {
      return;
    }

    restores.push(() => {
      if (chart.isDisposed()) return;
      chart.setOption({
        animation: false,
        legend: legends.map(legend => ({ selector: legend.selector })),
      });
      if (animation !== undefined) chart.setOption({ animation });
    });
  });

  return () => {
    restores.forEach(restore => {
      try {
        restore();
      } catch {
        // A chart re-rendered or torn down mid-export restores itself.
      }
    });
  };
}
