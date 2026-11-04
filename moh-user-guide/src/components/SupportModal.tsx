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
import { LifeBuoy, MessageSquare, X } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const SupportModal: React.FC<Props> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="support-modal-title"
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div className="relative w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <LifeBuoy className="w-5 h-5 text-blue-300" aria-hidden="true" />
            <h3 id="support-modal-title" className="text-base font-bold">Getting help</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
            aria-label="Close help dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4 text-sm text-slate-700 leading-relaxed">
          <p>
            <strong className="text-slate-900">For a login or access problem,</strong> contact the person in your
            organisation who gave you your account, or your dashboard administrator.
          </p>
          <p>
            <strong className="text-slate-900">To report a problem or suggest an improvement,</strong> use the
            Feedback form.
          </p>
          <a
            href="/feedback/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-900 text-white rounded-lg text-sm font-semibold hover:bg-blue-800 transition-colors"
          >
            <MessageSquare className="w-4 h-4" aria-hidden="true" />
            <span>Open the Feedback form</span>
          </a>
          <div>
            <strong className="text-slate-900 block mb-1">Include these details:</strong>
            <ul className="list-disc pl-5 space-y-1">
              <li>Your username and organisation unit</li>
              <li>The section and tab, for example Data Quality, Monthly</li>
              <li>The chart name and the filters you used</li>
              <li>A screenshot of the problem, without any personal information about patients</li>
            </ul>
          </div>
        </div>

        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800 transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
