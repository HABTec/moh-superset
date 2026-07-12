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
  cloneElement,
  memo,
  ReactElement,
  RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { css, styled } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import {
  LineEditableTabs,
  TabsProps as AntdTabsProps,
} from '@superset-ui/core/components/Tabs';
import { Icons } from '@superset-ui/core/components/Icons';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  DndContext,
  PointerSensor,
  useSensor,
  closestCenter,
} from '@dnd-kit/core';
import {
  horizontalListSortingStrategy,
  SortableContext,
  useSortable,
} from '@dnd-kit/sortable';
import HoverMenu from '../../menu/HoverMenu';
import DragHandle from '../../dnd/DragHandle';
import DeleteComponentButton from '../../DeleteComponentButton';

const StyledTabsContainer = styled.div<{ isDragging?: boolean }>`
  width: 100%;
  background-color: ${({ theme }) => theme.colorBgContainer};
  position: relative;

  & .dashboard-component-tabs-content {
    height: 100%;
  }

  & > .hover-menu:hover {
    opacity: 1;
  }

  &.dragdroppable-row .dashboard-component-tabs-content {
    height: calc(100% - 47px);
  }

  /* Ensure tab labels maintain full opacity during drag */
  .ant-tabs-tab {
    .dragdroppable-tab,
    .editable-title,
    textarea {
      opacity: 1;
      color: inherit;
    }
  }

  &.dashboard-component-tabs--responsive-scroll {
    .ant-tabs-nav-wrap {
      overflow-x: auto !important;
      overflow-y: hidden;
      scroll-behavior: auto;
      scrollbar-width: none;
      touch-action: pan-x;
      user-select: none;
      cursor: default;
    }

    .ant-tabs-nav-wrap::-webkit-scrollbar {
      display: none;
    }

    .ant-tabs-nav-wrap::before,
    .ant-tabs-nav-wrap::after {
      box-shadow: none !important;
      display: none !important;
    }

    .ant-tabs-nav-list {
      min-width: max-content;
      transform: none !important;
    }

    .ant-tabs-nav-more,
    .ant-tabs-nav-operations {
      display: none !important;
    }
  }

  &.dashboard-component-tabs--responsive {
    .ant-tabs-nav {
      padding-inline: 0;
    }

    .ant-tabs-nav-wrap {
      flex: 0 1 calc(100% - ${({ theme }) => theme.sizeUnit * 11 * 2}px);
      margin-inline: ${({ theme }) => theme.sizeUnit * 11}px;
    }

    .ant-tabs-nav-list {
      padding-inline: ${({ theme }) => theme.sizeUnit * 2}px;
    }
  }

  /* Hide ink-bar during drag */
  ${({ isDragging }) =>
    isDragging &&
    `
    .ant-tabs-card > .ant-tabs-nav .ant-tabs-ink-bar,
    .ant-tabs > .ant-tabs-nav .ant-tabs-ink-bar {
      display: none !important;
    }
  `}
`;

const TabScrollButton = styled.button<{ placement: 'left' | 'right' }>`
  ${({ placement, theme }) => css`
    align-items: center;
    background: ${theme.colorBgContainer};
    border: 0;
    color: ${theme.colorText};
    cursor: pointer;
    display: flex;
    height: ${theme.sizeUnit * 11}px;
    justify-content: center;
    min-width: ${theme.sizeUnit * 11}px;
    padding: 0;
    position: absolute;
    ${placement}: 0;
    top: 0;
    transition:
      color ${theme.motionDurationMid} ease-in-out,
      opacity ${theme.motionDurationMid} ease-in-out;
    width: ${theme.sizeUnit * 11}px;
    z-index: 2;

    &:hover:not(:disabled),
    &:focus-visible:not(:disabled) {
      color: ${theme.colorPrimary};
    }

    &:disabled {
      color: ${theme.colorTextDisabled};
      cursor: not-allowed;
      opacity: 0.45;
    }
  `}
`;

const responsiveTabScrollPositions = new Map<string, number>();

export interface TabItem {
  key: string;
  label: ReactElement;
  closeIcon: ReactElement;
  children?: ReactElement;
}

export interface TabsComponent {
  id: string;
}

export interface TabsRendererProps {
  tabItems: TabItem[];
  editMode: boolean;
  renderHoverMenu?: boolean;
  tabsDragSourceRef?: RefObject<HTMLDivElement>;
  handleDeleteComponent: () => void;
  tabsComponent: TabsComponent;
  activeKey: string;
  tabIds: string[];
  handleClickTab: (index: number) => void;
  handleEdit: AntdTabsProps['onEdit'];
  tabBarPaddingLeft?: number;
  onTabsReorder?: (oldIndex: number, newIndex: number) => void;
  isEditingTabTitle?: boolean;
  onTabTitleEditingChange?: (isEditing: boolean) => void;
  responsiveLayout?: boolean;
  responsiveCarousel?: boolean;
}

interface DraggableTabNodeProps extends React.HTMLAttributes<HTMLDivElement> {
  'data-node-key': string;
  disabled?: boolean;
}

const DraggableTabNode: React.FC<Readonly<DraggableTabNodeProps>> = ({
  className,
  disabled = false,
  ...props
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: props['data-node-key'],
    disabled,
  });

  const style: React.CSSProperties = {
    ...props.style,
    position: 'relative',
    transform: transform ? `translate3d(${transform.x}px, 0, 0)` : undefined,
    transition: isDragging ? 'none' : transition,
    cursor: disabled ? 'default' : 'move',
    zIndex: isDragging ? 1000 : 'auto',
    opacity: 1,
  };

  return cloneElement(props.children as React.ReactElement, {
    ref: setNodeRef,
    style,
    ...attributes,
    ...(disabled ? {} : listeners),
  });
};

/**
 * TabsRenderer component handles the rendering of dashboard tabs
 * Extracted from the main Tabs component for better separation of concerns
 */
const TabsRenderer = memo<TabsRendererProps>(
  ({
    tabItems,
    editMode,
    renderHoverMenu = true,
    tabsDragSourceRef,
    handleDeleteComponent,
    tabsComponent,
    activeKey,
    tabIds,
    handleClickTab,
    handleEdit,
    tabBarPaddingLeft = 0,
    onTabsReorder,
    isEditingTabTitle = false,
    onTabTitleEditingChange,
    responsiveLayout = false,
    responsiveCarousel = false,
  }) => {
    const [activeId, setActiveId] = useState<string | null>(null);
    const [scrollControls, setScrollControls] = useState({
      previous: false,
      next: false,
    });
    const tabsContainerRef = useRef<HTMLDivElement>(null);
    const isRestoringScrollRef = useRef(false);
    const preserveScrollUntilRef = useRef(0);
    const userScrollUntilRef = useRef(0);
    const savedScrollLeftRef = useRef(
      responsiveTabScrollPositions.get(tabsComponent.id) ?? 0,
    );

    // Use ref to always have access to the current tabIds in callbacks
    const tabIdsRef = useRef(tabIds);
    tabIdsRef.current = tabIds;

    const sensor = useSensor(PointerSensor, {
      activationConstraint: { distance: 10 },
    });

    const onDragStart = useCallback((event: any) => {
      setActiveId(event.active.id);
    }, []);

    const onDragEnd = useCallback(
      ({ active, over }: DragEndEvent) => {
        const currentTabIds = tabIdsRef.current;
        // Only reorder when we have a valid drop target and both IDs are found
        if (active.id !== over?.id && onTabsReorder) {
          const activeIndex = currentTabIds.findIndex(id => id === active.id);
          const overIndex = currentTabIds.findIndex(id => id === over?.id);
          if (activeIndex !== -1 && overIndex !== -1) {
            onTabsReorder(activeIndex, overIndex);
          }
        }
        setActiveId(null);
      },
      [onTabsReorder],
    );

    const onDragCancel = useCallback(() => {
      setActiveId(null);
    }, []);

    const isDragging = activeId !== null;
    const useResponsiveScrollableTabs =
      (responsiveLayout || responsiveCarousel) &&
      !editMode &&
      tabItems.length > 1;
    const showResponsiveTabControls =
      responsiveCarousel && !editMode && tabItems.length > 1;

    const getScrollElement = useCallback(
      () =>
        tabsContainerRef.current?.querySelector<HTMLElement>(
          '.ant-tabs-nav-wrap',
        ),
      [],
    );

    const updateScrollControls = useCallback(() => {
      const scrollElement = getScrollElement();
      let nextControls = { previous: false, next: false };

      if (showResponsiveTabControls && scrollElement) {
        const maxScrollLeft =
          scrollElement.scrollWidth - scrollElement.clientWidth;

        nextControls = {
          previous: scrollElement.scrollLeft > 1,
          next: scrollElement.scrollLeft < maxScrollLeft - 1,
        };
      }

      setScrollControls(current =>
        current.previous === nextControls.previous &&
        current.next === nextControls.next
          ? current
          : nextControls,
      );
    }, [getScrollElement, showResponsiveTabControls]);

    const captureScrollPosition = useCallback(
      (scrollElement = getScrollElement()) => {
        if (!scrollElement) {
          return;
        }

        savedScrollLeftRef.current = scrollElement.scrollLeft;
        responsiveTabScrollPositions.set(
          tabsComponent.id,
          savedScrollLeftRef.current,
        );
      },
      [getScrollElement, tabsComponent.id],
    );

    const restoreScrollPosition = useCallback(() => {
      const scrollElement = getScrollElement();

      if (!useResponsiveScrollableTabs || !scrollElement) {
        return;
      }

      const maxScrollLeft =
        scrollElement.scrollWidth - scrollElement.clientWidth;
      const savedScrollLeft =
        responsiveTabScrollPositions.get(tabsComponent.id) ??
        savedScrollLeftRef.current;
      savedScrollLeftRef.current = savedScrollLeft;
      const nextScrollLeft = Math.max(
        0,
        Math.min(maxScrollLeft, savedScrollLeft),
      );

      if (Math.abs(scrollElement.scrollLeft - nextScrollLeft) > 0.5) {
        isRestoringScrollRef.current = true;
        scrollElement.scrollLeft = nextScrollLeft;
        window.requestAnimationFrame(() => {
          isRestoringScrollRef.current = false;
        });
      }

      updateScrollControls();
    }, [
      getScrollElement,
      tabsComponent.id,
      updateScrollControls,
      useResponsiveScrollableTabs,
    ]);

    const restorePreservedScrollPosition = useCallback(() => {
      if (!useResponsiveScrollableTabs) {
        return;
      }

      preserveScrollUntilRef.current = Date.now() + 2000;
      restoreScrollPosition();
    }, [restoreScrollPosition, useResponsiveScrollableTabs]);

    const markScrollPositionForPreservation = useCallback(() => {
      if (!useResponsiveScrollableTabs) {
        return;
      }

      captureScrollPosition();
      preserveScrollUntilRef.current = Date.now() + 2000;
    }, [captureScrollPosition, useResponsiveScrollableTabs]);

    const scrollTabs = useCallback(
      (direction: -1 | 1) => {
        const scrollElement = getScrollElement();

        if (!scrollElement) {
          return;
        }

        const scrollDistance = Math.max(
          160,
          Math.floor(scrollElement.clientWidth * 0.75),
        );
        const maxScrollLeft =
          scrollElement.scrollWidth - scrollElement.clientWidth;
        const targetScrollLeft = Math.max(
          0,
          Math.min(
            maxScrollLeft,
            scrollElement.scrollLeft + direction * scrollDistance,
          ),
        );

        savedScrollLeftRef.current = targetScrollLeft;
        responsiveTabScrollPositions.set(tabsComponent.id, targetScrollLeft);

        if (typeof scrollElement.scrollTo === 'function') {
          scrollElement.scrollTo({
            behavior: 'smooth',
            left: targetScrollLeft,
          });
        } else {
          scrollElement.scrollLeft = targetScrollLeft;
        }

        window.setTimeout(() => {
          captureScrollPosition(scrollElement);
          updateScrollControls();
        }, 250);
      },
      [
        captureScrollPosition,
        getScrollElement,
        tabsComponent.id,
        updateScrollControls,
      ],
    );

    useEffect(() => {
      if (!showResponsiveTabControls) {
        updateScrollControls();
        return undefined;
      }

      let scrollElement: HTMLElement | undefined;
      let resizeObserver: ResizeObserver | undefined;
      let retryTimeoutId = 0;
      let updateTimeoutId = 0;

      const attachScrollControls = () => {
        scrollElement = getScrollElement() ?? undefined;

        if (!scrollElement) {
          retryTimeoutId = window.setTimeout(attachScrollControls, 50);
          return;
        }

        const ResizeObserverCtor = window.ResizeObserver;
        resizeObserver = ResizeObserverCtor
          ? new ResizeObserverCtor(updateScrollControls)
          : undefined;
        updateTimeoutId = window.setTimeout(updateScrollControls, 100);

        updateScrollControls();
        scrollElement.addEventListener('scroll', updateScrollControls, {
          passive: true,
        });
        window.addEventListener('resize', updateScrollControls);
        resizeObserver?.observe(scrollElement);
        resizeObserver?.observe(tabsContainerRef.current ?? scrollElement);
      };

      attachScrollControls();

      return () => {
        window.clearTimeout(retryTimeoutId);
        window.clearTimeout(updateTimeoutId);
        scrollElement?.removeEventListener('scroll', updateScrollControls);
        window.removeEventListener('resize', updateScrollControls);
        resizeObserver?.disconnect();
      };
    }, [
      activeKey,
      getScrollElement,
      showResponsiveTabControls,
      tabItems.length,
      updateScrollControls,
    ]);

    useLayoutEffect(() => {
      if (!useResponsiveScrollableTabs) {
        return undefined;
      }

      restoreScrollPosition();

      const animationFrameId = window.requestAnimationFrame(
        restoreScrollPosition,
      );

      return () => {
        window.cancelAnimationFrame(animationFrameId);
      };
    }, [
      activeKey,
      restoreScrollPosition,
      tabItems.length,
      useResponsiveScrollableTabs,
    ]);

    useEffect(() => {
      if (!useResponsiveScrollableTabs) {
        return undefined;
      }

      let retryTimeoutId = 0;
      let cleanupScrollableTabs = () => {};

      const attachScrollableTabs = () => {
        const scrollElement = getScrollElement();

        if (!scrollElement) {
          retryTimeoutId = window.setTimeout(attachScrollableTabs, 50);
          return;
        }

        const markUserScroll = () => {
          userScrollUntilRef.current = Date.now() + 1000;
        };

        const handleScroll = () => {
          if (isRestoringScrollRef.current) {
            return;
          }

          if (Date.now() < preserveScrollUntilRef.current) {
            restoreScrollPosition();
            return;
          }

          if (
            scrollElement.scrollLeft <= 1 &&
            savedScrollLeftRef.current > 1 &&
            Date.now() > userScrollUntilRef.current
          ) {
            restoreScrollPosition();
            return;
          }

          captureScrollPosition(scrollElement);
          updateScrollControls();
        };

        const handleWheel = (event: WheelEvent) => {
          const maxScrollLeft =
            scrollElement.scrollWidth - scrollElement.clientWidth;

          if (maxScrollLeft <= 0) {
            return;
          }

          const scrollDelta =
            Math.abs(event.deltaX) > Math.abs(event.deltaY)
              ? event.deltaX
              : event.deltaY;

          if (scrollDelta === 0) {
            return;
          }

          markUserScroll();

          const nextScrollLeft = Math.max(
            0,
            Math.min(maxScrollLeft, scrollElement.scrollLeft + scrollDelta),
          );

          if (nextScrollLeft === scrollElement.scrollLeft) {
            return;
          }

          event.preventDefault();
          scrollElement.scrollLeft = nextScrollLeft;
          captureScrollPosition(scrollElement);
          updateScrollControls();
        };

        const handleVisibilityChange = () => {
          if (document.visibilityState === 'visible') {
            restoreScrollPosition();
          }
        };

        scrollElement.addEventListener('scroll', handleScroll, {
          passive: true,
        });
        scrollElement.addEventListener('wheel', handleWheel, {
          passive: false,
        });
        scrollElement.addEventListener('touchmove', markUserScroll, {
          passive: true,
        });
        window.addEventListener('focus', restoreScrollPosition);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        cleanupScrollableTabs = () => {
          scrollElement.removeEventListener('scroll', handleScroll);
          scrollElement.removeEventListener('wheel', handleWheel);
          scrollElement.removeEventListener('touchmove', markUserScroll);
          window.removeEventListener('focus', restoreScrollPosition);
          document.removeEventListener(
            'visibilitychange',
            handleVisibilityChange,
          );
        };
      };

      attachScrollableTabs();

      return () => {
        window.clearTimeout(retryTimeoutId);
        cleanupScrollableTabs();
      };
    }, [
      captureScrollPosition,
      getScrollElement,
      restoreScrollPosition,
      useResponsiveScrollableTabs,
      updateScrollControls,
    ]);

    return (
      <StyledTabsContainer
        ref={tabsContainerRef}
        onMouseDownCapture={event => {
          if (event.button !== 0) {
            return;
          }

          const target = event.target;
          if (target instanceof Element && target.closest('.ant-tabs-tab')) {
            event.preventDefault();
            markScrollPositionForPreservation();
          }
        }}
        className={`dashboard-component dashboard-component-tabs${
          useResponsiveScrollableTabs
            ? ' dashboard-component-tabs--responsive-scroll'
            : ''
        }${
          showResponsiveTabControls
            ? ' dashboard-component-tabs--responsive'
            : ''
        }`}
        data-test="dashboard-component-tabs"
        isDragging={isDragging}
      >
        {editMode && renderHoverMenu && tabsDragSourceRef && (
          <HoverMenu innerRef={tabsDragSourceRef} position="left">
            <DragHandle position="left" />
            <DeleteComponentButton onDelete={handleDeleteComponent} />
          </HoverMenu>
        )}

        {showResponsiveTabControls && (
          <>
            <TabScrollButton
              aria-label={t('Scroll tabs left')}
              disabled={!scrollControls.previous}
              onClick={() => scrollTabs(-1)}
              placement="left"
              type="button"
            >
              <Icons.LeftOutlined iconSize="m" />
            </TabScrollButton>
            <TabScrollButton
              aria-label={t('Scroll tabs right')}
              disabled={!scrollControls.next}
              onClick={() => scrollTabs(1)}
              placement="right"
              type="button"
            >
              <Icons.RightOutlined iconSize="m" />
            </TabScrollButton>
          </>
        )}

        <LineEditableTabs
          id={tabsComponent.id}
          activeKey={activeKey}
          onChange={key => {
            if (typeof key === 'string') {
              restorePreservedScrollPosition();
              const tabIndex = tabIds.indexOf(key);
              if (tabIndex !== -1) handleClickTab(tabIndex);
            }
          }}
          onEdit={handleEdit}
          data-test="nav-list"
          type={editMode ? 'editable-card' : 'card'}
          items={tabItems}
          tabBarStyle={{ paddingLeft: tabBarPaddingLeft }}
          fullHeight
          {...(editMode && {
            renderTabBar: (tabBarProps, DefaultTabBar) => (
              <DndContext
                key={tabIds.join('-')}
                sensors={[sensor]}
                onDragStart={onDragStart}
                onDragEnd={onDragEnd}
                onDragCancel={onDragCancel}
                collisionDetection={closestCenter}
              >
                <SortableContext
                  items={tabIds}
                  strategy={horizontalListSortingStrategy}
                >
                  <DefaultTabBar {...tabBarProps}>
                    {(node: React.ReactElement) => (
                      <DraggableTabNode
                        {...(node as React.ReactElement<DraggableTabNodeProps>)
                          .props}
                        key={node.key}
                        data-node-key={node.key as string}
                        disabled={isEditingTabTitle}
                      >
                        {node}
                      </DraggableTabNode>
                    )}
                  </DefaultTabBar>
                </SortableContext>
              </DndContext>
            ),
          })}
        />
      </StyledTabsContainer>
    );
  },
);

TabsRenderer.displayName = 'TabsRenderer';

export default TabsRenderer;
