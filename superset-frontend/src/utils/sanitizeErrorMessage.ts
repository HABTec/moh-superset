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
import { t } from '@apache-superset/core/translation';

/**
 * Signs that a message was written for developers rather than users. Mirrors
 * `TECHNICAL_MARKERS` in `superset/utils/error_sanitizer.py`; the server
 * already replaces such messages, so this is a safety net for messages that
 * originate in the browser (e.g. a chart plugin crashing while rendering).
 */
const TECHNICAL_MARKERS = new RegExp(
  [
    'Traceback',
    '\\bDB::',
    '\\bCode:\\s*\\d+',
    'https?://',
    '\\b\\d{1,3}(?:\\.\\d{1,3}){3}\\b',
    '\\blocalhost:\\d+',
    '\\b\\w+(?:Exception|Error)\\b(?:\\s*[:(]|$)',
    '\\bpsycopg',
    '\\bsqlalchemy',
    '\\bclickhouse',
    '\\bHTTPDriver',
    '\\bErrno\\b',
    '\\bline \\d+',
    '\\.py\\b',
    'object has no attribute',
    'NoneType',
    'Cannot read propert',
    'is not a function',
    'is not defined',
    '\\(Background on this error',
    '\\bSELECT\\s[\\s\\S]+\\sFROM\\s',
  ].join('|'),
  'i',
);

export const GENERIC_ERROR_MESSAGE = t(
  'Something went wrong while loading this.',
);

export const isTechnicalErrorMessage = (message: string): boolean =>
  TECHNICAL_MARKERS.test(message);

/** Returns `message`, or a generic message when it contains technical detail. */
export function sanitizeErrorMessage(message: string): string {
  return isTechnicalErrorMessage(message) ? GENERIC_ERROR_MESSAGE : message;
}
