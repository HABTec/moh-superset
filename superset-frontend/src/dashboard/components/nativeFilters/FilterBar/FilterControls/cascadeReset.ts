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
import { isEqual } from 'lodash';

/**
 * Snapshot of the pending (pre-Apply) values of a dependent filter's
 * ancestors, keyed by ancestor filter id.
 */
export type ParentValues = Record<string, unknown>;

/**
 * Whether a filter value represents "nothing selected". Range filters use
 * `[null, null]` as their empty value; other filters use null/undefined or an
 * empty array.
 */
export const isEmptyFilterValue = (value: unknown): boolean =>
  value == null || (Array.isArray(value) && value.every(item => item == null));

/**
 * The value a dependent filter is reset to when an ancestor changes.
 * `null` (rather than `undefined`) keeps filter plugins from re-applying their
 * configured default value, which may be just as invalid for the new parent.
 */
export const getCascadeClearedValue = (filterType?: string) =>
  filterType === 'filter_range' ? [null, null] : null;

/**
 * Decide whether a dependent filter's own selection is stale because one of
 * its ancestors was changed or cleared by the user.
 *
 * Transitions that are not user edits are ignored:
 * - an ancestor receiving its first value (initial load, defaults);
 * - the filter's own value changing in the same update as its ancestor
 *   (applied state restored from a URL/permalink, or a dashboard switch);
 * - the filter already being empty (avoids redundant resets down a chain).
 */
export const shouldClearForParentChange = ({
  prevParentValues,
  parentValues,
  prevOwnValue,
  ownValue,
}: {
  prevParentValues: ParentValues;
  parentValues: ParentValues;
  prevOwnValue: unknown;
  ownValue: unknown;
}): boolean => {
  if (isEmptyFilterValue(ownValue) || !isEqual(prevOwnValue, ownValue)) {
    return false;
  }
  return Object.keys(parentValues).some(parentId => {
    const prev = prevParentValues[parentId];
    return prev !== undefined && !isEqual(prev, parentValues[parentId]);
  });
};
