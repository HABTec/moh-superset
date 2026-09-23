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
import { useEffect, useState } from 'react';
import { t } from '@apache-superset/core/translation';

export type AssignedOrgUnit = { id: string; name: string; level: number };

const DEFAULT_API_BASE_URL = '/api/v1/moh/dhis2';

const requestsByBaseUrl = new Map<string, Promise<AssignedOrgUnit | null>>();

/**
 * Test-only: clears the per-page-load cache so a suite can mock a different
 * response for a later test. Not used in the running application.
 */
export function resetAssignedOrgUnitCacheForTests(): void {
  requestsByBaseUrl.clear();
}

/** Fetches the logged-in user's assigned org unit once per page load. */
function fetchAssignedOrgUnit(
  apiBaseUrl: string,
): Promise<AssignedOrgUnit | null> {
  let request = requestsByBaseUrl.get(apiBaseUrl);
  if (!request) {
    request = fetch(`${apiBaseUrl}/me/organisationUnit`, {
      credentials: 'same-origin',
    })
      .then(response => (response.ok ? response.json() : null))
      .then(data => data?.organisationUnit ?? null)
      .catch(() => null);
    requestsByBaseUrl.set(apiBaseUrl, request);
  }
  return request;
}

/**
 * Label describing the area shown while no org unit is selected. Datasets scope
 * an empty selection to the logged-in user's assigned unit, or to the whole
 * country for national (level 1) users and users without an assignment.
 */
export function getOrgUnitScopeLabel(unit?: AssignedOrgUnit | null): string {
  if (!unit || unit.level <= 1 || !unit.name) {
    return t('National / Ethiopia');
  }
  return unit.name;
}

/**
 * The logged-in user's assigned org unit. `undefined` while loading, `null`
 * when the user has no assignment or the lookup failed.
 */
export function useAssignedOrgUnit(
  enabled = true,
  apiBaseUrl = DEFAULT_API_BASE_URL,
): AssignedOrgUnit | null | undefined {
  const [unit, setUnit] = useState<AssignedOrgUnit | null | undefined>();

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    let cancelled = false;
    fetchAssignedOrgUnit(apiBaseUrl).then(result => {
      if (!cancelled) {
        setUnit(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, apiBaseUrl]);

  return unit;
}
