/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 */
import { ChartProps } from '@superset-ui/core';

/**
 * Pass-through transform: the component reads directly from props that
 * Superset's filter machinery already injects (formData, filterState,
 * setDataMask). Nothing to compute here.
 */
export default function transformProps(chartProps: ChartProps) {
  const { formData, hooks, filterState, width, height } = chartProps as any;
  return {
    formData,
    filterState,
    setDataMask: hooks?.setDataMask,
    width,
    height,
  };
}
