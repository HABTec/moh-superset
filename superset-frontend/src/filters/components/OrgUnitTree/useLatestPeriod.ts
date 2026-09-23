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
import { formatFilterOptionLabel } from 'src/filters/utils/filterDisplay';

export type LatestPeriod = {
  period: string;
  fiscalYear: string;
  quarter: number;
  monthName: string;
};

const DEFAULT_API_BASE_URL = '/api/v1/moh/dhis2';

const requestsByBaseUrl = new Map<string, Promise<LatestPeriod | null>>();

/** Fetches the latest completed month with data once per page load. */
function fetchLatestPeriod(apiBaseUrl: string): Promise<LatestPeriod | null> {
  let request = requestsByBaseUrl.get(apiBaseUrl);
  if (!request) {
    request = fetch(`${apiBaseUrl}/latest-period`, {
      credentials: 'same-origin',
    })
      .then(response => (response.ok ? response.json() : null))
      .then(data => data?.latestPeriod ?? null)
      .catch(() => null);
    requestsByBaseUrl.set(apiBaseUrl, request);
  }
  return request;
}

/** e.g. "Latest: 2019 EFY · Q1 · Nehase"; a generic label when unknown. */
export function formatLatestPeriod(period?: LatestPeriod | null): string {
  if (!period) {
    return t('Latest period');
  }
  return t(
    'Latest: %s',
    [
      formatFilterOptionLabel(String(period.fiscalYear), 'fiscal_year'),
      `Q${period.quarter}`,
      period.monthName,
    ]
      .filter(Boolean)
      .join(' · '),
  );
}

/**
 * The latest completed month that has data. `undefined` while loading, `null`
 * when it could not be determined.
 */
export function useLatestPeriod(
  enabled = true,
  apiBaseUrl = DEFAULT_API_BASE_URL,
): LatestPeriod | null | undefined {
  const [period, setPeriod] = useState<LatestPeriod | null | undefined>();

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    let cancelled = false;
    fetchLatestPeriod(apiBaseUrl).then(result => {
      if (!cancelled) {
        setPeriod(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, apiBaseUrl]);

  return period;
}
