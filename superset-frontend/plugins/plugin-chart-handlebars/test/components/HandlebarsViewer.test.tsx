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
import { render, screen } from 'spec/helpers/testing-library';
import {
  HandlebarsViewer,
  removeLineIndentation,
} from '../../src/components/Handlebars/HandlebarsViewer';

// react-markdown is stubbed for all tests (spec/helpers/shim.tsx), so this
// checks the Markdown source the viewer hands to SafeMarkdown
jest.mock('@superset-ui/core/components', () => ({
  SafeMarkdown: ({ source }: { source: string }) => (
    <pre data-test="markdown-source">{source}</pre>
  ),
}));

// An indented card like the dashboard KPI templates, with the value on its
// own line between the opening and closing tags
const kpiTemplate = `{{#each data}}
<div>

  <div>
    <div>PERFORMANCE</div>
    <div>
      {{Performance}}
    </div>
  </div>

</div>
{{/each}}`;

const markdownSource = () =>
  screen.getByTestId('markdown-source').textContent ?? '';

test('removeLineIndentation strips leading spaces and tabs from every line', () => {
  expect(
    removeLineIndentation('<div>\n    <span>a</span>\n\t\t<b>b</b>\n</div>'),
  ).toBe('<div>\n<span>a</span>\n<b>b</b>\n</div>');
});

test('removeLineIndentation leaves text inside a line untouched', () => {
  expect(removeLineIndentation('  <p>two  spaces   inside</p>')).toBe(
    '<p>two  spaces   inside</p>',
  );
});

test('an empty value leaves no indented line that Markdown would show as code', () => {
  render(
    <HandlebarsViewer
      templateSource={kpiTemplate}
      data={{ data: [{ Performance: null }] }}
    />,
  );

  const source = markdownSource();
  // Markdown shows a line indented by 4+ spaces after a blank line as code
  expect(source).not.toMatch(/^ {4}/m);
  expect(source).toContain('\n</div>');
});

test('a value that is present is passed through unchanged', () => {
  render(
    <HandlebarsViewer
      templateSource={kpiTemplate}
      data={{ data: [{ Performance: 113.43 }] }}
    />,
  );

  expect(markdownSource()).toContain('\n113.43\n</div>');
});
