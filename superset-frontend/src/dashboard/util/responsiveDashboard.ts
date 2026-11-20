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
/** Set on dashboards that explicitly opted out; only these get the rotate overlay. */
export const RESPONSIVE_DASHBOARD_OPTOUT_BODY_CLASS = 'moh-responsive-optout';

export const RESPONSIVE_DASHBOARD_BREAKPOINTS = {
  mobile: 768,
  compact: 1120,
  phoneLandscapeHeight: 560,
};
export const RESPONSIVE_DASHBOARD_MIN_CHART_WIDTH = 240;

/**
 * Responsive mode is ON for every dashboard. A dashboard can opt out by setting
 * `responsive_dashboard_disabled: true` in its JSON metadata (no deploy needed).
 * The older opt-in keys (`responsive_mobile_enabled`, `responsive_dashboard_enabled`)
 * are still accepted and have no effect, so existing metadata stays valid.
 */
const RESPONSIVE_DASHBOARD_OPTOUT_METADATA_KEY =
  'responsive_dashboard_disabled';

type ResponsiveDashboardInfo = {
  id?: number;
  metadata?: Record<string, unknown>;
};

export function isResponsiveDashboardOptedOut(
  dashboardInfo?: ResponsiveDashboardInfo,
): boolean {
  return (
    dashboardInfo?.metadata?.[RESPONSIVE_DASHBOARD_OPTOUT_METADATA_KEY] === true
  );
}

export function isResponsiveDashboardEnabled(
  dashboardInfo?: ResponsiveDashboardInfo,
): boolean {
  // no dashboard loaded yet: not a dashboard view, nothing to enable
  if (!dashboardInfo) return false;
  return !isResponsiveDashboardOptedOut(dashboardInfo);
}

export function isResponsiveDashboardMobileViewport(
  width: number,
  height = typeof window === 'undefined'
    ? RESPONSIVE_DASHBOARD_BREAKPOINTS.phoneLandscapeHeight + 1
    : window.innerHeight,
): boolean {
  const mobileViewport = width <= RESPONSIVE_DASHBOARD_BREAKPOINTS.mobile;
  const compactViewport = width <= RESPONSIVE_DASHBOARD_BREAKPOINTS.compact;
  const phoneLandscape =
    compactViewport &&
    height <= RESPONSIVE_DASHBOARD_BREAKPOINTS.phoneLandscapeHeight &&
    width > height;

  return mobileViewport || phoneLandscape;
}

export function isResponsiveDashboardMobile(width: number): boolean {
  return isResponsiveDashboardMobileViewport(width);
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

export function getResponsiveKpiChartHeight(
  layoutHeight: number,
  viewportHeight = typeof window === 'undefined' ? 720 : window.innerHeight,
): number {
  const preferredHeight = Math.round(viewportHeight * 0.2);
  const minHeight = 136;
  const maxHeight = Math.max(160, preferredHeight);

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
