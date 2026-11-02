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
import { DataMask, FilterState, QueryFormColumn } from '@superset-ui/core';

type CellValue = string | number | boolean;

/** A clicked heatmap cell: its x-axis and y-axis values. */
export type HeatmapCell = [CellValue, CellValue];

const sameCell = (a: HeatmapCell, b: HeatmapCell) =>
  String(a[0]) === String(b[0]) && String(a[1]) === String(b[1]);

const unique = (values: CellValue[]) =>
  values.filter(
    (value, index) =>
      values.findIndex(other => String(other) === String(value)) === index,
  );

/** Cells clicked on this chart, as stored in its cross-filter state. */
export function getSelectedCells(filterState?: FilterState): HeatmapCell[] {
  const value = filterState?.value;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (cell): cell is HeatmapCell => Array.isArray(cell) && cell.length === 2,
  );
}

/**
 * The selection after clicking `cell`. A plain click selects only that cell,
 * or clears the selection when it is the only selected cell. An additive
 * (Ctrl/Cmd) click adds the cell, or removes it when already selected.
 */
export function toggleCell(
  selected: HeatmapCell[],
  cell: HeatmapCell,
  additive: boolean,
): HeatmapCell[] {
  const isSelected = selected.some(other => sameCell(other, cell));
  if (additive) {
    return isSelected
      ? selected.filter(other => !sameCell(other, cell))
      : [...selected, cell];
  }
  return isSelected && selected.length === 1 ? [] : [cell];
}

/**
 * Whether a cell is covered by the cross-filter. The filter is "x in the
 * selected x values AND y in the selected y values", so with several cells
 * selected every combination of their rows and columns is included.
 */
export function isCellInSelection(
  selected: HeatmapCell[],
  x: CellValue,
  y: CellValue,
): boolean {
  return (
    selected.some(([sx]) => String(sx) === String(x)) &&
    selected.some(([, sy]) => String(sy) === String(y))
  );
}

/** Cross-filter data mask filtering both axis columns on the selection. */
export function getHeatmapCrossFilterDataMask({
  cells,
  xAxis,
  yAxis,
  formatX = String,
  formatY = String,
}: {
  cells: HeatmapCell[];
  xAxis: QueryFormColumn;
  yAxis: QueryFormColumn;
  formatX?: (value: CellValue) => string;
  formatY?: (value: CellValue) => string;
}): DataMask {
  if (cells.length === 0) {
    return {
      extraFormData: { filters: [] },
      filterState: { value: null, label: undefined },
    };
  }
  return {
    extraFormData: {
      filters: [
        { col: xAxis, op: 'IN', val: unique(cells.map(([x]) => x)) },
        { col: yAxis, op: 'IN', val: unique(cells.map(([, y]) => y)) },
      ],
    },
    filterState: {
      value: cells,
      label: cells.map(([x, y]) => `${formatY(y)} × ${formatX(x)}`).join(', '),
    },
  };
}
