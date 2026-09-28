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
import { css, SupersetTheme } from '@apache-superset/core/theme';

export const EXPLORE_FULLSCREEN_TEST_ID = 'explore-fullscreen-container';
export const EXPLORE_FILTER_BAR_TEST_ID = 'explore-filter-bar';
/**
 * Styling for the element the Fullscreen API is called on.
 *
 * The rules are shared by the native `:fullscreen` state and by the CSS-only
 * fallback keyed off `data-fullscreen`, so both look and behave the same.
 *
 * While not fullscreen the element is a plain flex column, which is what
 * Explore's layout already expects of it, so nothing about the page changes.
 * It deliberately keeps a box at all times because the Fullscreen API needs
 * one to promote.
 */
export const exploreFullscreenStyles = (theme: SupersetTheme) => css`
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;

  &[data-fullscreen='true'],
  &:fullscreen {
    display: flex;
    flex-direction: column;
    position: fixed;
    inset: 0;
    z-index: ${theme.zIndexPopupBase};
    width: 100vw;
    height: 100vh;
    max-width: 100vw;
    max-height: 100vh;
    box-sizing: border-box;
    padding: ${theme.sizeUnit * 4}px;
    overflow: auto;
    background: ${theme.colorBgBase};
    color: ${theme.colorText};
    pointer-events: auto;
    opacity: 1;
    visibility: visible;
  }

  /* Restore the page box model the dashboard header styles depend on. */
  &:fullscreen {
    border: none;
  }

  /* Ant Design appends popovers, dropdowns, tooltips and select menus into a
     portal. getPopupContainer points that portal at this element, so these
     popups need positioning against it rather than the page. */
  &[data-fullscreen='true'] > .ant-popover,
  &[data-fullscreen='true'] > .ant-dropdown,
  &[data-fullscreen='true'] > .ant-select-dropdown,
  &[data-fullscreen='true'] > .ant-tooltip,
  &:fullscreen > .ant-popover,
  &:fullscreen > .ant-dropdown,
  &:fullscreen > .ant-select-dropdown,
  &:fullscreen > .ant-tooltip {
    position: absolute;
    z-index: ${theme.zIndexPopupBase + 1};
    pointer-events: auto;
  }
`;
