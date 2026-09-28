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
import {
  createContext,
  FC,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
} from 'react';
import { AntdThemeProvider } from '@superset-ui/core/components';
import { useToasts } from 'src/components/MessageToasts/withToasts';
import { useFullscreen } from 'src/explore/hooks/useFullscreen';
import {
  EXPLORE_FULLSCREEN_TEST_ID,
  exploreFullscreenStyles,
} from './Styles';

export type ExploreFullscreenContextValue = {
  /**
   * Whether an `ExploreFullscreen` provider is present. Controls only offer
   * the fullscreen action when there is something to go fullscreen with, so
   * components rendered outside the container keep their current menus.
   */
  isAvailable: boolean;
  isFullscreen: boolean;
  isSupported: boolean;
  toggle: () => void;
  exit: () => void;
};

const noop = () => {};

const defaultContext: ExploreFullscreenContextValue = {
  isAvailable: false,
  isFullscreen: false,
  isSupported: false,
  toggle: noop,
  exit: noop,
};

export const ExploreFullscreenContext =
  createContext<ExploreFullscreenContextValue>(defaultContext);

export const useExploreFullscreen = () => useContext(ExploreFullscreenContext);

const containerStyles = exploreFullscreenStyles;

/**
 * Wraps the Explore header, filter bar and chart so they can fill the screen
 * together. Leaving the children in the normal document flow while not
 * fullscreen means the page looks and behaves exactly as it did before.
 */
const ExploreFullscreen: FC<{ children: ReactNode }> = ({ children }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { addDangerToast } = useToasts();

  const { isFullscreen, isSupported, toggle, exit } = useFullscreen({
    targetRef: containerRef,
    onError: addDangerToast,
  });

  const contextValue = useMemo(
    () => ({
      isAvailable: true,
      isFullscreen,
      isSupported,
      toggle,
      exit,
    }),
    [isFullscreen, isSupported, toggle, exit],
  );

  const getPopupContainer = useCallback(
    () => containerRef.current ?? document.body,
    [],
  );

  // Ant Design portals popovers, dropdowns, tooltips and select menus onto
  // document.body, which sits outside the fullscreen element and is therefore
  // invisible while fullscreen. Only the fullscreen case needs them redirected,
  // so outside fullscreen Ant Design keeps its own default and Explore behaves
  // exactly as it did before.
  const content = isFullscreen ? (
    <AntdThemeProvider getPopupContainer={getPopupContainer}>
      {children}
    </AntdThemeProvider>
  ) : (
    children
  );

  return (
    <ExploreFullscreenContext.Provider value={contextValue}>
      <div
        ref={containerRef}
        css={containerStyles}
        data-fullscreen={isFullscreen}
        data-test={EXPLORE_FULLSCREEN_TEST_ID}
      >
        {content}
      </div>
    </ExploreFullscreenContext.Provider>
  );
};

export default ExploreFullscreen;
