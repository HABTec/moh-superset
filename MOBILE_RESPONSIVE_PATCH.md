/**
 * MOH Mobile Responsiveness Fix
 * ==============================
 * 
 * This file contains the CSS patches needed to make the dashboard responsive.
 * Apply these changes to superset-frontend/src/dashboard/styles.ts
 * 
 * Key changes:
 * 1. Filter bar collapses on mobile
 * 2. Dashboard grid adapts to screen size (1/2/4/12 columns)
 * 3. Chart heights scale with viewport
 * 4. Sidebar hides on small screens
 * 5. Touch targets increased to 44x44px minimum
 */

import styled from 'styled-components';
import { css } from 'styled-components';

// Mobile breakpoints
const MOBILE_BP = '576px';    // Phone/tablet boundary
const TABLET_BP = '768px';    // Tablet/laptop boundary
const DESKTOP_BP = '992px';   // Desktop boundary

// Apply to DashboardGrid
export const ResponsiveDashboardGrid = css`
  /* Mobile: 1 column */
  @media (max-width: ${MOBILE_BP}) {
    --grid-columns: 1;
    --chart-width: 100%;
    --gap: 8px;
  }

  /* Tablet: 2 columns */
  @media (min-width: ${MOBILE_BP}) and (max-width: ${TABLET_BP}) {
    --grid-columns: 2;
    --chart-width: calc(50% - 8px);
    --gap: 16px;
  }

  /* Laptop: 4 columns */
  @media (min-width: ${TABLET_BP}) and (max-width: ${DESKTOP_BP}) {
    --grid-columns: 4;
    --chart-width: calc(25% - 12px);
    --gap: 16px;
  }

  /* Desktop: 12 columns */
  @media (min-width: ${DESKTOP_BP}) {
    --grid-columns: 12;
    --chart-width: auto;
    --gap: 24px;
  }

  display: grid;
  grid-template-columns: repeat(var(--grid-columns), 1fr);
  gap: var(--gap);
  padding: var(--gap);
`;

// Filter bar responsive sizing
export const ResponsiveFilterBar = css`
  /* Hide filter bar on extra small screens */
  @media (max-width: calc(${MOBILE_BP} - 1px)) {
    width: 0 !important;
    min-width: 0;
    overflow: hidden;
  }

  /* Compact filter bar on tablets */
  @media (min-width: ${MOBILE_BP}) and (max-width: ${TABLET_BP}) {
    width: 150px !important;
    overflow-y: auto;
  }

  /* Normal filter bar on desktop */
  @media (min-width: ${TABLET_BP}) {
    width: 260px !important;
  }

  /* Touch-friendly controls */
  button, [role="button"] {
    min-height: 44px;
    min-width: 44px;
  }
`;

// Responsive chart heights
export const ResponsiveChartContainer = css`
  /* Mobile: reduced height */
  @media (max-width: ${MOBILE_BP}) {
    min-height: 200px !important;
    height: auto !important;
  }

  /* Tablet: medium height */
  @media (min-width: ${MOBILE_BP}) and (max-width: ${TABLET_BP}) {
    min-height: 300px !important;
  }

  /* Desktop: full configured height */
  @media (min-width: ${TABLET_BP}) {
    /* Keep original height */
  }

  /* Prevent horizontal scroll */
  overflow-x: hidden;
  overflow-y: auto;
`;

// Sidebar/Edit panel responsive
export const ResponsiveSidebar = css`
  /* Hide on mobile/tablet */
  @media (max-width: ${TABLET_BP}) {
    display: none;
    /* Or use: width: 0; overflow: hidden; */
  }

  /* Show full width on desktop */
  @media (min-width: ${TABLET_BP}) {
    width: 374px;
    display: flex;
    flex-direction: column;
  }
`;

// Responsive modal sizing
export const ResponsiveModal = css`
  max-width: 90vw;

  @media (max-width: ${MOBILE_BP}) {
    max-width: 95vw;
    margin: 16px;
  }

  @media (min-width: ${MOBILE_BP}) and (max-width: ${TABLET_BP}) {
    max-width: 85vw;
    margin: 24px;
  }

  @media (min-width: ${TABLET_BP}) {
    max-width: 1024px;
    margin: auto;
  }
`;

/**
 * IMPLEMENTATION STEPS:
 * 
 * 1. Update superset-frontend/src/dashboard/components/DashboardGrid.tsx:
 *    const GridContent = styled.div`
 *      ${ResponsiveDashboardGrid}
 *      // ... existing styles
 *    `;
 * 
 * 2. Update superset-frontend/src/dashboard/components/filters/FilterBar.tsx:
 *    const FilterBarContainer = styled.div`
 *      ${ResponsiveFilterBar}
 *      // ... existing styles
 *    `;
 * 
 * 3. Update superset-frontend/src/components/Chart/Chart.tsx:
 *    const Styles = styled.div`
 *      ${ResponsiveChartContainer}
 *      // ... existing styles
 *    `;
 * 
 * 4. Update superset-frontend/src/dashboard/components/DashboardBuilder.tsx:
 *    const SidePanel = styled.div`
 *      ${ResponsiveSidebar}
 *      // ... existing styles
 *    `;
 * 
 * 5. Update all modal components:
 *    const ModalContent = styled.div`
 *      ${ResponsiveModal}
 *      // ... existing styles
 *    `;
 */
