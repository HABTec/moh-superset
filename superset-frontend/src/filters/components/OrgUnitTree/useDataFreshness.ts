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

/** Update time per data source (ISO string), `null` when unknown. */
export type DataFreshness = Record<string, string | null>;

const DEFAULT_API_BASE_URL = '/api/v1/moh/dhis2';

const requestsByBaseUrl = new Map<string, Promise<DataFreshness | null>>();

/** Fetches when each data source was last updated, once per page load. */
function fetchDataFreshness(apiBaseUrl: string): Promise<DataFreshness | null> {
  let request = requestsByBaseUrl.get(apiBaseUrl);
  if (!request) {
    request = fetch(`${apiBaseUrl}/data-freshness`, {
      credentials: 'same-origin',
    })
      .then(response => (response.ok ? response.json() : null))
      .then(data => data?.sources ?? null)
      .catch(() => null);
    requestsByBaseUrl.set(apiBaseUrl, request);
  }
  return request;
}

/**
 * When each data source was last updated. `undefined` while loading, `null`
 * when it could not be determined.
 */
export function useDataFreshness(
  apiBaseUrl = DEFAULT_API_BASE_URL,
): DataFreshness | null | undefined {
  const [freshness, setFreshness] = useState<
    DataFreshness | null | undefined
  >();

  useEffect(() => {
    let cancelled = false;
    fetchDataFreshness(apiBaseUrl).then(result => {
      if (!cancelled) {
        setFreshness(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl]);

  return freshness;
}
