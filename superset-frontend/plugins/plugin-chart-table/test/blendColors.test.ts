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
import blendColors from '../src/utils/blendColors';

test('blends a light-mode stripe tint over white into #f5f5f5', () => {
  expect(blendColors('rgba(0,0,0,0.04)', '#ffffff')).toBe('#f5f5f5');
});

test('blends a dark-mode stripe tint over the dark card colour', () => {
  expect(blendColors('rgba(255, 255, 255, 0.08)', '#141414')).toBe('#272727');
});

test('returns the overlay when it is solid', () => {
  expect(blendColors('#abc', '#ffffff')).toBe('#aabbcc');
  expect(blendColors('rgb(1, 2, 3)', '#ffffff')).toBe('#010203');
});

test('returns the base colour when a colour cannot be read', () => {
  expect(blendColors('transparent', '#141414')).toBe('#141414');
  expect(blendColors('rgba(0,0,0,0.5)', 'not-a-colour')).toBe('not-a-colour');
});
