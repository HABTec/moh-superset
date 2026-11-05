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
export interface NavItem {
  id: string;
  title: string;
  category: 'GETTING STARTED' | 'USING THE DASHBOARD' | 'COMPARING AND EXPLORING DATA' | 'REFERENCE';
}

export interface ScreenshotAnnotation {
  number: number;
  title: string;
  description: string;
  /** Where the numbered marker sits on the image, as percentages. */
  position?: { top: string; left: string };
}

export interface ScreenshotData {
  id: string;
  title: string;
  altText: string;
  imagePath: string;
  displaySize?: 'small' | 'medium' | 'large' | 'full';
  annotations?: ScreenshotAnnotation[];
}

export interface ModuleSection {
  id: string;
  name: string;
  badgeNumber: string;
  shortSummary: string;
  purpose: string;
  whenToUse: string;
  howToOpen: string[];
  screenshot: ScreenshotData;
  extraScreenshots?: ScreenshotData[];
  tabs: { name: string; description: string }[];
  filters: string[];
  howToRead: string[];
  ifSomethingLooksWrong: string[];
  accessNote?: string;
}

export interface DataSourceItem {
  code: string;
  fullName: string;
  description: string;
  whereUsed: string;
}

export interface FilterOption {
  id: string;
  name: string;
  category: 'Time' | 'Geography' | 'Program Area' | 'Facility & Dataset';
  description: string;
  isDependent: boolean;
  dependentOn?: string;
  whereUsed: string;
}
