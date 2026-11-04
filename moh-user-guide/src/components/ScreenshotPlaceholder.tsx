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
import React from 'react';
import { ScreenshotData } from '../types/guide';

interface Props {
  data: ScreenshotData;
  className?: string;
}

const WIDTH_CLASS = {
  small: 'max-w-2xl',
  medium: 'max-w-4xl',
  large: 'max-w-6xl',
  full: 'max-w-full',
};

export const ScreenshotPlaceholder: React.FC<Props> = ({ data, className = '' }) => {
  const imageSrc = `${import.meta.env.BASE_URL}${data.imagePath.replace(/^\/+/, '')}`;
  const annotations = data.annotations ?? [];

  return (
    <figure className={`my-6 rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs ${className}`}>
      <figcaption className="px-4 py-2.5 bg-slate-100 border-b border-slate-200 text-xs font-semibold text-slate-900">
        {data.title}
      </figcaption>

      <div className={`relative mx-auto ${WIDTH_CLASS[data.displaySize ?? 'full']}`}>
        <a href={imageSrc} target="_blank" rel="noreferrer" title="Open the full-size picture in a new tab">
          <img src={imageSrc} alt={data.altText} className="block w-full h-auto" />
        </a>
        {annotations
          .filter((ann) => ann.position)
          .map((ann) => (
            <span
              key={ann.number}
              aria-hidden="true"
              style={ann.position}
              className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-rose-600 text-white text-xs font-bold flex items-center justify-center ring-2 ring-white shadow pointer-events-none"
            >
              {ann.number}
            </span>
          ))}
      </div>

      {annotations.length > 0 && (
        <ol className="p-4 border-t border-slate-200 bg-slate-50/60 grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2 text-sm text-slate-700 list-none">
          {annotations.map((ann) => (
            <li key={ann.number} className="flex items-start gap-2.5">
              <span className="w-5 h-5 mt-0.5 rounded-full bg-rose-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
                {ann.number}
              </span>
              <span>
                <strong className="text-slate-900">{ann.title}:</strong> {ann.description}
              </span>
            </li>
          ))}
        </ol>
      )}
    </figure>
  );
};
