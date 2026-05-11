/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 *
 * Admin-facing settings shown when configuring an OrgUnitTree filter on a
 * dashboard. Kept minimal — sensible defaults pulled from the Flask side
 * mean most installs need no config.
 */
import { t } from '@apache-superset/core/translation';
import { ControlPanelConfig } from '@superset-ui/chart-controls';

const config: ControlPanelConfig = {
  controlPanelSections: [
    {
      label: t('Tree settings'),
      expanded: true,
      controlSetRows: [
        [
          {
            name: 'apiBaseUrl',
            config: {
              type: 'TextControl',
              label: t('API base URL'),
              description: t(
                'Flask adapter that serves the DHIS2-shape JSON. Default points at the bundled /api/v1/moh/dhis2 endpoint.',
              ),
              default: '/api/v1/moh/dhis2',
              renderTrigger: true,
            },
          },
        ],
        [
          {
            name: 'rootLevel',
            config: {
              type: 'TextControl',
              label: t('Root level'),
              description: t('Org unit level shown at the top of the tree (1 = Country, 2 = Region).'),
              default: '1',
              isInt: true,
              renderTrigger: true,
            },
          },
          {
            name: 'maxLevel',
            config: {
              type: 'TextControl',
              label: t('Max level'),
              description: t('Deepest level the tree can drill to (6 = Health Post).'),
              default: '6',
              isInt: true,
              renderTrigger: true,
            },
          },
        ],
      ],
    },
  ],
};

export default config;
