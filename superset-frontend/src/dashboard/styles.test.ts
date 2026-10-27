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
import { supersetTheme } from '@apache-superset/core/theme';
import { printStyles } from './styles';

const printCss = printStyles(supersetTheme).styles;
const compactCss = printCss.replace(/\s+/g, '');

test('print styles only apply to print media', () => {
  expect(printCss.trim().startsWith('@media print')).toBe(true);
});

test('print styles hide navigation, filter rail, tabs, chart controls and ASK AI', () => {
  [
    '#main-menu',
    "[data-test='dashboard-filters-panel']",
    '.dashboard-component-tabs .ant-tabs-nav',
    '.right-button-panel',
    "[data-test='slice-header'] .header-controls",
    '.moh-ai-overlay',
  ].forEach(selector => expect(printCss).toContain(selector));
  expect(compactCss).toContain('display:none!important');
});

test('print styles keep each chart on one page and use a plain background', () => {
  expect(compactCss).toContain('break-inside:avoid;');
  expect(compactCss).toContain(`background:${supersetTheme.colorBgBase}`);
});
