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
export const RESPONSIVE_DASHBOARD_CLASS = 'dashboard--responsive-mode';
export const RESPONSIVE_DASHBOARD_MOBILE_CLASS = 'dashboard--responsive-mobile';
export const RESPONSIVE_DASHBOARD_BODY_CLASS = 'moh-responsive-dashboard';
export const RESPONSIVE_DASHBOARD_MOBILE_BODY_CLASS =
  'moh-responsive-dashboard-mobile';

export const RESPONSIVE_DASHBOARD_BREAKPOINTS = {
  mobile: 768,
  compact: 1024,
};
export const RESPONSIVE_DASHBOARD_MIN_CHART_WIDTH = 240;

const RESPONSIVE_DASHBOARD_PILOT_IDS = new Set([8]);
const RESPONSIVE_DASHBOARD_METADATA_KEYS = [
  'responsive_mobile_enabled',
  'responsive_dashboard_enabled',
];

type ResponsiveDashboardInfo = {
  id?: number;
  metadata?: Record<string, unknown>;
};

export function isResponsiveDashboardEnabled(
  dashboardInfo?: ResponsiveDashboardInfo,
): boolean {
  const metadata = dashboardInfo?.metadata ?? {};
  const metadataOptIn = RESPONSIVE_DASHBOARD_METADATA_KEYS.some(
    key => metadata[key] === true,
  );

  return (
    metadataOptIn ||
    (dashboardInfo?.id != null &&
      RESPONSIVE_DASHBOARD_PILOT_IDS.has(dashboardInfo.id))
  );
}

export function isResponsiveDashboardMobile(width: number): boolean {
  return width < RESPONSIVE_DASHBOARD_BREAKPOINTS.mobile;
}

export function isResponsiveDashboardCompact(width: number): boolean {
  return width <= RESPONSIVE_DASHBOARD_BREAKPOINTS.compact;
}

export function getResponsiveChartHeight(
  layoutHeight: number,
  viewportHeight = typeof window === 'undefined' ? 720 : window.innerHeight,
): number {
  const preferredHeight = Math.round(viewportHeight * 0.58);
  const minHeight = 260;
  const maxHeight = Math.max(320, preferredHeight);

  return Math.max(minHeight, Math.min(layoutHeight, maxHeight));
}

export function getResponsiveChartWidth(
  containerWidth: number,
  maxWidth = typeof window === 'undefined' ? containerWidth : window.innerWidth,
): number {
  const safeMaxWidth = Math.max(0, Math.floor(maxWidth));
  return Math.min(
    safeMaxWidth,
    Math.max(RESPONSIVE_DASHBOARD_MIN_CHART_WIDTH, Math.floor(containerWidth)),
  );
}
