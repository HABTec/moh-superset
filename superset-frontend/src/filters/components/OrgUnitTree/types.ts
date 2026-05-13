/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 */
import type { PluginFilterStylesProps } from '../types';

/** One row returned by /api/v1/moh/dhis2/organisationUnits. */
export type OrgUnit = {
  id: string;
  displayName: string;
  level: number;
  path: string;
  children?: OrgUnit[];
};

/** Filter plugin form data (admin-configurable settings). */
export type OrgUnitTreeFormData = {
  apiBaseUrl?: string; // default '/api/v1/moh/dhis2'
  rootLevel?: number;  // default 1
  maxLevel?: number;   // default 6
};

/** Local state — one checked node (rich info kept only in component state). */
export type OrgUnitSelection = {
  id: string;
  displayName: string;
  level: number;
};

export type OrgUnitTreeFilterProps = PluginFilterStylesProps & {
  formData: OrgUnitTreeFormData;
  // Superset persists filterState.value as the flat list of selected names
  // for the chip display. Component holds the rich array separately.
  filterState: { value?: string[] | null };
  setDataMask: (dataMask: {
    filterState?: { value?: string[] | null };
    extraFormData?: { filters?: Array<{ col: string; op: string; val: string[] }> };
  }) => void;
};
