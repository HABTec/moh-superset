/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 */
import { NativeFilterType } from '@superset-ui/core';
import {
  getCbmpTypesFromFormData,
  getCbmpTypesFromDashboard,
} from './OrgUnitTreeFilter';

test('getCbmpTypesFromFormData returns empty when no parent filter', () => {
  expect(getCbmpTypesFromFormData({})).toEqual([]);
  expect(
    getCbmpTypesFromFormData({ extra_form_data: { filters: [] } }),
  ).toEqual([]);
});

test('getCbmpTypesFromFormData reads cbmp_type from cascade filters', () => {
  expect(
    getCbmpTypesFromFormData({
      extra_form_data: {
        filters: [
          { col: 'cbmp_type', val: ['CBMP Hospital', 'CBMP Woreda'] },
          { col: 'region', val: ['Oromia'] },
        ],
      },
    }),
  ).toEqual(['CBMP Hospital', 'CBMP Woreda']);
});

test('getCbmpTypesFromFormData accepts cbmp column alias and scalar values', () => {
  expect(
    getCbmpTypesFromFormData({
      extraFormData: {
        filters: [{ col: 'CBMP', val: 'CBMP Hospital' }],
      },
    }),
  ).toEqual(['CBMP Hospital']);
});

test('getCbmpTypesFromDashboard finds CBMP by filter name without cascade', () => {
  const filters = {
    'NATIVE_FILTER-cbmp': {
      id: 'NATIVE_FILTER-cbmp',
      name: 'CBMP',
      filterType: 'filter_select',
      type: NativeFilterType.NativeFilter,
      targets: [{ column: { name: 'some_other_col' } }],
      cascadeParentIds: [],
      scope: { rootPath: [], excluded: [] },
      controlValues: {},
      defaultDataMask: {},
      description: '',
    },
    'NATIVE_FILTER-org': {
      id: 'NATIVE_FILTER-org',
      name: 'Org Unit',
      filterType: 'filter_org_unit_tree',
      type: NativeFilterType.NativeFilter,
      targets: [],
      cascadeParentIds: [],
      scope: { rootPath: [], excluded: [] },
      controlValues: {},
      defaultDataMask: {},
      description: '',
    },
  };
  const dataMask = {
    'NATIVE_FILTER-cbmp': {
      id: 'NATIVE_FILTER-cbmp',
      extraFormData: {
        filters: [{ col: 'some_other_col', op: 'IN', val: ['CBMP Hospital'] }],
      },
      filterState: { value: ['CBMP Hospital'] },
    },
  };

  expect(getCbmpTypesFromDashboard(filters as any, dataMask as any)).toEqual([
    'CBMP Hospital',
  ]);
});

test('getCbmpTypesFromDashboard returns empty when CBMP not selected', () => {
  const filters = {
    'NATIVE_FILTER-cbmp': {
      id: 'NATIVE_FILTER-cbmp',
      name: 'CBMP',
      filterType: 'filter_select',
      type: NativeFilterType.NativeFilter,
      targets: [{ column: { name: 'cbmp_type' } }],
      cascadeParentIds: [],
      scope: { rootPath: [], excluded: [] },
      controlValues: {},
      defaultDataMask: {},
      description: '',
    },
  };
  const dataMask = {
    'NATIVE_FILTER-cbmp': {
      id: 'NATIVE_FILTER-cbmp',
      extraFormData: { filters: [] },
      filterState: { value: null },
    },
  };
  expect(getCbmpTypesFromDashboard(filters as any, dataMask as any)).toEqual(
    [],
  );
});
