/**
 * Mobile-first responsive design utilities for Apache Superset dashboards
 * Addresses: filter bar width, grid layout, chart heights, sidebar collapse
 */

import { css } from 'styled-components';

// Responsive breakpoints (pixels)
export const BREAKPOINTS = {
  xs: 0,      // Extra small: phones
  sm: 576,    // Small: tablets
  md: 768,    // Medium: small laptops
  lg: 992,    // Large: desktops
  xl: 1200,   // Extra large: large desktops
  xxl: 1600,
};

// Mobile-first media query helpers
export const media = {
  xs: (styles: ReturnType<typeof css>) => css`
    @media (min-width: ${BREAKPOINTS.xs}px) {
      ${styles}
    }
  `,
  sm: (styles: ReturnType<typeof css>) => css`
    @media (min-width: ${BREAKPOINTS.sm}px) {
      ${styles}
    }
  `,
  md: (styles: ReturnType<typeof css>) => css`
    @media (min-width: ${BREAKPOINTS.md}px) {
      ${styles}
    }
  `,
  lg: (styles: ReturnType<typeof css>) => css`
    @media (min-width: ${BREAKPOINTS.lg}px) {
      ${styles}
    }
  `,
  xl: (styles: ReturnType<typeof css>) => css`
    @media (min-width: ${BREAKPOINTS.xl}px) {
      ${styles}
    }
  `,
  // Mobile-friendly touch target minimum (44x44px per Apple HIG)
  touchTarget: '44px',
};

// Dashboard responsive grid columns
export const getGridColumns = (screenWidth: number): number => {
  if (screenWidth < BREAKPOINTS.sm) return 1;      // Phones: 1 column
  if (screenWidth < BREAKPOINTS.md) return 2;      // Tablets: 2 columns
  if (screenWidth < BREAKPOINTS.lg) return 4;      // Small laptops: 4 columns
  return 12;                                         // Desktops: 12 columns
};

// Responsive filter bar width
export const getFilterBarWidth = (screenWidth: number): number => {
  if (screenWidth < BREAKPOINTS.sm) return 0;      // Hidden on phones
  if (screenWidth < BREAKPOINTS.md) return 150;    // Compact on tablets
  return 260;                                        // Full width on desktop
};

// Responsive chart height (viewport-relative)
export const getChartHeight = (screenHeight: number, baseHeight = 400): number => {
  if (screenHeight < 600) return Math.min(baseHeight, screenHeight - 200);
  return baseHeight;
};

// Responsive sidebar width
export const getSidebarWidth = (screenWidth: number): number => {
  if (screenWidth < BREAKPOINTS.md) return 0;      // Hidden on tablets/phones
  if (screenWidth < BREAKPOINTS.lg) return 200;    // Compact on small laptops
  return 374;                                        // Full width on desktop
};

/**
 * Usage in styled-components:
 * 
 * const MyDashboard = styled.div`
 *   display: flex;
 *   
 *   ${media.xs(css`
 *     flex-direction: column;
 *     gap: 12px;
 *   `)}
 *   
 *   ${media.md(css`
 *     flex-direction: row;
 *     gap: 24px;
 *   `)}
 * `;
 */
