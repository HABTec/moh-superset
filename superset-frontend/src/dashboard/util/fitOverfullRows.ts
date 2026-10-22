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
import { DashboardLayout, LayoutItem } from '../types';
import { COLUMN_TYPE, ROW_TYPE } from './componentTypes';
import { GRID_COLUMN_COUNT, GRID_MIN_COLUMN_COUNT } from './constants';

// Shrinking a column changes the width available to the rows inside it, so
// nested rows are re-checked; real layouts nest at most a couple of levels.
const MAX_PASSES = 5;

/**
 * Scale widths down so they add up to `capacity`, keeping their proportions.
 * Leftover columns from rounding go to the items that lost the most.
 */
function scaleWidths(widths: number[], capacity: number): number[] {
  const total = widths.reduce((sum, width) => sum + width, 0);
  const exact = widths.map(width => (width * capacity) / total);
  const scaled = exact.map(value =>
    Math.max(GRID_MIN_COLUMN_COUNT, Math.floor(value)),
  );
  let leftover = capacity - scaled.reduce((sum, width) => sum + width, 0);
  const byRemainder = exact
    .map((value, index) => ({ index, remainder: value - scaled[index] }))
    .sort((a, b) => b.remainder - a.remainder);
  for (const { index } of byRemainder) {
    if (leftover <= 0) break;
    scaled[index] += 1;
    leftover -= 1;
  }
  return scaled;
}

/**
 * Find rows whose children are wider than the space the row has (12 grid
 * columns, or the width of the column the row sits in) and scale those
 * children down to fit.
 *
 * Such rows look fine when viewing a responsive dashboard, which squeezes
 * them, but in edit mode the grid is fixed-width: the overflow runs under the
 * builder side panel and hides the resize handle needed to fix it.
 *
 * Returns only the components whose width changed, ready for
 * `updateComponents`; an empty object when every row already fits.
 */
export default function fitOverfullRows(
  layout: DashboardLayout,
): Record<string, LayoutItem> {
  const parentOf: Record<string, string> = {};
  Object.values(layout).forEach(item => {
    item?.children?.forEach(childId => {
      parentOf[childId] = item.id;
    });
  });

  const working: DashboardLayout = { ...layout };
  const changed: Record<string, LayoutItem> = {};

  for (let pass = 0; pass < MAX_PASSES; pass += 1) {
    let changedThisPass = false;

    Object.values(working).forEach(row => {
      if (row?.type !== ROW_TYPE || !row.children?.length) return;

      const parent = working[parentOf[row.id]];
      const capacity =
        parent?.type === COLUMN_TYPE && parent.meta?.width
          ? parent.meta.width
          : GRID_COLUMN_COUNT;
      const children = row.children
        .map(childId => working[childId])
        .filter((child): child is LayoutItem => Boolean(child));
      const widths = children.map(child => child.meta?.width || 0);
      const total = widths.reduce((sum, width) => sum + width, 0);
      // A row with more children than columns cannot fit at the minimum
      // width either; leave it as it is rather than squash it further.
      if (
        total <= capacity ||
        children.length * GRID_MIN_COLUMN_COUNT > capacity
      ) {
        return;
      }

      const fitted = scaleWidths(widths, capacity);
      children.forEach((child, index) => {
        if (fitted[index] === widths[index]) return;
        const next = {
          ...child,
          meta: { ...child.meta, width: fitted[index] },
        };
        working[child.id] = next;
        changed[child.id] = next;
        changedThisPass = true;
      });
    });

    if (!changedThisPass) break;
  }

  return changed;
}
