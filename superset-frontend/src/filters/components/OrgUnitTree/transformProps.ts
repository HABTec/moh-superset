/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 */
import { ChartProps } from '@superset-ui/core';
import type { OrgUnitTreeFilterProps, OrgUnitTreeFormData } from './types';

/**
 * Pass-through transform: the component reads directly from props that
 * Superset's filter machinery already injects (formData, filterState,
 * setDataMask). Cascade parent filters land on formData.extra_form_data.
 */
export default function transformProps(chartProps: ChartProps) {
  const { formData, hooks, filterState, width, height, rawFormData } =
    chartProps as ChartProps & {
      formData: OrgUnitTreeFormData & Record<string, unknown>;
      rawFormData?: OrgUnitTreeFormData & Record<string, unknown>;
      hooks?: { setDataMask?: OrgUnitTreeFilterProps['setDataMask'] };
      filterState?: OrgUnitTreeFilterProps['filterState'];
      width?: number;
      height?: number;
    };

  // Prefer the formData SuperChart already merged; fall back to rawFormData
  // so extra_form_data from cascade parents is never dropped.
  const mergedFormData: OrgUnitTreeFormData = {
    ...(rawFormData || {}),
    ...formData,
    extra_form_data:
      formData?.extra_form_data ||
      rawFormData?.extra_form_data ||
      formData?.extraFormData,
  };

  return {
    formData: mergedFormData,
    filterState,
    setDataMask: hooks?.setDataMask,
    width,
    height,
  };
}
