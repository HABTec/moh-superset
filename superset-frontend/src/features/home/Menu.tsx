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
import { useState, useEffect } from 'react';
import { styled, css, useTheme } from '@apache-superset/core/theme';
import { t } from '@apache-superset/core/translation';
import { ensureStaticPrefix } from 'src/utils/assetUrl';
import { ensureAppRoot } from 'src/utils/pathUtils';
import { getUrlParam } from 'src/utils/urlUtils';
import { MainNav, MenuItem } from '@superset-ui/core/components/Menu';
import {
  Button,
  Drawer,
  Tooltip,
  Grid,
  Row,
  Col,
  Image,
} from '@superset-ui/core/components';
import { GenericLink } from 'src/components';
import { NavLink, useLocation } from 'react-router-dom';
import { Icons } from '@superset-ui/core/components/Icons';
import { Typography } from '@superset-ui/core/components/Typography';
import { useUiConfig } from 'src/components/UiConfigContext';
import { URL_PARAMS } from 'src/constants';
import {
  MenuObjectChildProps,
  MenuObjectProps,
  MenuData,
} from 'src/types/bootstrapTypes';
import {
  RESPONSIVE_DASHBOARD_BREAKPOINTS,
  isResponsiveDashboardCompact,
  isResponsiveDashboardMobileViewport,
} from 'src/dashboard/util/responsiveDashboard';
import { datasetsLabel } from 'src/features/semanticLayers/label';
import RightMenu from './RightMenu';
import { NAVBAR_MENU_POPUP_OFFSET } from './commonMenuData';

interface MenuProps {
  data: MenuData;
  isFrontendRoute?: (path?: string) => boolean;
}

const StyledHeader = styled.header`
  ${({ theme }) => css`
    background-color: ${theme.colorBgContainer};
    border-bottom: 1px solid ${theme.colorBorderSecondary};
    padding: 0 ${theme.sizeUnit * 4}px;
    z-index: 10;

    @media (max-width: ${theme.screenMDMax}px) {
      padding: 0 ${theme.sizeUnit * 4}px;
    }

    &:nth-last-of-type(2) nav {
      margin-bottom: 2px;
    }

    .caret {
      display: none;
    }
  `}
`;

const StyledBrandText = styled.div`
  ${({ theme }) => css`
    border-left: 1px solid ${theme.colorBorderSecondary};
    border-right: 1px solid ${theme.colorBorderSecondary};
    height: 100%;
    color: ${theme.colorText};
    padding-left: ${theme.sizeUnit * 4}px;
    padding-right: ${theme.sizeUnit * 4}px;
    font-size: ${theme.fontSizeLG}px;
    float: left;
    display: flex;
    flex-direction: column;
    justify-content: center;

    span {
      max-width: ${theme.sizeUnit * 58}px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    @media (max-width: 1127px) {
      display: none;
    }
  `}
`;

const StyledMainNav = styled(MainNav)`
  ${({ theme }) => css`
    .ant-menu-item .ant-menu-item-icon + span,
    .ant-menu-submenu-title .ant-menu-item-icon + span,
    .ant-menu-item .anticon + span,
    .ant-menu-submenu-title .anticon + span {
      margin-inline-start: 0;
    }

    .ant-menu-submenu.ant-menu-submenu-horizontal {
      display: flex;
      align-items: center;
      height: 100%;
      padding: 0;

      .ant-menu-submenu-title {
        display: flex;
        gap: ${theme.sizeUnit * 2}px;
        flex-direction: row-reverse;
        align-items: center;
        height: 100%;
        padding: 0 ${theme.sizeUnit * 4}px;
      }

      &:hover,
      &.ant-menu-submenu-active {
        .ant-menu-title-content {
          color: ${theme.colorPrimary};
        }
      }

      &::after {
        content: '';
        position: absolute;
        width: 98%;
        height: 2px;
        background-color: ${theme.colorPrimaryBorderHover};
        bottom: ${theme.sizeUnit / 8}px;
        left: 1%;
        right: auto;
        inset-inline-start: 1%;
        inset-inline-end: auto;
        transform: scale(0);
        transition: 0.2s all ease-out;
      }

      &:hover::after,
      &.ant-menu-submenu-open::after {
        transform: scale(1);
      }
    }

    .ant-menu-submenu-selected.ant-menu-submenu-horizontal::after {
      transform: scale(1);
    }
  `}
`;

const StyledBrandWrapper = styled.div<{ margin?: string }>`
  ${({ margin }) => css`
    height: ${margin ? 'auto' : '100%'};
    margin: ${margin ?? 0};
  `}
`;

const StyledBrandLink = styled(Typography.Link)`
  ${({ theme }) => css`
    align-items: center;
    display: flex;
    height: 100%;
    justify-content: center;

    &:focus {
      border-color: transparent;
    }

    &:focus-visible {
      border-color: ${theme.colorPrimaryText};
    }
  `}
`;

const StyledRow = styled(Row)`
  height: 100%;
  position: relative;
`;

const StyledCol = styled(Col)`
  ${({ theme }) => css`
    display: flex;
    gap: ${theme.sizeUnit * 4}px;
    flex-wrap: wrap;

    @media (max-width: ${theme.screenMDMax}px) {
      align-items: center;
      flex: 0 0 100%;
      flex-wrap: nowrap;
      gap: ${theme.sizeUnit * 2}px;
      justify-content: space-between;
      max-width: 100%;
      min-height: ${theme.sizeUnit * 16}px;
    }

    @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
      align-items: center;
      flex: 0 0 100%;
      flex-wrap: nowrap;
      gap: ${theme.sizeUnit * 2}px;
      justify-content: space-between;
      max-width: 100%;
      min-height: ${theme.sizeUnit * 16}px;
    }
  `}
`;

const StyledDesktopRightCol = styled(Col)`
  ${({ theme }) => css`
    @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
      display: block;
      flex: 0 0 auto;
      max-width: none;
      pointer-events: none;
      position: absolute;
      right: ${theme.sizeUnit * 18}px;
      top: ${theme.sizeUnit * 3}px;
      width: auto;
      z-index: 11;

      > div > :not(.moh-nav-dashboard-actions) {
        display: none !important;
      }

      .moh-nav-dashboard-actions {
        align-items: center !important;
        display: flex !important;
        gap: ${theme.sizeUnit}px !important;
        height: ${theme.sizeUnit * 11}px !important;
        margin-left: 0 !important;
        pointer-events: auto;
        width: auto !important;
      }

      .moh-nav-dashboard-actions .ant-btn {
        height: ${theme.sizeUnit * 11}px !important;
        min-width: ${theme.sizeUnit * 11}px !important;
      }
    }
  `}
`;

const StyledMobileMenuButton = styled(Button)`
  ${({ theme }) => css`
    display: none;

    @media (max-width: ${theme.screenMDMax}px) {
      align-items: center;
      display: inline-flex;
      height: ${theme.sizeUnit * 11}px;
      justify-content: center;
      min-width: ${theme.sizeUnit * 11}px;
      padding: 0;
    }

    @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
      align-items: center;
      display: inline-flex;
      height: ${theme.sizeUnit * 11}px;
      justify-content: center;
      min-width: ${theme.sizeUnit * 11}px;
      padding: 0;
      position: relative;
      z-index: 12;
    }
  `}
`;

const StyledMobileDashboardActionsSlot = styled.div`
  ${({ theme }) => css`
    display: none;

    @media (max-width: ${RESPONSIVE_DASHBOARD_BREAKPOINTS.compact}px) {
      body.moh-responsive-dashboard-mobile & {
        align-items: center;
        display: flex;
        height: ${theme.sizeUnit * 11}px;
        margin-left: auto;
        pointer-events: auto;
      }

      body.moh-responsive-dashboard-mobile & .ant-btn {
        height: ${theme.sizeUnit * 11}px;
        min-width: ${theme.sizeUnit * 11}px;
      }
    }
  `}
`;

const StyledMobileDrawerContent = styled.div`
  ${({ theme }) => css`
    display: flex;
    flex-direction: column;
    gap: ${theme.sizeUnit * 4}px;

    .main-nav {
      border-inline-end: none !important;
    }

    .ant-menu-inline {
      width: 100%;
    }

    .ant-menu-item,
    .ant-menu-submenu-title {
      min-height: ${theme.sizeUnit * 11}px;
    }
  `}
`;

const StyledMobileDrawerActions = styled.div`
  ${({ theme }) => css`
    border-top: 1px solid ${theme.colorBorderSecondary};
    padding-top: ${theme.sizeUnit * 4}px;

    > div {
      align-items: flex-start;
      flex-direction: column;
      gap: ${theme.sizeUnit * 2}px;
      height: auto;
    }

    .ant-menu {
      border-inline-end: none !important;
    }

    .ant-menu-horizontal {
      flex-direction: column;
      width: 100%;
    }

    .ant-menu-submenu,
    .ant-menu-submenu-title {
      width: 100%;
    }
  `}
`;

const StyledImage = styled(Image)`
  object-fit: contain;
`;

const { useBreakpoint } = Grid;

const getViewportSize = () => ({
  width: typeof window === 'undefined' ? 0 : window.innerWidth,
  height: typeof window === 'undefined' ? 0 : window.innerHeight,
});

export function Menu({
  data: {
    menu,
    brand,
    navbar_right: navbarRight,
    settings,
    environment_tag: environmentTag,
  },
  isFrontendRoute = () => false,
}: MenuProps) {
  const screens = useBreakpoint();
  const uiConfig = useUiConfig();
  const theme = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [viewportSize, setViewportSize] = useState(getViewportSize);

  useEffect(() => {
    const syncViewportSize = () => {
      setViewportSize(getViewportSize());
    };

    syncViewportSize();
    window.addEventListener('resize', syncViewportSize);
    window.addEventListener('orientationchange', syncViewportSize);

    return () => {
      window.removeEventListener('resize', syncViewportSize);
      window.removeEventListener('orientationchange', syncViewportSize);
    };
  }, []);
  const useMobileNavigation =
    screens.lg === false ||
    isResponsiveDashboardCompact(viewportSize.width) ||
    isResponsiveDashboardMobileViewport(
      viewportSize.width,
      viewportSize.height,
    );

  enum Paths {
    Explore = '/explore',
    Dashboard = '/dashboard',
    Chart = '/chart',
    Datasets = '/tablemodelview',
    SqlLab = '/sqllab',
    SavedQueries = '/savedqueryview',
  }

  const defaultTabSelection: string[] = [];
  const [activeTabs, setActiveTabs] = useState(defaultTabSelection);
  const location = useLocation();
  useEffect(() => {
    const path = location.pathname;
    switch (true) {
      case path.startsWith(Paths.Dashboard):
        setActiveTabs(['Dashboards']);
        break;
      case path.startsWith(Paths.Chart) || path.startsWith(Paths.Explore):
        setActiveTabs(['Charts']);
        break;
      case path.startsWith(Paths.Datasets):
        setActiveTabs([datasetsLabel()]);
        break;
      case path.startsWith(Paths.SqlLab) || path.startsWith(Paths.SavedQueries):
        setActiveTabs(['SQL']);
        break;
      default:
        setActiveTabs(defaultTabSelection);
    }
  }, [location.pathname]);

  const standalone = getUrlParam(URL_PARAMS.standalone);
  if (standalone || uiConfig.hideNav) return <></>;

  const buildMenuItem = ({
    label,
    childs,
    url,
    isFrontendRoute,
  }: MenuObjectProps): MenuItem => {
    if (url && isFrontendRoute) {
      return {
        key: label,
        label: (
          <NavLink role="button" to={url} activeClassName="is-active">
            {label}
          </NavLink>
        ),
      };
    }

    if (url) {
      return {
        key: label,
        label: <Typography.Link href={url}>{label}</Typography.Link>,
      };
    }

    const childItems: MenuItem[] = [];
    childs?.forEach((child: MenuObjectChildProps | string, index1: number) => {
      if (typeof child === 'string' && child === '-' && label !== 'Data') {
        childItems.push({ type: 'divider', key: `divider-${index1}` });
      } else if (typeof child !== 'string') {
        childItems.push({
          key: `${child.label}`,
          label: child.isFrontendRoute ? (
            <NavLink to={child.url || ''} exact activeClassName="is-active">
              {child.label}
            </NavLink>
          ) : (
            <Typography.Link href={child.url}>{child.label}</Typography.Link>
          ),
        });
      }
    });

    return {
      key: label,
      label,
      ...(!useMobileNavigation &&
        screens.md && {
          icon: <Icons.DownOutlined iconSize="xs" />,
          popupOffset: NAVBAR_MENU_POPUP_OFFSET,
        }),
      children: childItems,
    };
  };
  const renderBrand = () => {
    let link;
    if (theme.brandLogoUrl) {
      link = (
        <StyledBrandWrapper margin={theme.brandLogoMargin}>
          <StyledBrandLink href={ensureAppRoot(theme.brandLogoHref)}>
            <StyledImage
              preview={false}
              src={ensureStaticPrefix(theme.brandLogoUrl)}
              alt={theme.brandLogoAlt || 'Apache Superset'}
              height={theme.brandLogoHeight}
            />
          </StyledBrandLink>
        </StyledBrandWrapper>
      );
    } else if (isFrontendRoute(window.location.pathname)) {
      // ---------------------------------------------------------------------------------
      // TODO: deprecate this once Theme is fully rolled out
      // Kept as is for backwards compatibility with the old theme system / superset_config.py
      link = (
        <GenericLink className="navbar-brand" to={brand.path}>
          <StyledImage
            preview={false}
            src={ensureStaticPrefix(brand.icon)}
            alt={brand.alt}
          />
        </GenericLink>
      );
    } else {
      link = (
        <Typography.Link
          className="navbar-brand"
          href={ensureAppRoot(brand.path)}
          tabIndex={-1}
        >
          <StyledImage
            preview={false}
            src={ensureStaticPrefix(brand.icon)}
            alt={brand.alt}
          />
        </Typography.Link>
      );
    }
    // ---------------------------------------------------------------------------------
    return <>{link}</>;
  };

  const mainNavItems = menu.map(item => {
    const props = {
      ...item,
      isFrontendRoute: isFrontendRoute(item.url),
      childs: item.childs?.map(c => {
        if (typeof c === 'string') {
          return c;
        }

        return {
          ...c,
          isFrontendRoute: isFrontendRoute(c.url),
        };
      }),
    };

    return buildMenuItem(props);
  });

  return (
    <StyledHeader
      className="top"
      id="main-menu"
      role="navigation"
      aria-label={t('Main navigation')}
    >
      <StyledRow>
        <StyledCol md={16} xs={24}>
          <Tooltip
            id="brand-tooltip"
            placement="bottomLeft"
            title={brand.tooltip}
            arrow={{ pointAtCenter: true }}
          >
            {renderBrand()}
          </Tooltip>
          {brand.text && (
            <StyledBrandText>
              <span>{brand.text}</span>
            </StyledBrandText>
          )}
          {!useMobileNavigation && (
            <StyledMainNav
              mode="horizontal"
              data-test="navbar-top"
              className="main-nav"
              selectedKeys={activeTabs}
              disabledOverflow
              items={mainNavItems}
            />
          )}
          {useMobileNavigation && (
            <>
              <StyledMobileDashboardActionsSlot
                id="moh-mobile-dashboard-actions-slot"
                aria-label={t('Dashboard actions')}
              />
              <StyledMobileMenuButton
                aria-label={t('Open navigation menu')}
                icon={<Icons.MenuOutlined iconSize="m" />}
                onClick={() => setMobileMenuOpen(true)}
                type="default"
              />
            </>
          )}
        </StyledCol>
        <StyledDesktopRightCol md={8} xs={24}>
          <RightMenu
            align={screens.md ? 'flex-end' : 'flex-start'}
            settings={settings}
            navbarRight={navbarRight}
            isFrontendRoute={isFrontendRoute}
            environmentTag={environmentTag}
          />
        </StyledDesktopRightCol>
      </StyledRow>
      {useMobileNavigation && (
        <Drawer
          title={t('Navigation')}
          placement="right"
          open={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          width={320}
        >
          <StyledMobileDrawerContent>
            <StyledMainNav
              mode="inline"
              data-test="navbar-mobile"
              className="main-nav"
              selectedKeys={activeTabs}
              disabledOverflow
              items={mainNavItems}
              onClick={() => setMobileMenuOpen(false)}
            />
            <StyledMobileDrawerActions>
              <RightMenu
                align="flex-start"
                settings={settings}
                navbarRight={navbarRight}
                isFrontendRoute={isFrontendRoute}
                environmentTag={environmentTag}
              />
            </StyledMobileDrawerActions>
          </StyledMobileDrawerContent>
        </Drawer>
      )}
    </StyledHeader>
  );
}

// transform the menu data to reorganize components
export default function MenuWrapper({ data, ...rest }: MenuProps) {
  const newMenuData = {
    ...data,
  };
  // Menu items that should go into settings dropdown
  const settingsMenus = {
    Data: true,
    Security: true,
    Manage: true,
  };

  // Remap labels that depend on feature flags so they stay in sync with
  // the active-tab key used in the Menu component above.
  const labelOverrides: Record<string, () => string> = {
    Datasets: datasetsLabel,
  };

  // Cycle through menu.menu to build out cleanedMenu and settings
  const cleanedMenu: MenuObjectProps[] = [];
  const settings: MenuObjectProps[] = [];
  newMenuData.menu.forEach((item: any) => {
    if (!item) {
      return;
    }

    const children: (MenuObjectProps | string)[] = [];
    const newItem = {
      ...item,
      // Apply any label override for this item (keyed by FAB internal name).
      ...(item.name && labelOverrides[item.name]
        ? { label: labelOverrides[item.name]() }
        : {}),
    };

    // Filter childs
    if (item.childs) {
      item.childs.forEach((child: MenuObjectChildProps | string) => {
        if (typeof child === 'string') {
          children.push(child);
        } else if ((child as MenuObjectChildProps).label) {
          children.push(child);
        }
      });

      newItem.childs = children;
    }

    if (!settingsMenus.hasOwnProperty(item.name)) {
      cleanedMenu.push(newItem);
    } else {
      settings.push(newItem);
    }
  });

  newMenuData.menu = cleanedMenu;
  newMenuData.settings = settings;

  return <Menu data={newMenuData} {...rest} />;
}
